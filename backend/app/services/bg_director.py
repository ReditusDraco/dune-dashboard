"""Battlegroup Director HTTP API client."""

import json
import logging
from typing import Any, Dict

import httpx

from app.models import BattlegroupState, ErrorDetail

logger = logging.getLogger(__name__)


class BgDirectorService:
    def __init__(self, host: str, node_port: int):
        self.base_url = f"http://{host}:{node_port}"
        self.client = httpx.Client(base_url=self.base_url, timeout=15)
        logger.debug("BgDirectorService initialized: %s", self.base_url)

    def _request(self, method: str, path: str, data: Any = None, timeout: int = 15) -> dict | str:
        try:
            if method == "GET":
                resp = self.client.get(path, timeout=timeout)
            else:
                if isinstance(data, str):
                    resp = self.client.request(method, path, content=data, headers={"Content-Type": "application/json"}, timeout=timeout)
                else:
                    resp = self.client.request(method, path, json=data, timeout=timeout)
            resp.raise_for_status()
            if resp.headers.get("content-type", "").startswith("application/json"):
                return resp.json()
            return resp.text
        except httpx.HTTPStatusError as e:
            logger.error("BGD HTTP error %s %s: %s", method, path, e)
            raise DirectorUnavailableError(f"BGD returned {e.response.status_code}")
        except httpx.ConnectError as e:
            logger.error("BGD connection error %s %s: %s", method, path, e)
            raise DirectorUnavailableError("The Battlegroup Director is not responding. Check BGD pod logs.")
        except Exception as e:
            logger.error("BGD request error %s %s: %s", method, path, e)
            raise DirectorUnavailableError(str(e))

    # ── Player Endpoints ──────────────────────────────────────────

    def get_battlegroup(self) -> BattlegroupState:
        data = self._request("GET", "/v0/battlegroup", timeout=15)
        if isinstance(data, str):
            data = json.loads(data)
        return _parse_battlegroup(data)

    def get_all_players(self) -> list[str]:
        data = self._request("GET", "/v0/players")
        return data if isinstance(data, list) else []

    def get_online_players(self) -> list[str]:
        data = self._request("GET", "/v0/players/online")
        return data if isinstance(data, list) else []

    def get_intransit_players(self) -> list[str]:
        data = self._request("GET", "/v0/players/intransit")
        return data if isinstance(data, list) else []

    def get_graceperiod_players(self) -> list[str]:
        data = self._request("GET", "/v0/players/graceperiod")
        return data if isinstance(data, list) else []

    def get_completion_players(self) -> list[str]:
        data = self._request("GET", "/v0/players/completion")
        return data if isinstance(data, list) else []

    def get_queued_players(self) -> list[str]:
        data = self._request("GET", "/v0/players/queued")
        return data if isinstance(data, list) else []

    # ── FLS Settings ───────────────────────────────────────────────

    def get_fls_settings(self) -> dict:
        return self._request("GET", "/v0/BattlegroupFetchFlsReportSettings")

    def update_fls_settings(self, settings: dict) -> str:
        return self._request("POST", "/v0/BattlegroupUpdateFlsReportSettings", data=settings, timeout=30)

    def clear_fls_overrides(self) -> str:
        return self._request("POST", "/v0/BattlegroupClearFlsReportOverrides", timeout=30)

    # ── Server Config ──────────────────────────────────────────────

    def update_server_config(self, config: dict) -> str:
        return self._request("POST", "/v0/BattlegroupUpdateServerGroupConfig", data=config, timeout=30)

    def clear_map_config(self, map_name: str) -> str:
        return self._request("POST", "/v0/BattlegroupClearMapConfigOverrides", data=map_name, timeout=30)

    # ── Character Transfer ──────────────────────────────────────────

    def get_transfer_rules(self) -> dict:
        return self._request("GET", "/v0/BattlegroupFetchCharacterTransferRules")

    def update_transfer_settings(self, config: dict) -> str:
        return self._request("POST", "/v0/BattlegroupUpdateCharacterTransferSettings", data=config, timeout=30)

    def clear_transfer_overrides(self) -> str:
        return self._request("POST", "/v0/BattlegroupClearCharacterTransferOverrides", timeout=30)

    def close(self):
        self.client.close()


class DirectorUnavailableError(Exception):
    pass


def _parse_battlegroup(data: dict) -> BattlegroupState:
    """Parse raw BGD JSON into BattlegroupState model."""
    state = BattlegroupState()

    for key in ["dimensionMaps", "singleServerMaps", "instancedMaps"]:
        if key in data:
            target = "dimension_maps" if key == "dimensionMaps" else "single_server_maps" if key == "singleServerMaps" else "instanced_maps"
            for mg in data[key]:
                group = {"name": mg.get("name", ""), "servers": []}
                for sv in mg.get("servers", []):
                    sst = sv.get("lastServerState", {})
                    sgs = sst.get("serverGameplaySettings", {})
                    server = {
                        "partition": sv.get("partition", ""),
                        "ip": sv.get("ip", ""),
                        "game_port": sv.get("gamePort", 7777),
                        "num_players": sv.get("numPlayers", 0),
                        "status": sv.get("status", "unknown"),
                        "hydration": sgs.get("hydration", 1.0),
                        "sandstorm": sgs.get("sandstorm", False),
                        "sandworm": sgs.get("sandworm", True),
                        "pvp_enabled": sgs.get("pvpEnabled", False),
                        "mining_multiplier": sgs.get("miningMultiplier", 1.0),
                        "durability": sgs.get("durability", 1.0),
                    }
                    group["servers"].append(server)
                getattr(state, target).append(group)

    return state
