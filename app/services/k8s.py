"""Kubernetes service - kubectl operations via SSH"""

import logging

logger = logging.getLogger(__name__)


class K8sService:
    def __init__(self, ssh_service, namespace):
        self.ssh = ssh_service
        self.namespace = namespace

    def run(self, kubectl_command, timeout=30):
        full_cmd = f'sudo kubectl {kubectl_command} -n {self.namespace}'
        logger.debug(f"K8s executing: kubectl {kubectl_command} -n {self.namespace}")
        result = self.ssh.run(full_cmd, timeout=timeout)
        out, err, rc = result
        if rc != 0:
            logger.debug(f"K8s command failed (rc={rc}): {err[:100] if err else 'no error'}")
        else:
            logger.debug(f"K8s command OK, output lines: {len(out.split(chr(10))) if out else 0}")
        return result

    def get_pods(self):
        out, err, rc = self.run('get pods -o name')
        if rc != 0:
            logger.error(f"Failed to get pods: {err}")
            return []
        pods = [line.replace('pod/', '').strip() for line in (out or '').strip().split('\n') if line.strip()]
        logger.debug(f"Found {len(pods)} pods in namespace {self.namespace}")
        return pods

    def find_pod_by_pattern(self, pattern):
        pods = self.get_pods()
        for pod in pods:
            if pattern.lower() in pod.lower():
                return pod
        return None

    def get_text_router_pod(self):
        pod = self.find_pod_by_pattern('tr-deploy')
        if pod:
            return pod
        pod = self.find_pod_by_pattern('text')
        if pod:
            return pod
        pod = self.find_pod_by_pattern('router')
        return pod

    def get_rabbitmq_pod(self):
        pod = self.find_pod_by_pattern('mq-admin')
        if pod:
            return pod
        pod = self.find_pod_by_pattern('mq-game')
        return pod

    def get_deployments(self):
        out, err, rc = self.run('get deployments -o name')
        if rc != 0:
            return []
        return [d.strip() for d in (out or '').strip().split('\n') if d.strip()]

    def get_node_metrics(self):
        out, err, rc = self.run('top nodes')
        if rc == 0 and out.strip():
            lines = out.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    return {
                        'cpu': parts[2],
                        'memory': parts[3],
                        'cpu_pct': parts[1]
                    }
        return {}

    def auto_detect_namespace(self):
        out, err, rc = self.ssh.run('sudo kubectl get namespaces -o name', timeout=10)
        if rc == 0:
            for line in (out or '').strip().split('\n'):
                ns = line.replace('namespace/', '').strip()
                if ns.startswith('funcom-seabass-'):
                    logger.info(f"Auto-detected K8s namespace: {ns}")
                    self.namespace = ns
                    return ns
        return None
