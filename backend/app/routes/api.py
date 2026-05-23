# Main API routes — players, guilds, economy, world, progression, character, admin.

import logging

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from pydantic import ValidationError

from app.models import (
    ApiResponse, ErrorDetail, PlayerDetail, BroadcastRequest,
    TeleportRequest, FunctionExecuteRequest, RawQueryRequest,
)

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


def _audit(action: str, details: dict | None = None, target_player_id: int | None = None, severity: str = "info"):
    from app.factory import get_services
    services = get_services()
    audit = services.get("audit")
    if audit:
        audit.log(
            action=action,
            user=current_user.id if current_user.is_authenticated else "anonymous",
            details=details,
            target_player_id=target_player_id,
            severity=severity,
            source_ip=request.remote_addr,
        )


@api_bp.errorhandler(ValidationError)
def handle_validation_error(e):
    return jsonify(ApiResponse(
        success=False,
        error=ErrorDetail(code="ValidationError", message=str(e)),
    ).model_dump()), 400


# ── Player Endpoints ──────────────────────────────────────────────

@api_bp.route("/players", methods=["GET"])
@login_required
def list_players():
    term = request.args.get("q", "")
    limit = int(request.args.get("limit", 50))
    from app.factory import get_services
    svc = get_services()["player"]
    results = svc.search(term, limit=limit)
    return jsonify(ApiResponse(success=True, data=[r.model_dump() for r in results]).model_dump())


@api_bp.route("/players/search", methods=["POST"])
@login_required
def search_players():
    data = request.get_json() or {}
    term = data.get("term", "")
    from app.factory import get_services
    svc = get_services()["player"]
    results = svc.search(term)
    return jsonify(ApiResponse(success=True, data=[r.model_dump() for r in results]).model_dump())


@api_bp.route("/players/<int:account_id>", methods=["GET"])
@login_required
def get_player(account_id):
    from app.factory import get_services
    svc = get_services()["player"]
    detail = svc.get_detail(account_id)
    if not detail:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="NotFound", message="Player not found"),
        ).model_dump()), 404
    return jsonify(ApiResponse(success=True, data=detail.model_dump()).model_dump())


@api_bp.route("/players/<int:account_id>/inventory", methods=["GET"])
@login_required
def get_player_inventory(account_id):
    from app.factory import get_services
    svc = get_services()["economy"]
    inventories = svc.get_inventory(account_id)
    return jsonify(ApiResponse(success=True, data=[inv.model_dump() for inv in inventories]).model_dump())


@api_bp.route("/players/<int:account_id>/currency", methods=["GET"])
@login_required
def get_player_currency(account_id):
    from app.factory import get_services
    player_svc = get_services()["player"]
    detail = player_svc.get_detail(account_id)
    if not detail or not detail.player_controller_id:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="NotFound", message="Player controller not found"),
        ).model_dump()), 404
    econ = get_services()["economy"]
    currency = econ.get_currency(detail.player_controller_id)
    return jsonify(ApiResponse(success=True, data=[c.model_dump() for c in currency]).model_dump())


@api_bp.route("/players/<int:account_id>/vitals", methods=["GET"])
@login_required
def get_player_vitals(account_id):
    from app.factory import get_services
    player_svc = get_services()["player"]
    detail = player_svc.get_detail(account_id)
    if not detail or not detail.player_pawn_id:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="NotFound", message="Player pawn not found"),
        ).model_dump()), 404
    econ = get_services()["economy"]
    vitals = econ.get_vitals(detail.player_pawn_id)
    return jsonify(ApiResponse(success=True, data=vitals.model_dump()).model_dump())


# ── Economy Mutations ────────────────────────────────────────────

@api_bp.route("/items/add", methods=["POST"])
@login_required
def add_item():
    data = request.get_json() or {}
    inventory_id = data.get("inventory_id")
    template_id = data.get("template_id")
    stack_size = data.get("stack_size", 1)
    quality_level = data.get("quality_level", 0)
    if not inventory_id or not template_id:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing inventory_id or template_id"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["economy"]
    item_id = svc.add_item(inventory_id, template_id, stack_size, quality_level)
    _audit("item_add", {"inventory_id": inventory_id, "template_id": template_id, "item_id": item_id})
    return jsonify(ApiResponse(success=True, data={"item_id": item_id}).model_dump())


@api_bp.route("/items/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):
    from app.factory import get_services
    svc = get_services()["economy"]
    svc.delete_item(item_id)
    _audit("item_delete", {"item_id": item_id})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/items/<int:item_id>", methods=["PATCH"])
@login_required
def edit_item(item_id):
    data = request.get_json() or {}
    field = data.get("field")
    value = data.get("value")
    if not field or value is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing field or value"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["economy"]
    svc.edit_item_field(item_id, field, value)
    _audit("item_edit", {"item_id": item_id, "field": field, "value": value})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/currency/adjust", methods=["POST"])
@login_required
def adjust_currency():
    data = request.get_json() or {}
    controller_id = data.get("controller_id")
    currency_id = data.get("currency_id")
    delta = data.get("delta")
    if controller_id is None or currency_id is None or delta is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing required parameters"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["economy"]
    new_balance = svc.adjust_currency(controller_id, currency_id, delta)
    _audit("currency_adjust", {"controller_id": controller_id, "currency_id": currency_id, "delta": delta, "new_balance": new_balance}, target_player_id=controller_id)
    return jsonify(ApiResponse(success=True, data={"new_balance": new_balance}).model_dump())


@api_bp.route("/currency/set", methods=["POST"])
@login_required
def set_currency():
    data = request.get_json() or {}
    controller_id = data.get("controller_id")
    currency_id = data.get("currency_id")
    balance = data.get("balance")
    if controller_id is None or currency_id is None or balance is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing required parameters"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["economy"]
    svc.set_currency(controller_id, currency_id, balance)
    _audit("currency_set", {"controller_id": controller_id, "currency_id": currency_id, "balance": balance}, target_player_id=controller_id)
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/vitals/set", methods=["POST"])
@login_required
def set_vitals():
    data = request.get_json() or {}
    pawn_id = data.get("pawn_id")
    health = data.get("health")
    max_health = data.get("max_health")
    hydration = data.get("hydration")
    spice = data.get("spice")
    if pawn_id is None or hydration is None or spice is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing required parameters"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["economy"]
    svc.set_vitals(pawn_id, health, max_health, hydration, spice)
    _audit("vitals_edit", {"pawn_id": pawn_id, "health": health, "max_health": max_health, "hydration": hydration, "spice": spice})
    return jsonify(ApiResponse(success=True).model_dump())


# ── Guild Endpoints ──────────────────────────────────────────────

@api_bp.route("/guilds", methods=["GET"])
@login_required
def list_guilds():
    term = request.args.get("q", "")
    limit = int(request.args.get("limit", 50))
    from app.factory import get_services
    svc = get_services()["guild"]
    guilds = svc.list_all()
    if term:
        guilds = [g for g in guilds if term.lower() in g.guild_name.lower()]
    return jsonify(ApiResponse(success=True, data=[g.model_dump() for g in guilds[:limit]]).model_dump())


@api_bp.route("/guilds/<int:guild_id>", methods=["GET"])
@login_required
def get_guild(guild_id):
    from app.factory import get_services
    svc = get_services()["guild"]
    guild = svc.get_detail(guild_id)
    if not guild:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="NotFound", message="Guild not found"),
        ).model_dump()), 404
    return jsonify(ApiResponse(success=True, data=guild.model_dump()).model_dump())


@api_bp.route("/guilds/<int:guild_id>", methods=["DELETE"])
@login_required
def disband_guild(guild_id):
    from app.factory import get_services
    svc = get_services()["guild"]
    svc.disband(guild_id)
    _audit("guild_disband", {"guild_id": guild_id})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/guilds/<int:guild_id>/members/<int:player_id>", methods=["DELETE"])
@login_required
def remove_guild_member(guild_id, player_id):
    from app.factory import get_services
    svc = get_services()["guild"]
    svc.remove_member(guild_id, player_id)
    _audit("guild_kick", {"guild_id": guild_id, "player_id": player_id})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/guilds/<int:guild_id>/members/<int:player_id>/role", methods=["PUT"])
@login_required
def set_guild_role(guild_id, player_id):
    data = request.get_json() or {}
    role_id = data.get("role_id")
    action = data.get("action", "promote")
    if role_id is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing role_id"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["guild"]
    if action == "promote":
        svc.promote(guild_id, player_id, role_id)
    else:
        svc.demote(guild_id, player_id, role_id)
    _audit(f"guild_{action}", {"guild_id": guild_id, "player_id": player_id, "role_id": role_id})
    return jsonify(ApiResponse(success=True).model_dump())


# ── World Endpoints ──────────────────────────────────────────────

@api_bp.route("/partitions", methods=["GET"])
@login_required
def list_partitions():
    map_name = request.args.get("map", "")
    from app.factory import get_services
    svc = get_services()["world"]
    partitions = svc.get_partitions(map_name)
    return jsonify(ApiResponse(success=True, data=[p.model_dump() for p in partitions]).model_dump())


@api_bp.route("/teleport", methods=["POST"])
@login_required
def teleport():
    data = request.get_json() or {}
    try:
        req = TeleportRequest(**data)
    except ValidationError as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message=str(e)),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["world"]
    svc.teleport(req.fls_id, req.partition_id, req.x, req.y, req.z)
    _audit("player_teleport", {"fls_id": req.fls_id, "partition_id": req.partition_id, "coords": [req.x, req.y, req.z]})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/spice/reset", methods=["POST"])
@login_required
def reset_spice():
    data = request.get_json() or {}
    map_name = data.get("map_name")
    dimension_index = data.get("dimension_index", 0)
    if not map_name:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing map_name"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["world"]
    svc.reset_spice(map_name, dimension_index)
    _audit("spice_reset", {"map": map_name, "dimension": dimension_index})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/spice/spawn", methods=["POST"])
@login_required
def force_spice_spawn():
    data = request.get_json() or {}
    server_id = data.get("server_id")
    spicefield_type_id = data.get("spicefield_type_id")
    if not server_id or spicefield_type_id is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing required parameters"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["world"]
    svc.force_spice_spawn(server_id, spicefield_type_id)
    _audit("spice_spawn", {"server_id": server_id, "spicefield_type_id": spicefield_type_id})
    return jsonify(ApiResponse(success=True).model_dump())


# ── Progression Endpoints ────────────────────────────────────────

@api_bp.route("/progression/journey", methods=["POST"])
@login_required
def journey_action():
    data = request.get_json() or {}
    player_id = data.get("player_id")
    node_ids = data.get("node_ids", [])
    action = data.get("action", "complete")
    if not player_id or not node_ids:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing player_id or node_ids"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["progression"]
    if action == "complete":
        svc.complete_nodes(player_id, node_ids)
    elif action == "reveal":
        svc.reveal_nodes(player_id, node_ids)
    elif action == "reset":
        svc.reset_nodes(player_id, node_ids)
    else:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Invalid action"),
        ).model_dump()), 400
    _audit(f"journey_{action}", {"player_id": player_id, "node_ids": node_ids})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/progression/specialization", methods=["POST"])
@login_required
def set_specialization():
    data = request.get_json() or {}
    player_id = data.get("player_id")
    track_type = data.get("track_type")
    xp = data.get("xp")
    level = data.get("level")
    if player_id is None or not track_type or xp is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing required parameters"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["progression"]
    svc.set_specialization(player_id, track_type, xp, level or 0)
    _audit("specialization_set", {"player_id": player_id, "track": track_type, "xp": xp, "level": level})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/progression/specialization/reset", methods=["POST"])
@login_required
def reset_specializations():
    data = request.get_json() or {}
    player_id = data.get("player_id")
    if player_id is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing player_id"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["progression"]
    svc.reset_specializations(player_id)
    _audit("specialization_reset", {"player_id": player_id})
    return jsonify(ApiResponse(success=True).model_dump())


# ── Character Management Endpoints ──────────────────────────────

@api_bp.route("/characters/<int:account_id>/name", methods=["PUT"])
@login_required
def rename_character(account_id):
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing name"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["character"]
    svc.rename(account_id, name)
    _audit("character_rename", {"account_id": account_id, "new_name": name})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/characters/<int:actor_id>", methods=["DELETE"])
@login_required
def delete_character(actor_id):
    from app.factory import get_services
    svc = get_services()["character"]
    svc.delete_character(actor_id)
    _audit("character_delete", {"actor_id": actor_id})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/accounts/<user_id>", methods=["DELETE"])
@login_required
def delete_account(user_id):
    data = request.get_json() or {}
    reason = data.get("reason", "admin")
    from app.factory import get_services
    svc = get_services()["character"]
    svc.delete_account(user_id, reason)
    _audit("account_delete", {"user_id": user_id, "reason": reason})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/accounts/<user_id>/demo", methods=["PUT"])
@login_required
def set_demo_state(user_id):
    data = request.get_json() or {}
    state = data.get("demo")
    if state is None:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing demo"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["character"]
    svc.set_demo(user_id, state)
    _audit("demo_set", {"user_id": user_id, "state": state})
    return jsonify(ApiResponse(success=True).model_dump())


# ── Vehicles ────────────────────────────────────────────────────

@api_bp.route("/vehicles", methods=["GET"])
@login_required
def list_vehicles():
    from app.factory import get_services
    db = get_services()["db"]
    term = request.args.get("q", "")
    limit = int(request.args.get("limit", 100))
    rows = db.execute_readonly(
        """SELECT a.id, a.class, a.map, c.character_name as owner_name
           FROM dune.actors a
           JOIN dune.vehicle_instances vi ON a.id = vi.actor_id
           LEFT JOIN public.characters c ON vi.owner_id = c.id
           WHERE a.class ILIKE %s OR c.character_name ILIKE %s
           ORDER BY a.id DESC LIMIT %s""",
        [f"%{term}%", f"%{term}%", limit],
    )
    vehicles = [{
        "id": r["id"],
        "class_name": r["class"],
        "display_name": (r["class"] or "").split("/")[-1].replace("_C", "").replace("BP_", "").replace("_", " "),
        "map": r["map"],
        "owner_name": r["owner_name"] or "Unknown",
    } for r in rows]
    return jsonify(ApiResponse(success=True, data=vehicles).model_dump())


@api_bp.route("/vehicles/<int:vehicle_id>/<action>", methods=["POST"])
@login_required
def vehicle_action(vehicle_id, action):
    from app.factory import get_services
    db = get_services()["db"]
    if action == "repair":
        db.call_procedure("repair_vehicle", [vehicle_id])
        _audit("vehicle_repair", {"vehicle_id": vehicle_id})
    elif action == "destroy":
        db.call_procedure("destroy_vehicle", [vehicle_id])
        _audit("vehicle_destroy", {"vehicle_id": vehicle_id})
    else:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message=f"Unknown action: {action}"),
        ).model_dump()), 400
    return jsonify(ApiResponse(success=True).model_dump())


# ── Buildings ───────────────────────────────────────────────────

@api_bp.route("/buildings", methods=["GET"])
@login_required
def list_buildings():
    from app.factory import get_services
    db = get_services()["db"]
    term = request.args.get("q", "")
    limit = int(request.args.get("limit", 100))
    rows = db.execute_readonly(
        """SELECT a.id, a.class, a.map, a.properties->>'m_bIsPowered' as is_powered,
                  a.properties->>'m_PowerLevel' as power_level,
                  c.character_name as owner_name
           FROM dune.actors a
           JOIN dune.buildings b ON a.id = b.id
           LEFT JOIN public.characters c ON b.owner_id = c.id
           WHERE a.class ILIKE %s OR c.character_name ILIKE %s
           ORDER BY a.id DESC LIMIT %s""",
        [f"%{term}%", f"%{term}%", limit],
    )
    buildings = [{
        "id": r["id"],
        "class_name": r["class"],
        "map": r["map"],
        "owner_name": r["owner_name"] or "Unknown",
        "is_powered": r.get("is_powered") == "True",
        "power_level": r.get("power_level"),
        "instance_count": 1,
    } for r in rows]
    return jsonify(ApiResponse(success=True, data=buildings).model_dump())


# ── Accounts ────────────────────────────────────────────────────

@api_bp.route("/accounts", methods=["GET"])
@login_required
def list_accounts():
    from app.factory import get_services
    db = get_services()["db"]
    term = request.args.get("q", "")
    limit = int(request.args.get("limit", 100))
    rows = db.execute_readonly(
        """SELECT a.id, a.email, a.funcom_id,
                  (SELECT COUNT(*) FROM public.characters c WHERE c.account_id = a.id) as character_count,
                  a.is_demo, a.is_cheater, a.last_login
           FROM public.accounts a
           WHERE a.email ILIKE %s OR a.funcom_id ILIKE %s
           ORDER BY a.last_login DESC NULLS LAST LIMIT %s""",
        [f"%{term}%", f"%{term}%", limit],
    )
    accounts = [{
        "id": r["id"],
        "email": r["email"],
        "funcom_id": r["funcom_id"],
        "character_count": r["character_count"],
        "is_demo": r["is_demo"],
        "is_cheater": r["is_cheater"],
        "last_login": r["last_login"].isoformat() if r["last_login"] else None,
    } for r in rows]
    return jsonify(ApiResponse(success=True, data=accounts).model_dump())


@api_bp.route("/players/<int:account_id>/cheater", methods=["POST"])
@login_required
def flag_cheater(account_id):
    data = request.get_json() or {}
    cheat_type = data.get("cheat_type")
    if not cheat_type:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing cheat_type"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["character"]
    svc.flag_cheater(account_id, cheat_type)
    _audit("cheater_flag", {"account_id": account_id, "cheat_type": cheat_type})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/players/<int:account_id>/tags", methods=["GET"])
@login_required
def get_player_tags(account_id):
    from app.factory import get_services
    svc = get_services()["character"]
    tags = svc.get_tags(account_id)
    return jsonify(ApiResponse(success=True, data={"tags": tags}).model_dump())


@api_bp.route("/players/<int:account_id>/tags", methods=["PUT"])
@login_required
def update_player_tags(account_id):
    data = request.get_json() or {}
    add = data.get("add", [])
    remove = data.get("remove", [])
    from app.factory import get_services
    svc = get_services()["character"]
    svc.update_tags(account_id, add, remove)
    _audit("tags_update", {"account_id": account_id, "add": add, "remove": remove})
    return jsonify(ApiResponse(success=True).model_dump())


# ── Broadcast ───────────────────────────────────────────────────

@api_bp.route("/broadcast", methods=["POST"])
@login_required
def send_broadcast():
    data = request.get_json() or {}
    try:
        req = BroadcastRequest(**data)
    except ValidationError as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message=str(e)),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["rmq_game"]
    success = svc.send_broadcast(req.message, server=req.server, partition=req.partition)
    if success:
        _audit("broadcast_sent", {"message": req.message, "server": req.server, "partition": req.partition})
        return jsonify(ApiResponse(success=True).model_dump())
    return jsonify(ApiResponse(
        success=False,
        error=ErrorDetail(code="BroadcastFailed", message="Failed to send broadcast via RMQ"),
    ).model_dump()), 502


# ── Vendor / Economy ────────────────────────────────────────────

@api_bp.route("/vendors/clean", methods=["POST"])
@login_required
def clean_vendor_stock():
    data = request.get_json() or {}
    player_id = data.get("player_id")
    if not player_id:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing player_id"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["economy"]
    svc.clean_vendor_stock(player_id)
    _audit("vendor_clean", {"player_id": player_id})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/tax/invoices", methods=["POST"])
@login_required
def get_tax_invoices():
    data = request.get_json() or {}
    player_id = data.get("player_id")
    if not player_id:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing player_id"),
        ).model_dump()), 400
    from app.factory import get_services
    svc = get_services()["economy"]
    invoices = svc.get_tax_invoices(player_id)
    return jsonify(ApiResponse(success=True, data=invoices).model_dump())


# ── Function Explorer ────────────────────────────────────────────

@api_bp.route("/functions", methods=["GET"])
@login_required
def list_functions():
    from app.factory import get_services
    db = get_services()["db"]
    rows = db.execute_readonly(
        """SELECT p.proname as name,
                  pg_get_function_identity_arguments(p.oid) as args,
                  l.lanname as language,
                  p.prokind as kind
           FROM pg_proc p
           JOIN pg_namespace n ON n.oid = p.pronamespace
           JOIN pg_language l ON l.oid = p.prolang
           WHERE n.nspname = 'dune' AND p.prokind = 'f'
           ORDER BY p.proname"""
    )
    return jsonify(ApiResponse(success=True, data=rows).model_dump())


@api_bp.route("/functions/<name>", methods=["GET"])
@login_required
def get_function_detail(name):
    from app.factory import get_services
    db = get_services()["db"]
    rows = db.execute_readonly(
        """SELECT pg_get_functiondef(p.oid) as definition,
                  p.proname as name,
                  pg_get_function_identity_arguments(p.oid) as args
           FROM pg_proc p
           JOIN pg_namespace n ON n.oid = p.pronamespace
           WHERE n.nspname = 'dune' AND p.proname = %s AND p.prokind = 'f'""",
        [name],
    )
    if not rows:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="NotFound", message="Function not found"),
        ).model_dump()), 404
    return jsonify(ApiResponse(success=True, data=rows[0]).model_dump())


@api_bp.route("/functions/execute", methods=["POST"])
@login_required
def execute_function_v2():
    data = request.get_json() or {}
    schema = data.get("schema")
    func_name = data.get("function", "")
    args = data.get("args", {})
    if not func_name:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing function name"),
        ).model_dump()), 400
    from app.factory import get_services
    db = get_services()["db"]
    try:
        full_name = f"{schema}.{func_name}" if schema else func_name
        if isinstance(args, dict):
            params = list(args.values())
        elif isinstance(args, list):
            params = args
        else:
            params = [args]
        result = db.call_function(full_name, params)
        _audit("function_execute", {"function": full_name, "params": params})
        return jsonify(ApiResponse(success=True, data=result).model_dump())
    except Exception as e:
        logger.exception("Function execution failed")
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ExecutionError", message=str(e)),
        ).model_dump()), 500


@api_bp.route("/functions/<name>/execute", methods=["POST"])
@login_required
def execute_function(name):
    data = request.get_json() or {}
    params = data.get("params", [])
    from app.factory import get_services
    db = get_services()["db"]
    try:
        result = db.call_function(name, params)
        _audit("function_execute", {"function": name, "params": params})
        return jsonify(ApiResponse(success=True, data=result).model_dump())
    except Exception as e:
        logger.exception("Function execution failed")
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ExecutionError", message=str(e)),
        ).model_dump()), 500


# ── Raw Query (SELECT only) ──────────────────────────────────────

@api_bp.route("/query", methods=["POST"])
@login_required
def raw_query():
    data = request.get_json() or {}
    sql = (data.get("query") or data.get("sql", "")).strip()
    if not sql:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Missing SQL"),
        ).model_dump()), 400
    upper = sql.upper()
    if any(kw in upper for kw in ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "GRANT", "TRUNCATE")):
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="Forbidden", message="Only SELECT queries are allowed"),
        ).model_dump()), 403
    from app.factory import get_services
    db = get_services()["db"]
    try:
        result = db.execute_readonly(sql)
        _audit("raw_query", {"sql": sql[:200]})
        return jsonify(ApiResponse(success=True, data=result).model_dump())
    except Exception as e:
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="QueryError", message=str(e)),
        ).model_dump()), 500


# ── Audit Logs ──────────────────────────────────────────────────

@api_bp.route("/audit/logs", methods=["GET"])
@login_required
def get_audit_logs():
    action = request.args.get("action")
    user = request.args.get("user")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    from app.factory import get_services
    svc = get_services()["audit"]
    logs = svc.get_logs(action=action, user=user, limit=limit, offset=offset)
    return jsonify(ApiResponse(success=True, data=logs).model_dump())


@api_bp.route("/stats", methods=["GET"])
@login_required
def get_stats():
    from app.factory import get_services
    db = get_services()["db"]
    try:
        stats = db.execute_readonly("""
            SELECT
                (SELECT COUNT(*) FROM public.characters) AS total_players,
                (SELECT COUNT(*) FROM public.characters WHERE is_online = true) AS online_players,
                (SELECT COUNT(*) FROM public.guilds) AS guild_count,
                (SELECT COUNT(*) FROM public.guilds WHERE active = true) AS active_guilds,
                (SELECT COUNT(*) FROM public.game_servers) AS server_count,
                (SELECT COUNT(*) FROM public.partitions) AS partition_count,
                (SELECT COALESCE(SUM(worth), 0) FROM public.player_economy) AS total_worth,
                (SELECT COUNT(*) FROM public.flavor_text) AS total_flavor_text
        """)
        return jsonify(ApiResponse(success=True, data=stats[0] if stats else {}).model_dump())
    except Exception as e:
        logger.exception("Failed to get stats")
        return jsonify(ApiResponse(success=False, error=ErrorDetail(code="StatsError", message=str(e))).model_dump()), 500


@api_bp.route("/audit/stats", methods=["GET"])
@login_required
def get_audit_stats():
    from app.factory import get_services
    svc = get_services()["audit"]
    stats = svc.get_stats()
    return jsonify(ApiResponse(success=True, data=stats).model_dump())


# ── Settings ────────────────────────────────────────────────────

@api_bp.route("/settings", methods=["GET"])
@login_required
def get_settings():
    from app.factory import get_services
    settings = get_services()["db"].execute_readonly(
        "SELECT key, value, updated_at FROM dashboard.settings ORDER BY key"
    )
    return jsonify(ApiResponse(success=True, data={r["key"]: r["value"] for r in settings}).model_dump())


@api_bp.route("/settings", methods=["POST"])
@login_required
def update_settings():
    data = request.get_json() or {}
    if not isinstance(data, dict):
        return jsonify(ApiResponse(
            success=False,
            error=ErrorDetail(code="ValidationError", message="Expected JSON object"),
        ).model_dump()), 400
    from app.factory import get_services
    db = get_services()["db"]
    for key, value in data.items():
        db.execute_mutation(
            """INSERT INTO dashboard.settings (key, value, updated_at)
               VALUES (%s, %s, NOW())
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
            [key, str(value)],
        )
    _audit("settings_update", {"keys": list(data.keys())})
    return jsonify(ApiResponse(success=True).model_dump())


# ── Moderation (Ban / Kick) ────────────────────────────────────

@api_bp.route("/players/<int:player_id>/ban", methods=["POST"])
@login_required
def ban_player(player_id):
    data = request.get_json() or {}
    reason = data.get("reason", "admin")
    duration = data.get("duration_hours", 0)
    from app.factory import get_services
    db = get_services()["db"]
    db.execute_mutation(
        """INSERT INTO dashboard.bans (player_id, reason, duration, banned_at, expires_at, active)
           VALUES (%s, %s, %s, NOW(), CASE WHEN %s > 0 THEN NOW() + INTERVAL '%s hours' ELSE NULL END, TRUE)
           ON CONFLICT (player_id) DO UPDATE SET reason = EXCLUDED.reason, duration = EXCLUDED.duration, banned_at = NOW(), expires_at = EXCLUDED.expires_at, active = TRUE""",
        [player_id, reason, duration, duration, duration],
    )
    _audit("player_ban", {"player_id": player_id, "reason": reason, "duration": duration})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/players/<int:player_id>/unban", methods=["POST"])
@login_required
def unban_player(player_id):
    from app.factory import get_services
    db = get_services()["db"]
    db.execute_mutation(
        "UPDATE dashboard.bans SET active = FALSE WHERE player_id = %s",
        [player_id],
    )
    _audit("player_unban", {"player_id": player_id})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/players/<int:player_id>/ban", methods=["GET"])
@login_required
def get_player_ban(player_id):
    from app.factory import get_services
    db = get_services()["db"]
    rows = db.execute_readonly(
        "SELECT * FROM dashboard.bans WHERE player_id = %s AND active = TRUE",
        [player_id],
    )
    return jsonify(ApiResponse(success=True, data=rows[0] if rows else None).model_dump())


@api_bp.route("/players/<int:player_id>/kick", methods=["POST"])
@login_required
def kick_player(player_id):
    data = request.get_json() or {}
    reason = data.get("reason", "admin")
    _audit("player_kick", {"player_id": player_id, "reason": reason})
    return jsonify(ApiResponse(success=True).model_dump())


@api_bp.route("/players/<int:player_id>/history", methods=["GET"])
@login_required
def get_player_history(player_id):
    from app.factory import get_services
    db = get_services()["db"]
    logs = db.execute_readonly(
        """SELECT * FROM dashboard.audit_log
           WHERE target_player_id = %s OR (details->>'player_id')::bigint = %s
           ORDER BY created_at DESC LIMIT 100""",
        [player_id, player_id],
    )
    return jsonify(ApiResponse(success=True, data=logs).model_dump())
