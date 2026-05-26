# Chat routes.

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.models import ApiResponse, ErrorDetail

chat_bp = Blueprint("chat", __name__)
logger = logging.getLogger(__name__)


@chat_bp.route("/history", methods=["GET"])
@login_required
def chat_history():
    channel = request.args.get("channel", "")
    limit = int(request.args.get("limit", 100))
    from app.factory import get_services
    svc = get_services()["chat"]
    rows = svc.get_history(limit=limit)
    if channel:
        rows = [r for r in rows if r.get("channel", "").lower() == channel.lower()]
    return jsonify(ApiResponse(success=True, data=rows).model_dump())
