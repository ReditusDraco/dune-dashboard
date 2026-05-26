# Server and infrastructure routes.

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.models import ApiResponse, ErrorDetail

server_bp = Blueprint("server", __name__)
logger = logging.getLogger(__name__)


def _get_services():
    from app.factory import get_services
    return get_services()


@server_bp.route("/pods", methods=["GET"])
@login_required
def server_pods():
    services = _get_services()
    pods = services["k8s"].get_pods()
    return jsonify(ApiResponse(success=True, data=pods).model_dump())


@server_bp.route("/deployments", methods=["GET"])
@login_required
def server_deployments():
    services = _get_services()
    deployments = services["k8s"].get_deployments()
    return jsonify(ApiResponse(success=True, data=deployments).model_dump())


@server_bp.route("/metrics", methods=["GET"])
@login_required
def server_metrics():
    services = _get_services()
    raw = services["k8s"].get_node_metrics()
    from datetime import datetime, timezone
    metrics = []
    if raw:
        cpu_str = raw.get("cpu", "0m").replace("m", "").replace("%", "")
        mem_str = raw.get("memory", "0Mi").replace("Mi", "").replace("Gi", "000")
        try:
            cpu_val = float(cpu_str)
            mem_val = float(mem_str)
            metrics.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cpu_percent": min(100, round(cpu_val / 10, 1)),  # rough estimate
                "memory_percent": min(100, round(mem_val / 100, 1)),  # rough estimate
            })
        except ValueError:
            pass
    return jsonify(ApiResponse(success=True, data=metrics).model_dump())


@server_bp.route("/deployments/<name>/restart", methods=["POST"])
@login_required
def restart_deployment(name: str):
    services = _get_services()
    out, err, rc = services["k8s"].run(f"rollout restart deployment/{name}")
    return jsonify(ApiResponse(
        success=rc == 0,
        data={"output": out, "error": err, "rc": rc},
    ).model_dump())


@server_bp.route("/deployments/<name>/scale", methods=["POST"])
@login_required
def scale_deployment(name: str):
    data = request.get_json() or {}
    replicas = data.get("replicas")
    if replicas is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing replicas"),
        ).model_dump()), 400
    services = _get_services()
    out, err, rc = services["k8s"].run(f"scale deployment/{name} --replicas={replicas}")
    return jsonify(ApiResponse(
        success=rc == 0,
        data={"output": out, "error": err, "rc": rc},
    ).model_dump())


@server_bp.route("/action", methods=["POST"])
@login_required
def server_action():
    data = request.get_json() or {}
    deployment = data.get("deployment", "")
    action = data.get("action", "")
    if not deployment or not action:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing deployment or action"),
        ).model_dump()), 400

    actions = {
        "restart": f"rollout restart deployment/{deployment}",
        "status": f"rollout status deployment/{deployment}",
        "scale_0": f"scale deployment/{deployment} --replicas=0",
        "scale_1": f"scale deployment/{deployment} --replicas=1",
        "describe": f"describe deployment/{deployment}",
    }
    cmd = actions.get(action)
    if not cmd:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message=f"Unknown action: {action}"),
        ).model_dump()), 400

    services = _get_services()
    out, err, rc = services["k8s"].run(cmd)
    return jsonify(ApiResponse(
        success=rc == 0,
        data={"output": out, "error": err, "rc": rc},
    ).model_dump())


@server_bp.route("/firewall", methods=["GET"])
@server_bp.route("/firewall/status", methods=["GET"])
@login_required
def firewall_status():
    services = _get_services()
    ssh = services["ssh"]
    out, _, _ = ssh.run(
        "sudo iptables -L INPUT -n 2>/dev/null | grep -E 'dpt:(18888|32479)'; "
        "sudo iptables -L FORWARD -n 2>/dev/null | grep -E 'dpt:(18888|32479)'; "
        "sudo iptables -t mangle -L PREROUTING -n 2>/dev/null | grep -E 'dpt:(18888|32479)'",
        timeout=15,
    )
    blocked_ports = set()
    for line in out.split("\n"):
        for port in ("18888", "32479"):
            if f"dpt:{port}" in line and "DROP" in line:
                blocked_ports.add(port)
    return jsonify(ApiResponse(
        success=True,
        data={
            "18888_blocked": "18888" in blocked_ports,
            "32479_blocked": "32479" in blocked_ports,
        },
    ).model_dump())


@server_bp.route("/firewall/toggle", methods=["POST"])
@login_required
def firewall_toggle():
    data = request.get_json() or {}
    port = data.get("port")
    block = data.get("block", True)
    if not port:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing port"),
        ).model_dump()), 400
    services = _get_services()
    ssh = services["ssh"]
    if block:
        cmd = (
            f"sudo iptables -I INPUT 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && "
            f"sudo iptables -I INPUT 2 -p tcp --dport {port} -j DROP && "
            f"sudo iptables -I FORWARD 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && "
            f"sudo iptables -I FORWARD 2 -p tcp --dport {port} -j DROP && "
            f"sudo iptables -t mangle -I PREROUTING 1 -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT && "
            f"sudo iptables -t mangle -I PREROUTING 2 -p tcp --dport {port} -j DROP"
        )
    else:
        cmd = (
            f"sudo iptables -D INPUT -p tcp --dport {port} -j DROP 2>/dev/null; "
            f"sudo iptables -D INPUT -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT 2>/dev/null; "
            f"sudo iptables -D FORWARD -p tcp --dport {port} -j DROP 2>/dev/null; "
            f"sudo iptables -D FORWARD -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT 2>/dev/null; "
            f"sudo iptables -t mangle -D PREROUTING -p tcp --dport {port} -j DROP 2>/dev/null; "
            f"sudo iptables -t mangle -D PREROUTING -p tcp --dport {port} -s 127.0.0.1 -j ACCEPT 2>/dev/null; "
            f"echo DONE"
        )
    out, err, rc = ssh.run(cmd, timeout=20)
    success = rc == 0 or "DONE" in out
    return jsonify(ApiResponse(
        success=success,
        data={"output": out, "error": err},
    ).model_dump())


@server_bp.route("/rmq/queues", methods=["GET"])
@login_required
def rmq_queues():
    services = _get_services()
    try:
        queues = services["rmq_admin"].get_queue_depths()
        return jsonify(ApiResponse(
            success=True,
            data=[q.model_dump() for q in queues],
        ).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="RmqError", message=str(e)),
        ).model_dump()), 503


@server_bp.route("/rmq/overview", methods=["GET"])
@login_required
def rmq_overview():
    services = _get_services()
    try:
        overview = services["rmq_admin"].get_overview()
        return jsonify(ApiResponse(
            success=True,
            data=overview.model_dump(),
        ).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="RmqError", message=str(e)),
        ).model_dump()), 503
