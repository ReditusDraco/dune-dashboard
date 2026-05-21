#!/usr/bin/env python3
"""Pre-flight database connectivity check for the launcher scripts."""

import sys
import os
import yaml
import psycopg2


def main():
    if len(sys.argv) < 2:
        print("Usage: db_check.py <port>")
        sys.exit(1)

    port = int(sys.argv[1])

    settings_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'settings.yaml')
    if not os.path.exists(settings_path):
        print("settings.yaml not found")
        sys.exit(1)

    with open(settings_path) as f:
        settings = yaml.safe_load(f) or {}

    db = settings.get('database', {})
    config = {
        'host': '127.0.0.1',
        'port': port,
        'user': db.get('user', 'postgres'),
        'password': db.get('password', ''),
        'dbname': db.get('name', 'dune'),
    }

    try:
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.close()
        conn.close()
        print("ok")
    except Exception as e:
        print(f"failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
