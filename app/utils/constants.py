"""Shared data constants and helpers"""
import json

INVENTORY_TYPE_LABELS = {
    0: 'Main Inventory',
    1: 'Equipped Items',
    5: 'Hotbar',
    12: 'Storage',
    14: 'Recipes',
    15: 'Key Items',
    20: 'Crafting Queue',
    25: 'Schematics',
    27: 'Emotes',
    29: 'Quest Items',
    30: 'Bank',
    31: 'Power Pack Slots',
    32: 'Module Slots',
    33: 'Augment Slots',
}

# Inventory types to hide from display
INVENTORY_HIDDEN_TYPES = {14, 27}

# Inventory types to show in the collapsible "Unknown" section
INVENTORY_UNKNOWN_TYPES = {12, 20, 25, 29, 30, 31, 32, 33}

# Primary inventory types shown as main sections
INVENTORY_PRIMARY_TYPES = {0, 1, 5, 15}

# Equipped item slot labels (by position_index 0-9)
EQUIPPED_SLOT_LABELS = {
    0: 'Head',
    1: 'Chest',
    2: 'Legs',
    3: 'Gloves',
    4: 'Feet',
    5: 'Unknown Spare Slot',
    6: 'Portable Light',
    7: 'Suspensor Belt',
    8: 'Power Pack',
    9: 'Shield',
}

# Quality tier colors
QUALITY_TIERS = {
    0: {'label': 'Common', 'color': '#9a8a7a'},
    1: {'label': 'Uncommon', 'color': '#27ae60'},
    2: {'label': 'Rare', 'color': '#3498db'},
    3: {'label': 'Epic', 'color': '#9b59b6'},
    4: {'label': 'Legendary', 'color': '#f39c12'},
}


def parse_stats(stats_text):
    """Parse item stats JSONB text into a dict."""
    if not stats_text:
        return {}
    try:
        return json.loads(stats_text)
    except (json.JSONDecodeError, TypeError):
        return {}

CURRENCY_ID_LABELS = {
    0: 'Solari Credits',
    1: 'House Script',
    2: 'Spice',
}

GUILD_ROLES = {100: 'Leader', 90: 'Officer', 80: 'Officer', 50: 'Member', 1: 'Member'}

NAV_PAGES = [
    ('/', 'Overview'),
    ('/server', 'Server'),
    ('/director', 'Director'),
    ('/shell', 'Shell'),
    ('/files', 'Files'),
    ('/events', 'Events'),
    ('/chat', 'Chat'),
    ('/players', 'Players'),
    ('/vehicles', 'Vehicles'),
    ('/guilds', 'Guilds'),
    ('/buildings', 'Buildings'),
    ('/map', 'Map'),
    ('/admin-experimental', 'Admin Experimental'),
]
