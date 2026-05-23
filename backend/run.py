"""Entry point for the new backend."""

import sys
import os

# Add backend to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.factory import create_app

app = create_app()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    app.run(
        host=app.dune_settings["dashboard"]["host"],
        port=app.dune_settings["dashboard"]["port"],
        debug=app.dune_settings["dashboard"]["debug"],
    )
