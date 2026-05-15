import sys
sys.path.insert(0, '.')
from app.config import load_settings
from app.services.database import DatabaseService
import re

settings = load_settings()
db_config = {
    'host': settings['database']['host'],
    'port': settings['database']['port'],
    'user': settings['database']['user'],
    'password': settings['database']['password'],
    'database': settings['database']['name'],
}
db = DatabaseService(db_config, 2, 10)

# Get count by map
counts = db.query('''
    SELECT map, COUNT(*) as cnt
    FROM dune.actors
    WHERE transform IS NOT NULL
    GROUP BY map
    ORDER BY cnt DESC
''')

print('Map coordinate counts:')
for c in counts:
    print(f"  {c['map']}: {c['cnt']} items")

# Get bounds for HaggaBasin (seems to have more)
print('\n=== HaggaBasin bounds ===')
coords = db.query('''
    SELECT transform FROM dune.actors
    WHERE map = 'HaggaBasin' AND transform IS NOT NULL
    LIMIT 500
''')

points = []
for a in coords:
    t = a.get('transform')
    if t:
        pos_match = re.search(r'\(([0-9.e+-]+),([0-9.e+-]+),([0-9.e+-]+)\)', str(t))
        if pos_match:
            points.append((float(pos_match.group(1)), float(pos_match.group(2))))

if points:
    x_vals = [p[0] for p in points]
    y_vals = [p[1] for p in points]
    print(f'Min X: {min(x_vals):.1f}, Max X: {max(x_vals):.1f}')
    print(f'Min Y: {min(y_vals):.1f}, Max Y: {max(y_vals):.1f}')
    print(f'X range: {max(x_vals) - min(x_vals):.1f}')
    print(f'Y range: {max(y_vals) - min(y_vals):.1f}')