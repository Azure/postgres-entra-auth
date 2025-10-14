"""
Sample demonstrating an everlasting psycopg2 connection with Azure Entra ID authentication
for Azure PostgreSQL that runs queries indefinitely to test token refresh capabilities.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from psycopg2.pool import ThreadedConnectionPool
from azurepg_entra.psycopg2 import EntraConnection

# Load environment variables from .env file
load_dotenv()
SERVER = os.getenv("POSTGRES_SERVER")
DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")


def run_everlasting_queries(interval_minutes: int = 2) -> None:
    """Run database queries indefinitely with psycopg2 and Entra authentication using ThreadedConnectionPool."""

    print(f"Running queries every {interval_minutes} minutes...")
    print("Press Ctrl+C to stop\n")

    # Create connection string
    conninfo = f"postgresql://{SERVER}:5432/{DATABASE}"

    # Create connection pool with EntraConnection factory
    print("Creating connection pool with Entra ID authentication enabled...")
    pool = ThreadedConnectionPool(
        minconn=1, maxconn=3, dsn=conninfo, connection_factory=EntraConnection
    )

    execution_count = 0

    # Get one connection and reuse it throughout the program
    conn = pool.getconn()

    try:
        while True:
            execution_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"Execution #{execution_count} at {current_time}")

            try:
                with conn.cursor() as cur:
                    # Query 1: Get PostgreSQL version
                    cur.execute("SELECT version()")
                    version = cur.fetchone()
                    print(f"Connected to PostgreSQL: {version[0][:50]}...")

                    # Query 2: Get current user (shows the Entra username)
                    cur.execute("SELECT current_user")
                    user = cur.fetchone()
                    print(f"Connected as: {user[0]}")

                    # Query 3: Get current timestamp
                    cur.execute("SELECT now()")
                    timestamp = cur.fetchone()
                    print(f"Server time: {timestamp[0]}")

                    print("Query execution successful!")

            except Exception as e:
                print(f"Database error: {e}")

            print(f"Waiting {interval_minutes} minutes until next execution...\n")
            time.sleep(interval_minutes * 60)
    finally:
        pool.putconn(conn)
        pool.closeall()


def main() -> None:
    """Main function with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Demonstrate everlasting psycopg2 connection with Azure Entra ID authentication"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Query execution interval in minutes (default: 2)",
    )
    args = parser.parse_args()

    # Validate environment variables
    if not SERVER:
        print("Error: POSTGRES_SERVER environment variable is required")
        sys.exit(1)
    # Run the everlasting queries
    run_everlasting_queries(args.interval)


if __name__ == "__main__":
    main()
