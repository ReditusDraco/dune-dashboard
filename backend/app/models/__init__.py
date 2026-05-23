# Pydantic models for the Dune Admin Dashboard API.

from pydantic import BaseModel, Field
from typing import Any, List, Optional


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None


# ── Player Models ───────────────────────────────────────────────

class Vitals(BaseModel):
    current_health: Optional[float] = None
    max_health: Optional[float] = None
    current_hydration: Optional[float] = None
    dehydration_penalty: Optional[float] = None
    current_spice: Optional[float] = None
    spice_addiction_level: Optional[float] = None
    spice_tolerance: Optional[float] = None


class CurrencyBalance(BaseModel):
    currency_id: int
    currency_label: str
    balance: float = 0.0


class Item(BaseModel):
    id: Optional[int] = None
    template_id: str = ""
    stack_size: int = 1
    quality_level: int = 0
    is_new: bool = False
    position_index: int = 0
    stats: Optional[Any] = None
    durability: Optional[float] = None
    max_durability: Optional[float] = None
    ammo: Optional[int] = None


class Inventory(BaseModel):
    inventory_id: int
    actor_id: Optional[int] = None
    inventory_type: int = 0
    inventory_type_label: str = ""
    max_item_count: Optional[int] = None
    max_item_volume: Optional[float] = None
    items: List[Item] = []


class VehicleSummary(BaseModel):
    id: Optional[int] = None
    class_name: str = ""
    display_name: str = ""
    map: Optional[str] = None


class BuildingSummary(BaseModel):
    id: Optional[int] = None
    class_name: str = ""
    map: Optional[str] = None
    owner_name: str = ""
    instance_count: int = 0
    is_powered: bool = False
    power_level: Optional[Any] = None


class Landclaim(BaseModel):
    id: Optional[int] = None
    class_name: str = ""
    map: Optional[str] = None


class SpecializationTrack(BaseModel):
    track_type: str = ""
    xp_amount: int = 0
    level: int = 0


class Keystone(BaseModel):
    id: int
    name: str = ""


class FactionReputation(BaseModel):
    faction_id: Optional[int] = None
    faction_name: str = ""
    reputation_amount: int = 0


class LandsraadInfo(BaseModel):
    daily_reward_charges: Optional[int] = None
    last_viewed_term_id: Optional[int] = None
    daily_reward_last_processed: Optional[Any] = None


class PlayerSummary(BaseModel):
    player_controller_id: Optional[int] = None
    character_name: str = "Unknown"
    account_email: Optional[str] = None
    funcom_id: Optional[str] = None
    faction_name: Optional[str] = None
    faction_id: Optional[int] = None
    map: Optional[str] = None
    online_status: str = "Unknown"
    life_state: Optional[str] = None
    last_login_time: Optional[str] = None
    last_avatar_activity: Optional[str] = None


class PlayerDetail(BaseModel):
    id: Optional[int] = None
    account_id: int
    player_controller_id: Optional[int] = None
    player_pawn_id: Optional[int] = None
    character_name: str = "Unknown"
    account_email: Optional[str] = None
    funcom_id: Optional[str] = None
    faction_name: Optional[str] = None
    faction_id: Optional[int] = None
    map: Optional[str] = None
    online_status: str = "Unknown"
    life_state: Optional[str] = None
    last_login_time: Optional[str] = None
    last_avatar_activity: Optional[str] = None
    vitals: Optional[Vitals] = None
    currency: List[CurrencyBalance] = []
    inventories: List[Inventory] = []
    vehicles: List[VehicleSummary] = []
    buildings: List[BuildingSummary] = []
    landclaims: List[Landclaim] = []
    specialization: List[SpecializationTrack] = []
    keystones: List[Keystone] = []
    faction_reputation: List[FactionReputation] = []
    landsraad: Optional[LandsraadInfo] = None
    tags: List[str] = []
    is_online: bool = False


# ── Guild Models ────────────────────────────────────────────────

class GuildMember(BaseModel):
    player_id: int
    role_id: int = 50
    role_name: str = "Member"
    player_name: str = "Unknown"
    online_status: str = "Unknown"


class GuildSummary(BaseModel):
    guild_id: int
    guild_name: str = ""
    guild_description: Optional[str] = None
    faction_name: Optional[str] = None
    member_count: int = 0
    online_count: int = 0


class GuildDetail(BaseModel):
    guild_id: int
    guild_name: str = ""
    guild_description: Optional[str] = None
    faction_name: Optional[str] = None
    faction_id: Optional[int] = None
    members: List[GuildMember] = []


# ── World Models ───────────────────────────────────────────────

class PartitionInfo(BaseModel):
    partition_id: int
    name: str = ""
    map: Optional[str] = None
    player_count: int = 0
    status: str = "unknown"


# ── RMQ Models ────────────────────────────────────────────────

class RmqQueueInfo(BaseModel):
    name: str
    messages: int = 0
    consumers: int = 0
    state: str = ""


class RmqOverview(BaseModel):
    queues: List[RmqQueueInfo] = []
    total_messages: int = 0
    total_consumers: int = 0


# ── BGD Models ────────────────────────────────────────────────

class BattlegroupState(BaseModel):
    battlegroup_id: Optional[int] = None
    name: Optional[str] = None
    status: Optional[str] = None
    player_count: Optional[int] = None
    servers: Optional[List[Any]] = None


# ── Request Models ─────────────────────────────────────────────

class BroadcastRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    server: Optional[str] = None
    partition: Optional[str] = None


class TeleportRequest(BaseModel):
    player_id: int
    destination: str = Field(..., min_length=1)


class FunctionExecuteRequest(BaseModel):
    schema_name: Optional[str] = Field(default=None, alias="schema")
    function: str = Field(..., min_length=1)
    args: dict = {}


class RawQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
