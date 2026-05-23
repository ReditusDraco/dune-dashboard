# World service — partitions, spice, teleport.

import logging

from app.models import PartitionInfo
from app.services.database import DatabaseService

logger = logging.getLogger(__name__)


class WorldService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def get_partitions(self, map_name: str = "") -> list[PartitionInfo]:
        rows = self.db.call_function("get_partitions", [map_name])
        return [PartitionInfo(
            id=r.get("partition_id", 0),
            map=r.get("map", ""),
            dimension_index=r.get("dimension_index", 0),
            label=r.get("label", ""),
            definition=str(r.get("partition_definition", "")),
        ) for r in rows]

    def teleport(self, fls_id: str, partition_id: int, x: float, y: float, z: float) -> bool:
        self.db.call_procedure("admin_move_offline_player_to_partition", [fls_id, partition_id, (x, y, z)])
        return True

    def reset_spice(self, map_name: str, dimension_index: int) -> bool:
        self.db.call_procedure("reset_global_spice_field_state", [map_name, dimension_index])
        return True

    def force_spice_spawn(self, server_id: str, spicefield_type_id: int) -> bool:
        self.db.call_procedure("try_spawn_spicefield", [server_id, spicefield_type_id])
        return True
