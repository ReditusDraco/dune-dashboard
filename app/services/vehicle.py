"""Vehicle service - vehicle queries and operations"""

import logging

logger = logging.getLogger(__name__)

VEHICLE_TYPE_MAP = {
    'BP_MediumOrnithopter_CHOAM': 'Medium Ornithopter',
    'BP_TransportOrnithopter_CHOAM': 'Transport Ornithopter',
    'BP_Buggy_CHOAM': 'Buggy',
    'BP_LightOrnithopter_Choam': 'Light Ornithopter',
    'BP_Sandbike_CHOAM': 'Sandbike',
}

TYPE_CONFIGS = {
    'Ornithopter': {
        'base': {'Chassis': 2200, 'Engine': 2000, 'Generator': 2000, 'Hull': 1650, 'HullFront': 1650, 'HullBack': 1650, 'Locomotion': 2000, 'Boost': 2000, 'Launcher': 2000},
        'names': {'Chassis': 'Chassis', 'Engine': 'Engine', 'Generator': 'Generator', 'Hull': 'Hull', 'HullFront': 'Cockpit', 'HullBack': 'Tail', 'Locomotion': 'Wing', 'Boost': 'Boost', 'Launcher': 'Launcher'}
    },
    'Transport': {
        'base': {'Chassis': 2200, 'Engine': 2000, 'Generator': 2000, 'Hull': 1650, 'HullFront': 1650, 'HullBack': 1650, 'Locomotion': 2000},
        'names': {'Chassis': 'Chassis', 'Engine': 'Engine', 'Generator': 'Generator', 'Hull': 'Hull', 'HullFront': 'Main Hull', 'HullBack': 'Tail Hull', 'Locomotion': 'Wing'}
    },
    'Buggy': {
        'base': {'Chassis': 3500, 'Engine': 1750, 'Generator': 1750, 'Hull': 2625, 'HullFront': 2625, 'HullBack': 2625, 'Locomotion': 1750},
        'names': {'Chassis': 'Chassis', 'Engine': 'Engine', 'Generator': 'PSU', 'Hull': 'Hull', 'HullFront': 'Front', 'HullBack': 'Rear', 'Locomotion': 'Tread'}
    },
    'Sandcrawler': {
        'base': {'Chassis': 4250, 'Hull': 3187, 'Locomotion': 2500, 'SpiceHeader': 2500, 'Generator': 2500, 'Engine': 2500, 'SpiceContainer': 3200},
        'names': {'Chassis': 'Chassis', 'Hull': 'Hull', 'Locomotion': 'Tread', 'SpiceHeader': 'Spice Header', 'Generator': 'PSU', 'Engine': 'Engine', 'SpiceContainer': 'Spice Container'}
    },
    'Sandbike': {
        'base': {'Chassis': 1500, 'Engine': 1200, 'Generator': 1200, 'Hull': 1000, 'Locomotion': 1200},
        'names': {'Chassis': 'Chassis', 'Engine': 'Engine', 'Generator': 'Generator', 'Hull': 'Hull', 'Locomotion': 'Wheel'}
    }
}


def vehicle_type_name(cls):
    if '/' in cls:
        short = cls.split('/')[-1].replace('_C', '')
        for key, name in VEHICLE_TYPE_MAP.items():
            if key in short:
                return name
        return short.replace('BP_', '').replace('_CHOAM', '').replace('_Choam', '').replace('_', ' ')
    return cls


def get_vehicle_type_config(vehicle_class):
    type_order = ['Sandcrawler', 'Sandbike', 'Buggy', 'Transport', 'Ornithopter', 'Light', 'Medium']
    for t in type_order:
        if t in vehicle_class:
            return TYPE_CONFIGS.get(t, TYPE_CONFIGS['Buggy'])
    return TYPE_CONFIGS['Buggy']


def parse_vehicle_modules(modules, vehicle_class):
    config = get_vehicle_type_config(vehicle_class)
    parsed = []
    for m in modules:
        stats = m.get('stats', {})
        durability = stats.get('FVehicleModuleDurabilityStats', [{}])[1] if stats.get('FVehicleModuleDurabilityStats') else {}
        current = durability.get('CurrentDurability', 0)
        max_durability = durability.get('MaxDurability') or durability.get('DecayedMaxDurability') or current

        template = m.get('template_id', '')
        mod_clean = template.replace('Ornithopter', '').replace('Buggy', '').replace('Sandcrawler', '').replace('Sandbike', '').replace('_6', '').replace('_0', '')
        mod_type = mod_clean.replace('Medium', '').replace('Transport', '').replace('Light', '').replace('Heavy', '').replace('Front', '').replace('Back', '').replace('Left', '').replace('Right', '').replace('Center', '').replace('1', '').replace('2', '')
        name = config['names'].get(mod_type, mod_clean)

        parsed.append({
            'id': m['id'],
            'name': name,
            'template': template,
            'current': round(current, 1),
            'max': round(max_durability, 1),
            'damage_cause': durability.get('LastDeteriorationCause', '')
        })
    return parsed


class VehicleService:
    def __init__(self, db_service):
        self.db = db_service

    def get_all_vehicles(self, limit=200):
        return self.db.query("""
            SELECT a.id, a.class, a.map, a.transform::text as transform_text,
                pa.actor_name,
                pilot_ps.character_name as pilot_name,
                pilot_a.id as pilot_pawn_id,
                ps_owner.character_name as owner_name,
                ps_owner.player_pawn_id as owner_pawn_id,
                par.rank as owner_rank
            FROM dune.actors a
            JOIN dune.vehicles v ON a.id = v.id
            LEFT JOIN dune.permission_actor pa ON a.id = pa.actor_id AND pa.is_child = FALSE
            LEFT JOIN dune.actors pilot_a ON pilot_a.properties->'BP_DunePlayerCharacter_C'->>'m_CurrentVehicleId' = CONCAT('!!act#', a.id::text)
                AND (pilot_a.properties->'BP_DunePlayerCharacter_C'->>'m_bIsDriving')::boolean = TRUE
            LEFT JOIN dune.player_state pilot_ps ON pilot_a.owner_account_id = pilot_ps.account_id AND pilot_a.id = pilot_ps.player_pawn_id
            LEFT JOIN dune.permission_actor_rank par ON a.id = par.permission_actor_id AND par.rank = 1
            LEFT JOIN dune.player_state ps_owner ON par.player_id = ps_owner.player_controller_id
            ORDER BY a.class
            LIMIT %s
        """, [limit]) or []

    def get_vehicle(self, vehicle_id):
        return self.db.query("""
            SELECT a.id, a.class, a.map, a.transform::text as transform_text,
                pa.actor_name,
                ps.character_name as owner_name,
                ps.player_pawn_id as owner_pawn_id
            FROM dune.actors a
            JOIN dune.vehicles v ON a.id = v.id
            LEFT JOIN dune.permission_actor pa ON a.id = pa.actor_id AND pa.is_child = FALSE
            LEFT JOIN dune.permission_actor_rank par ON a.id = par.permission_actor_id AND par.rank = 1
            LEFT JOIN dune.player_state ps ON par.player_id = ps.player_controller_id
            WHERE a.id = %s
        """, [vehicle_id], one=True)

    def get_vehicle_modules(self, vehicle_id):
        return self.db.query("""
            SELECT id, template_id, stats
            FROM dune.vehicle_modules
            WHERE vehicle_id = %s
            ORDER BY id
        """, [vehicle_id]) or []

    
