"""Director service - battlegroup director API and ConfigMap management."""

import json
import logging
import urllib.request
import configparser
import io
import base64
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DirectorService:
    """Service for interacting with the game server's battlegroup director.

    Handles:
    - Director API requests (battlegroup status, config updates, character transfers)
    - Kubernetes ConfigMap patching for director.ini overrides
    - INI section manipulation for map-specific config
    """

    def __init__(self, host: str, node_port: int, k8s_service, ssh_service, namespace: str):
        self.host = host
        self.node_port = node_port
        self.base_url = f"http://{host}:{node_port}"
        self.k8s = k8s_service
        self.ssh = ssh_service
        self.namespace = namespace
        resource_prefix = namespace
        for prefix in ['funcom-seabass-']:
            if resource_prefix.startswith(prefix):
                resource_prefix = resource_prefix[len(prefix):]
                break
        self.resource_prefix = resource_prefix
        self.cm_name = f"{resource_prefix}-bgd-conf-cm"

    def _request(self, path: str, method: str = 'GET', data: Any = None,
                 timeout: int = 15, raw_data: bool = False) -> str:
        """Execute HTTP request to director service via NodePort.

        Args:
            path: URL path (e.g., '/v0/battlegroup').
            method: HTTP method.
            data: Request body (dict for JSON, str for raw).
            timeout: Request timeout in seconds.
            raw_data: If True, send data as raw text instead of JSON.

        Returns:
            Response body as string.
        """
        url = f"{self.base_url}{path}"
        logger.debug("Director request: %s %s", method, url)

        if method == 'GET':
            req = urllib.request.Request(url)
        else:
            if raw_data and isinstance(data, str):
                body = data.encode()
            elif data is not None:
                body = json.dumps(data).encode()
            else:
                body = None
            req = urllib.request.Request(
                url, data=body,
                headers={'Content-Type': 'application/json'},
                method=method
            )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode()

    # ── Director API methods ──────────────────────────────────────────

    def get_battlegroup(self) -> str:
        """Fetch current battlegroup status."""
        return self._request('/v0/battlegroup')

    def update_server_config(self, config: Dict) -> str:
        """Update server group configuration."""
        return self._request(
            '/v0/BattlegroupUpdateServerGroupConfig',
            method='POST', data=config, timeout=30
        )

    def clear_map_config(self, map_name: str) -> str:
        """Clear map config overrides."""
        return self._request(
            '/v0/BattlegroupClearMapConfigOverrides',
            method='POST', data=map_name, timeout=30, raw_data=True
        )

    def fetch_character_transfer_rules(self) -> str:
        """Fetch character transfer rules."""
        return self._request('/v0/BattlegroupFetchCharacterTransferRules')

    def update_character_transfer(self, config: Dict) -> str:
        """Update character transfer settings."""
        return self._request(
            '/v0/BattlegroupUpdateCharacterTransferSettings',
            method='POST', data=config, timeout=30
        )

    def clear_character_transfer_overrides(self) -> str:
        """Clear character transfer overrides."""
        return self._request(
            '/v0/BattlegroupClearCharacterTransferOverrides',
            method='POST', timeout=30
        )

    # ── ConfigMap management ─────────────────────────────────────────

    def patch_configmap(self, new_ini_content: str) -> bool:
        """Patch the BGD ConfigMap with new director.ini content.

        Args:
            new_ini_content: The full director.ini content to write.

        Returns:
            True if the patch succeeded, False otherwise.
        """
        cm_out, cm_err, cm_rc = self.k8s.run(f'get configmap {self.cm_name} -o json')
        if cm_rc != 0 or not cm_out:
            logger.warning("Could not get ConfigMap: %s", cm_err)
            return False

        cm = json.loads(cm_out)
        cm['data']['director.ini'] = new_ini_content
        cm_json = json.dumps(cm)
        cm_b64 = base64.b64encode(cm_json.encode()).decode()
        patch_cmd = f'echo {cm_b64} | base64 -d | sudo kubectl apply -f - -n {self.namespace}'
        out, err, rc = self.ssh.run(patch_cmd, timeout=15)
        if rc != 0:
            logger.warning("ConfigMap patch failed: %s", err)
            return False
        return True

    def update_ini_section(self, map_name: str, key_values: Dict[str, Any],
                           remove_section: bool = False) -> bool:
        """Read ConfigMap INI, modify a section, write back.

        Args:
            map_name: The INI section name (e.g., map name).
            key_values: Key-value pairs to set in the section.
            remove_section: If True, remove the section instead.

        Returns:
            True if the update succeeded, False otherwise.
        """
        cm_out, cm_err, cm_rc = self.k8s.run(f'get configmap {self.cm_name} -o json')
        if cm_rc != 0 or not cm_out:
            logger.warning("update_ini_section: could not get ConfigMap %s: %s", self.cm_name, cm_err)
            return False

        cm = json.loads(cm_out)
        ini_content = cm['data'].get('director.ini', '')

        cfg = configparser.ConfigParser()
        cfg.read_string(ini_content)

        if remove_section:
            if cfg.has_section(map_name):
                cfg.remove_section(map_name)
        else:
            if not cfg.has_section(map_name):
                cfg.add_section(map_name)
            for key, value in key_values.items():
                if value is not None:
                    cfg.set(map_name, key, str(value))

        buf = io.StringIO()
        cfg.write(buf)
        return self.patch_configmap(buf.getvalue())

    # ── ServerSetScale management ────────────────────────────────────

    def _map_to_scale_name(self, map_name: str) -> str:
        safe = map_name.lower().replace('_', '-')
        return f"{self.resource_prefix}-{safe}"

    def get_server_set_scale(self, map_name: str) -> Optional[Dict]:
        name = self._map_to_scale_name(map_name)
        cm_out, cm_err, cm_rc = self.k8s.run(
            f'get serversetscale {name} -o json')
        if cm_rc != 0 or not cm_out:
            return None
        return json.loads(cm_out)

    def patch_server_set_scale(self, map_name: str, replicas: int,
                                partitions: list) -> bool:
        name = self._map_to_scale_name(map_name)
        patch = json.dumps({
            'spec': {
                'partitions': partitions,
                'replicas': replicas,
            }
        })
        patch_b64 = base64.b64encode(patch.encode()).decode()
        cmd = (f'echo {patch_b64} | base64 -d | '
               f'sudo kubectl patch serversetscale {name} -n {self.namespace} '
               f'--type merge --patch-file /dev/stdin')
        out, err, rc = self.ssh.run(cmd, timeout=15)
        if rc != 0:
            logger.warning("ServerSetScale patch failed for %s: %s", map_name, err)
            return False
        return True

    # ── Helper: extract config values for INI update ─────────────────

    @staticmethod
    def extract_server_config_kv(config: Dict) -> Dict[str, str]:
        """Extract key-value pairs from a director config dict for INI update.

        Handles DimensionServerGroupConfig, ClassicalInstancingGroupConfig,
        and SingleServerConfig formats.
        """
        kv = {}
        cfg_keys = ('DimensionServerGroupConfig', 'ClassicalInstancingGroupConfig')
        for cfg_key in cfg_keys:
            if cfg_key in config:
                dcfg = config[cfg_key]
                if dcfg.get('playerHardCap') is not None:
                    kv['PlayerHardCap'] = dcfg['playerHardCap']
                if dcfg.get('minServers') is not None:
                    kv['MinServers'] = dcfg['minServers']
                if dcfg.get('numExtraServers') is not None:
                    kv['NumExtraServers'] = dcfg['numExtraServers']
                if 'enableAutomaticInstanceScaling' in dcfg:
                    kv['EnableAutomaticInstanceScaling'] = str(dcfg['enableAutomaticInstanceScaling'])
                if dcfg.get('instanceScalingThrottlingSeconds') is not None:
                    kv['InstanceScalingThrottlingSeconds'] = dcfg['instanceScalingThrottlingSeconds']
                break

        if not kv and 'SingleServerConfig' in config:
            scfg = config['SingleServerConfig']
            if scfg.get('playerHardCap') is not None:
                kv['PlayerHardCap'] = scfg['playerHardCap']

        return kv

    @staticmethod
    def extract_character_transfer_kv(config: Dict) -> Dict[str, str]:
        """Extract key-value pairs from character transfer config."""
        kv = {}
        if 'ForceIsWorldClosed' in config:
            kv['ForceIsWorldClosed'] = str(config['ForceIsWorldClosed'])
        if 'ForceIsWorldClosingSoon' in config:
            kv['ForceIsWorldClosingSoon'] = str(config['ForceIsWorldClosingSoon'])
        return kv
