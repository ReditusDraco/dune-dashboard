# BGD Director proxy routes.

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.models import ApiResponse, ErrorDetail

director_bp = Blueprint("director", __name__)
logger = logging.getLogger(__name__)


def _get_service():
    from app.factory import get_services
    return get_services()["bg_director"]


@director_bp.route("/battlegroup", methods=["GET"])
@login_required
def director_battlegroup():
    try:
        svc = _get_service()
        data = svc.get_battlegroup()
        return jsonify(ApiResponse(success=True, data=data.model_dump()).model_dump())
    except Exception as e:
        logger.error("Director battlegroup error: %s", e)
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e), hint="Check BGD pod logs"),
        ).model_dump()), 503


@director_bp.route("/config", methods=["POST"])
@login_required
def director_update_config():
    data = request.get_json() or {}
    try:
        svc = _get_service()
        result = svc.update_server_config(data)
        return jsonify(ApiResponse(success=True, data={"result": result}).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e)),
        ).model_dump()), 503


@director_bp.route("/config/clear", methods=["POST"])
@login_required
def director_clear_config():
    map_name = request.get_data(as_text=True).strip()
    try:
        svc = _get_service()
        result = svc.clear_map_config(map_name)
        return jsonify(ApiResponse(success=True, data={"result": result}).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e)),
        ).model_dump()), 503


@director_bp.route("/transfer", methods=["GET"])
@login_required
def director_transfer_get():
    try:
        svc = _get_service()
        data = svc.get_transfer_rules()
        return jsonify(ApiResponse(success=True, data=data).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e)),
        ).model_dump()), 503


@director_bp.route("/transfer", methods=["POST"])
@login_required
def director_transfer_update():
    data = request.get_json() or {}
    try:
        svc = _get_service()
        result = svc.update_transfer_settings(data)
        return jsonify(ApiResponse(success=True, data={"result": result}).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e)),
        ).model_dump()), 503


@director_bp.route("/transfer/clear", methods=["POST"])
@login_required
def director_transfer_clear():
    try:
        svc = _get_service()
        result = svc.clear_transfer_overrides()
        return jsonify(ApiResponse(success=True, data={"result": result}).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e)),
        ).model_dump()), 503


@director_bp.route("/fls", methods=["GET"])
@login_required
def director_fls_get():
    try:
        svc = _get_service()
        data = svc.get_fls_settings()
        return jsonify(ApiResponse(success=True, data=data).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e)),
        ).model_dump()), 503


@director_bp.route("/fls", methods=["POST"])
@login_required
def director_fls_update():
    data = request.get_json() or {}
    try:
        svc = _get_service()
        result = svc.update_fls_settings(data)
        return jsonify(ApiResponse(success=True, data={"result": result}).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e)),
        ).model_dump()), 503


@director_bp.route("/fls/clear", methods=["POST"])
@login_required
def director_fls_clear():
    try:
        svc = _get_service()
        result = svc.clear_fls_overrides()
        return jsonify(ApiResponse(success=True, data={"result": result}).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="DirectorUnavailable", message=str(e)),
        ).model_dump()), 503
