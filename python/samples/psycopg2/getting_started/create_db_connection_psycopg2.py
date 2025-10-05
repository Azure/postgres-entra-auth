"""
Sample demonstrating psycopg2 connection with synchronous Entra ID authentication for Azure PostgreSQL.
"""

from dotenv import load_dotenv
import os
from psycopg2 import pool
from azurepg_entra.psycopg2 import SyncEntraConnection

# Load environment variables from .env file
load_dotenv()
SERVER = os.getenv("POSTGRES_SERVER")
DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")

def main_sync():
    try:
        # We pass in the SyncEntraConnection class to enable Entra authentication for the
        # PostgreSQL database by acquiring an Azure access token, extracting a username from the token, and using
        # the token itself (with the PostgreSQL scope) as the password.
        connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            host=SERVER,
            database=DATABASE,
            connection_factory=SyncEntraConnection
        )

        # Get a connection from the pool
        conn = connection_pool.getconn()
        
        try:
            with conn.cursor() as cur:
                # Query 1
                cur.execute("SELECT now()")
                result = cur.fetchone()
                print(f"Database time: {result[0]}")
                
                # Query 2
                cur.execute("SELECT current_user")
                user = cur.fetchone()
                print(f"Connected as: {user[0]}")
        finally:
            # Return connection to pool
            connection_pool.putconn(conn)
            connection_pool.closeall()
            
    except Exception as e:
        print(f"Sync - Error connecting to database: {e}")
        raise

if __name__ == "__main__":
    main_sync()