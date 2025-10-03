"""
Sample demonstrating both synchronous and asynchronous SQLAlchemy connections 
with Azure Entra ID authentication for Azure PostgreSQL.

This example shows:
1. Synchronous connection using create_engine_with_entra and connection pooling
2. Asynchronous connection using create_async_engine_with_entra and async connection pooling

Both examples use the same Azure Entra ID authentication mechanism to connect
to Azure Database for PostgreSQL.
"""

from dotenv import load_dotenv
import argparse
import asyncio
import sys
import os
from sqlalchemy import text
from azurepg_entra.sqlalchemy import create_engine_with_entra, create_async_engine_with_entra

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
SERVER = os.getenv("POSTGRES_SERVER")
DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")

def main_sync():
    """Synchronous connection example using SQLAlchemy with Entra ID authentication."""

    try:
        # Create engine with Entra ID authentication and connection pooling
        engine = create_engine_with_entra(
            f"postgresql+psycopg://{SERVER}:5432/{DATABASE}",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Validate connections before use
            echo=False  # Set to True to see SQL queries
        )
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT now()"))
            db_time = result.fetchone()
            print(f"Sync - Database time: {db_time[0]}")
            
            # Test current user query
            result = conn.execute(text("SELECT current_user"))
            user = result.fetchone()
            print(f"Sync - Connected as: {user[0]}")
            
            # Test a simple query to verify functionality
            result = conn.execute(text("SELECT 'SQLAlchemy Sync Entra Connection Working!' as message"))
            message = result.fetchone()
            print(f"Sync - Test message: {message[0]}")
        
        # Clean up the sync engine
        engine.dispose()
            
    except Exception as e:
        print(f"Sync - Error connecting to database: {e}")
        raise

async def main_async():
    """Asynchronous connection example using SQLAlchemy with Entra ID authentication."""

    try:
        # Create async engine with Entra ID authentication and connection pooling
        engine = create_async_engine_with_entra(
            f"postgresql+psycopg://{SERVER}:5432/{DATABASE}",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Validate connections before use
            echo=False  # Set to True to see SQL queries
        )

        # Test async connection
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT now()"))
            db_time = result.fetchone()
            print(f"Async - Database time: {db_time[0]}")
            
            # Test current user query
            result = await conn.execute(text("SELECT current_user"))
            user = result.fetchone()
            print(f"Async - Connected as: {user[0]}")
            
            # Test a simple query to verify functionality
            result = await conn.execute(text("SELECT 'SQLAlchemy Async Entra Connection Working!' as message"))
            message = result.fetchone()
            print(f"Async - Test message: {message[0]}")
            
        # Clean up the async engine
        await engine.dispose()
            
    except Exception as e:
        print(f"Async - Error connecting to database: {e}")
        raise

def test_connection_pool_refresh():
    """Test that connection pool handles token refresh properly (sync version)."""
    
    try:
        print("\n=== Testing Connection Pool Token Refresh (Sync) ===")
        
        engine = create_engine_with_entra(
            f"postgresql+psycopg://{SERVER}:5432/{DATABASE}",
            pool_size=2,
            max_overflow=0,
            echo=False
        )
        
        # Make multiple connections to test token refresh
        for i in range(3):
            with engine.connect() as conn:
                result = conn.execute(text("SELECT current_user, now()"))
                user, db_time = result.fetchone()
                print(f"Connection {i+1} - User: {user}, Time: {db_time}")
        
        # Clean up the sync engine
        engine.dispose()
        print("✅ Connection pool token refresh test completed successfully!")
        
    except Exception as e:
        print(f"❌ Connection pool test failed: {e}")
        raise

async def test_async_connection_pool_refresh():
    """Test that async connection pool handles token refresh properly."""
    
    try:
        print("\n=== Testing Async Connection Pool Token Refresh ===")
        
        engine = create_async_engine_with_entra(
            f"postgresql+psycopg://{SERVER}:5432/{DATABASE}",
            pool_size=2,
            max_overflow=0,
            echo=False
        )
        
        # Make multiple async connections to test token refresh
        for i in range(3):
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT current_user, now()"))
                user, db_time = result.fetchone()
                print(f"Async Connection {i+1} - User: {user}, Time: {db_time}")
                
        await engine.dispose()
        print("✅ Async connection pool token refresh test completed successfully!")
        
    except Exception as e:
        print(f"❌ Async connection pool test failed: {e}")
        raise

async def main(mode: str = "both"):
    """Main function that runs sync and/or async examples based on mode.
    
    Args:
        mode: "sync", "async", or "both" to determine which examples to run
    """
    if mode in ("sync", "both"):
        print("=== Running Synchronous Example ===")
        try:
            main_sync()
            print("✅ Sync example completed successfully!")
            
            # Test connection pool behavior
            test_connection_pool_refresh()
            
        except Exception as e:
            print(f"❌ Sync example failed: {e}")
    
    if mode in ("async", "both"):
        if mode == "both":
            print("\n=== Running Asynchronous Example ===")
        else:
            print("=== Running Asynchronous Example ===")
        try:
            await main_async()
            print("✅ Async example completed successfully!")
            
            # Test async connection pool behavior
            await test_async_connection_pool_refresh()
            
        except Exception as e:
            print(f"❌ Async example failed: {e}")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Demonstrate SQLAlchemy connections with Azure Entra ID authentication"
    )
    parser.add_argument(
        "--mode",
        choices=["sync", "async", "both"],
        default="both",
        help="Run synchronous, asynchronous, or both examples (default: both)"
    )
    args = parser.parse_args()
    
    # Set Windows event loop policy for compatibility if needed
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main(args.mode))