# World service — partitions, spice, teleport.

import logging

from app.services.database import DatabaseService

logger = logging.getLogger(__name__)


class WorldService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def get_partitions(self, map_name: str = "") -> list[dict]:
        try:
            if map_name:
                return self.db.execute_readonly(
                    """SELECT partition_id as id, map, dimension_index,
                              label, partition_definition::text as definition
                       FROM dune.partitions WHERE map = %s ORDER BY partition_id""",
                    [map_name],
                )
            return self.db.execute_readonly(
                """SELECT partition_id as id, map, dimension_index,
                          label, partition_definition::text as definition
                   FROM dune.partitions ORDER BY partition_id"""
            )
        except Exception:
            return []

    def teleport(self, fls_id: str, partition_id: int, x: float, y: float, z: float) -> bool:
        try:
            self.db.execute_mutation(
                "SELECT dune.admin_move_offline_player_to_partition(%s, %s, (%s, %s, %s))",
                [fls_id, partition_id, x, y, z],
            )
            return True
        except Exception:
            return False

    def reset_spice(self, map_name: str, dimension_index: int) -> bool:
        return False

    def force_spice_spawn(self, server_id: str, spicefield_type_id: int) -> bool:
        return False
