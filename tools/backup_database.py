"""Online SQLite backup; writes only inside the selected private runtime directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

import sqlite3
from datetime import datetime, timezone
from app import create_app
from models import db


if __name__ == '__main__':
    app = create_app({'AUTO_SEED': False})
    with app.app_context():
        source_path = db.engine.url.database
        destination = Path(app.config['INSTANCE_DIRECTORY']) / 'backups'
        destination.mkdir(parents=True, exist_ok=True)
        filename = destination / ('medibed-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.db')
        with sqlite3.connect(source_path) as source, sqlite3.connect(filename) as target:
            source.backup(target)
        print('Backup created:', filename)
