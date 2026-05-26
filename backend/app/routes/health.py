# Health and SSE routes.

import asyncio
import json
import logging

from flask import Blueprint, jsonify, Response, request, stream_with_context
from flask_login import login_required, current_user

from app.models import ApiResponse, ErrorDetail

health_bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    from app.factory import get_services
    services = get_services()
    health = {"status": "healthy", "timestamp": __import__("datetime").datetime.now().isoformat(), "checks": {}}
    status_code = 200

    try:
        services["db"].health_check()
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {e}"
        health["status"] = "degraded"
        status_code = 503

    try:
        services["ssh"].check_connection()
        health["checks"]["ssh"] = "ok"
    except Exception as e:
        health["checks"]["ssh"] = f"error: {e}"
        health["status"] = "degraded"
        status_code = 503

    try:
        services["bg_director"].get_battlegroup()
        health["checks"]["bgd"] = "ok"
    except Exception as e:
        health["checks"]["bgd"] = f"error: {e}"
        health["status"] = "degraded"
        status_code = 503

    try:
        services["rmq_admin"].get_overview()
        health["checks"]["rmq"] = "ok"
    except Exception as e:
        health["checks"]["rmq"] = f"error: {e}"
        health["status"] = "degraded"
        status_code = 503

    return jsonify(health), status_code


@health_bp.route("/events/stream", methods=["GET"])
@login_required
def sse_stream():
    from app.factory import get_services
    services = get_services()
    realtime = services["realtime"]

    queue = asyncio.Queue(maxsize=100)
    realtime.add_client(queue)

    def event_stream():
        try:
            yield "event: connected\ndata: {}\n\n"
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            while True:
                try:
                    msg = loop.run_until_complete(asyncio.wait_for(queue.get(), timeout=30))
                    yield msg
                except asyncio.TimeoutError:
                    yield ":ping\n\n"
                except Exception:
                    break
        finally:
            realtime.remove_client(queue)

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")
