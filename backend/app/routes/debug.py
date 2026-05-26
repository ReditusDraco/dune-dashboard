# Debug routes — restricted to admin.

import logging

from flask import Blueprint, jsonify
from flask_login import login_required

from app.models import ApiResponse, ErrorDetail

debug_bp = Blueprint("debug", __name__)
logger = logging.getLogger(__name__)


def _get_services():
    from app.factory import get_services
    return get_services()


@debug_bp.route("/tables", methods=["GET"])
@login_required
def list_tables():
    db = _get_services()["db"]
    rows = db.execute_readonly(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'dune' ORDER BY table_name"
    )
    return jsonify(ApiResponse(success=True, data={"tables": [r["table_name"] for r in rows]}).model_dump())


@debug_bp.route("/vehicle/<int:vehicle_id>", methods=["GET"])
@login_required
def debug_vehicle(vehicle_id):
    db = _get_services()["db"]
    vehicle = db.execute_readonly(
        """SELECT a.id, a.class, a.properties
           FROM dune.actors a JOIN dune.vehicles v ON a.id = v.id WHERE a.id = %s""",
        [vehicle_id],
    )
    if not vehicle:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="NotFound", message="Vehicle not found"),
        ).model_dump()), 404
    return jsonify(ApiResponse(success=True, data=vehicle[0]).model_dump())
