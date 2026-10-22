# -*- coding: utf-8 -*-
"""
Database initialization script.

This script initializes the PostgreSQL database with all required tables.
Run this after starting the Docker containers.

Usage:
    python scripts/init_database.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database import DatabaseManager


def main():
    """Initialize the database."""
    print("=" * 50)
    print("Quantitative Trading Tool - Database Initialization")
    print("=" * 50)

    try:
        # Create database manager
        print("\n[1/3] Connecting to database...")
        db = DatabaseManager()

        # Test connection
        if db.test_connection():
            print("      Connection successful!")
        else:
            print("      Connection failed!")
            print("      Make sure PostgreSQL is running (docker-compose up -d)")
            return False

        # Create tables
        print("\n[2/3] Creating database tables...")
        db.create_tables()
        print("      Tables created successfully!")

        # Verify tables
        print("\n[3/3] Verifying tables...")
        with db.get_session() as session:
            # Try to query each table
            from core.database import Exchange, Security, Price
            exchanges = session.query(Exchange).count()
            securities = session.query(Security).count()
            prices = session.query(Price).count()

            print(f"      - Exchanges: {exchanges} records")
            print(f"      - Securities: {securities} records")
            print(f"      - Prices: {prices} records")

        print("\n" + "=" * 50)
        print("Database initialization completed successfully!")
        print("=" * 50)

        return True

    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Docker is running")
        print("2. Run: docker-compose up -d")
        print("3. Check .env file for correct database settings")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
