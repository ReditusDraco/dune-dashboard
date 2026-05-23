# Progression service — journey and specialization using DB functions.

import logging

from app.services.database import DatabaseService

logger = logging.getLogger(__name__)


class ProgressionService:
    def __init__(self, db: DatabaseService):
        self.db = db

    def complete_nodes(self, player_id: str, node_ids: list[str]) -> bool:
        self.db.call_procedure("complete_journey_story_nodes_for_player", [player_id, node_ids])
        return True

    def reveal_nodes(self, player_id: str, node_ids: list[str]) -> bool:
        self.db.call_procedure("reveal_journey_story_nodes_for_player", [player_id, node_ids])
        return True

    def reset_nodes(self, player_id: str, node_ids: list[str]) -> bool:
        self.db.call_procedure("delete_journey_story_nodes_for_player", [player_id, node_ids])
        return True

    def set_specialization(self, player_id: int, track_type: str, xp: int, level: float) -> bool:
        self.db.call_procedure("set_specialization_xp_and_level", [player_id, track_type, xp, level])
        return True

    def reset_specializations(self, player_id: int) -> bool:
        self.db.call_procedure("reset_specialization_tracks", [player_id])
        return True
