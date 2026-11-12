#!/usr/bin/env python3
"""
Database Migration Script
Adds missing merkle_root column to audit_logs table if it doesn't exist.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/ledger.db")


def migrate():
    """Add merkle_root column if missing."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(audit_logs)")
        columns = [row[1] for row in cursor.fetchall()]

        if "merkle_root" not in columns:
            print("Adding merkle_root column to audit_logs table...")
            cursor.execute(
                "ALTER TABLE audit_logs ADD COLUMN merkle_root VARCHAR"
            )
            conn.commit()
            print("✓ Migration successful: merkle_root column added")
        else:
            print("✓ merkle_root column already exists")

        if "source_ip" not in columns:
            print("Adding source_ip column to audit_logs table...")
            cursor.execute(
                "ALTER TABLE audit_logs ADD COLUMN source_ip VARCHAR"
            )
            conn.commit()
            print("✓ Migration successful: source_ip column added")
        else:
            print("✓ source_ip column already exists")

        if "ingestion_mode" not in columns:
            print("Adding ingestion_mode column to audit_logs table...")
            cursor.execute(
                "ALTER TABLE audit_logs ADD COLUMN ingestion_mode VARCHAR"
            )
            conn.commit()
            print("✓ Migration successful: ingestion_mode column added")
        else:
            print("✓ ingestion_mode column already exists")

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()

