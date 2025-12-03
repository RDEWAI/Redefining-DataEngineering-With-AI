#!/usr/bin/env python3
"""
Script to add DuckDB as a data source in Apache Superset.

This script runs during `make superset-init` to automatically configure
DuckDB as an available database connection for creating charts and dashboards.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def add_duckdb_database():
    """Add DuckDB database connection to Superset."""
    from superset.app import create_app

    # Create and configure the Superset app
    app = create_app()

    with app.app_context():
        # Import these inside the app context to avoid circular dependency issues
        from superset.models.core import Database
        from superset.extensions import db
        # Get the DuckDB database path from config
        duckdb_path = app.config.get('DUCKDB_DATABASE')
        if not duckdb_path:
            duckdb_path = PROJECT_ROOT / 'data' / 'duckdb' / 'raw.db'

        # SQLAlchemy URI for DuckDB
        sqlalchemy_uri = f"duckdb:///{duckdb_path}"

        # Check if DuckDB database already exists
        existing_db = db.session.query(Database).filter_by(
            database_name="DuckDB Analytics"
        ).first()

        if existing_db:
            print(f"✓ DuckDB database connection already exists (ID: {existing_db.id})")
            # Update the URI in case the path changed
            if existing_db.sqlalchemy_uri != sqlalchemy_uri:
                existing_db.sqlalchemy_uri = sqlalchemy_uri
                db.session.commit()
                print(f"  Updated connection URI to: {sqlalchemy_uri}")
            return

        # Create new database connection
        database = Database(
            database_name="DuckDB Analytics",
            sqlalchemy_uri=sqlalchemy_uri,
            expose_in_sqllab=True,
            allow_run_async=False,
            allow_file_upload=True,
        )

        db.session.add(database)
        db.session.commit()

        print(f"✓ DuckDB database connection created successfully")
        print(f"  Database: DuckDB Analytics")
        print(f"  URI: {sqlalchemy_uri}")
        print(f"  Path: {duckdb_path}")

if __name__ == "__main__":
    try:
        add_duckdb_database()
    except Exception as e:
        import traceback
        print(f"ERROR: Failed to add DuckDB connection: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
