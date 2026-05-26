"""Kubernetes service — kubectl operations via SSH."""

import logging

logger = logging.getLogger(__name__)


class K8sService:
    def __init__(self, ssh_service, namespace):
        self.ssh = ssh_service
        self.namespace = namespace

    def run(self, kubectl_command, timeout=30):
        full_cmd = f"sudo kubectl {kubectl_command} -n {self.namespace}"
        logger.debug("K8s executing: %s", full_cmd)
        result = self.ssh.run(full_cmd, timeout=timeout)
        out, err, rc = result
        if rc != 0:
            logger.debug("K8s command failed (rc=%d): %s", rc, err[:100] if err else "no error")
        else:
            logger.debug("K8s command OK, output lines: %d", len(out.split("\n")) if out else 0)
        return result

    def get_pods(self):
        out, err, rc = self.run("get pods -o json")
        if rc != 0:
            logger.error("Failed to get pods: %s", err)
            return []
        try:
            import json
            data = json.loads(out or "{}")
            items = data.get("items", [])
            pods = []
            for item in items:
                metadata = item.get("metadata", {})
                status = item.get("status", {})
                container_statuses = status.get("containerStatuses", [])
                restarts = sum(c.get("restartCount", 0) for c in container_statuses)
                pods.append({
                    "name": metadata.get("name", ""),
                    "namespace": metadata.get("namespace", self.namespace),
                    "status": status.get("phase", "Unknown"),
                    "restarts": restarts,
                    "age": self._age_from_creation(metadata.get("creationTimestamp")),
                })
            logger.debug("Found %d pods in namespace %s", len(pods), self.namespace)
            return pods
        except Exception as e:
            logger.error("Failed to parse pods: %s", e)
            return []

    def find_pod_by_pattern(self, pattern):
        pods = self.get_pods()
        for pod in pods:
            if pattern.lower() in pod.lower():
                return pod
        return None

    def get_text_router_pod(self):
        pod = self.find_pod_by_pattern("tr-deploy")
        if pod:
            return pod
        pod = self.find_pod_by_pattern("text")
        if pod:
            return pod
        return self.find_pod_by_pattern("router")

    def get_rabbitmq_pod(self, admin=True):
        if admin:
            return self.find_pod_by_pattern("mq-admin")
        return self.find_pod_by_pattern("mq-game")

    def get_filebrowser_pod(self):
        return self.find_pod_by_pattern("fb-deploy")

    def get_deployments(self):
        out, err, rc = self.run("get deployments -o json")
        if rc != 0:
            return []
        try:
            import json
            data = json.loads(out or "{}")
            items = data.get("items", [])
            deployments = []
            for item in items:
                metadata = item.get("metadata", {})
                spec = item.get("spec", {})
                status = item.get("status", {})
                deployments.append({
                    "name": metadata.get("name", ""),
                    "namespace": metadata.get("namespace", self.namespace),
                    "replicas": spec.get("replicas", 0),
                    "available": status.get("availableReplicas", 0),
                })
            return deployments
        except Exception as e:
            logger.error("Failed to parse deployments: %s", e)
            return []

    def get_node_metrics(self):
        out, err, rc = self.run("top nodes")
        if rc == 0 and out.strip():
            lines = out.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    return {
                        "cpu": parts[2],
                        "memory": parts[3],
                        "cpu_pct": parts[1],
                    }
        return {}

    @staticmethod
    def _age_from_creation(timestamp: str | None) -> str:
        if not timestamp:
            return "Unknown"
        from datetime import datetime, timezone
        try:
            created = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - created
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            if days > 0:
                return f"{days}d"
            if hours > 0:
                return f"{hours}h"
            return f"{minutes}m"
        except Exception:
            return "Unknown"

    def auto_detect_namespace(self):
        out, err, rc = self.ssh.run("sudo kubectl get namespaces -o name", timeout=10)
        if rc == 0:
            for line in (out or "").strip().split("\n"):
                ns = line.replace("namespace/", "").strip()
                if ns.startswith("funcom-seabass-"):
                    logger.info("Auto-detected K8s namespace: %s", ns)
                    self.namespace = ns
                    return ns
        return None
