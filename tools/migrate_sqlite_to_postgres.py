"""Back up and copy MediBed SQLite data into an empty PostgreSQL database."""
import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import URL, make_url
from models import db


def migrate(source_path, target_url):
    source_path = Path(source_path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f'Source SQLite database does not exist: {source_path}')
    database_url = make_url(target_url)
    if database_url.get_backend_name() != 'postgresql':
        raise ValueError('DATABASE_URL must point to a PostgreSQL database.')
    if database_url.drivername in ('postgres', 'postgresql'):
        database_url = database_url.set(drivername='postgresql+psycopg')
    tables = db.metadata.sorted_tables
    target_engine = create_engine(database_url, connect_args={'connect_timeout': 15})
    source_engine = create_engine(URL.create('sqlite', database=str(source_path)))

    try:
        source_inspector = inspect(source_engine)
        source_tables = set(source_inspector.get_table_names())
        expected_tables = {table.name for table in tables}
        missing_tables = expected_tables - source_tables
        extra_tables = source_tables - expected_tables
        if missing_tables or extra_tables:
            raise ValueError(
                f'Source schema does not match this app; missing={sorted(missing_tables)}, '
                f'extra={sorted(extra_tables)}'
            )
        for table in tables:
            source_columns = {column['name'] for column in source_inspector.get_columns(table.name)}
            model_columns = {column.name for column in table.columns}
            if source_columns != model_columns:
                raise ValueError(
                    f'Source schema mismatch in {table.name}; '
                    f'missing={sorted(model_columns - source_columns)}, '
                    f'extra={sorted(source_columns - model_columns)}'
                )

        backup_dir = source_path.parent / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / (
            'medibed-pre-postgres-' +
            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.db'
        )
        with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as backup:
            source.backup(backup)

        db.metadata.create_all(bind=target_engine)
        with target_engine.connect() as connection:
            populated = []
            for table in tables:
                count = connection.scalar(select(func.count()).select_from(table))
                if count:
                    populated.append(table.name)
            if populated:
                raise ValueError(
                    f'Target database is not empty; refusing to overwrite tables: {sorted(populated)}'
                )

        copied = {}
        with source_engine.connect() as source, target_engine.begin() as target:
            for table in tables:
                rows = source.execute(select(table)).mappings()
                count = 0
                while batch := rows.fetchmany(500):
                    target.execute(table.insert(), [dict(row) for row in batch])
                    count += len(batch)
                copied[table.name] = count
            if target_engine.dialect.name == 'postgresql':
                for table in tables:
                    for column in table.primary_key.columns:
                        if column.autoincrement is False:
                            continue
                        sequence = target.scalar(
                            text('SELECT pg_get_serial_sequence(:table_name, :column_name)'),
                            {'table_name': table.name, 'column_name': column.name},
                        )
                        if sequence:
                            maximum = target.scalar(select(func.max(column)).select_from(table))
                            target.execute(
                                text('SELECT setval(CAST(:sequence AS regclass), :value, :called)'),
                                {
                                    'sequence': sequence,
                                    'value': maximum or 1,
                                    'called': maximum is not None,
                                },
                            )

        print(f'Backup created: {backup_path}')
        print('Rows copied:', ', '.join(f'{name}={count}' for name, count in copied.items()))
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Path to the local MediBed SQLite database')
    args = parser.parse_args()
    import os

    destination = os.environ.get('DATABASE_URL')
    if not destination:
        parser.error('Set DATABASE_URL to the Render external PostgreSQL connection URL.')
    migrate(args.source, destination)
