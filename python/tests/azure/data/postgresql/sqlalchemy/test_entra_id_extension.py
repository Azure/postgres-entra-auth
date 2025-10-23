# Copyright (c) Microsoft. All rights reserved.

"""
Integration tests showcasing Entra ID authentication with PostgreSQL Docker instance.
These tests demonstrate token-based authentication for SQLAlchemy engines.
"""

import asyncio
import sys

import pytest

# Configure asyncio to use SelectorEventLoop on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.ext.asyncio import create_async_engine
except ImportError as e:
    # Provide a helpful error message if sqlalchemy dependencies are missing
    raise ImportError(
        "sqlalchemy dependencies are not installed. "
        "Install them with: pip install azurepg-entra[sqlalchemy]"
    ) from e

from testcontainers.postgres import PostgresContainer

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from azurepg_entra.sqlalchemy.async_entra_connection import (
    enable_entra_authentication_async,
)
from azurepg_entra.sqlalchemy.entra_connection import enable_entra_authentication
from tests.azure.data.postgresql.test_utils import (
    TestTokenCredential,
    create_jwt_token_with_xms_mirid,
    create_valid_jwt_token,
)


@pytest.fixture(scope="module")
def postgres_container():
    """Fixture to start a PostgreSQL container for the test module."""
    with PostgresContainer("postgres:15") as container:
        yield container


@pytest.fixture(scope="module")
def connection_url(postgres_container) -> str:
    """Fixture to get SQLAlchemy connection URL from the container."""
    return (
        f"postgresql+psycopg2://{postgres_container.username}:{postgres_container.password}"
        f"@{postgres_container.get_container_host_ip()}:{postgres_container.get_exposed_port(5432)}"
        f"/{postgres_container.dbname}"
    )


@pytest.fixture(scope="module")
def async_connection_url(postgres_container) -> str:
    """Fixture to get async SQLAlchemy connection URL from the container."""
    return (
        f"postgresql+psycopg://{postgres_container.username}:{postgres_container.password}"
        f"@{postgres_container.get_container_host_ip()}:{postgres_container.get_exposed_port(5432)}"
        f"/{postgres_container.dbname}"
    )


@pytest.fixture(scope="module")
def setup_entra_users(connection_url):
    """Setup test users with JWT tokens as passwords."""
    # Generate JWT tokens for each user
    test_user_token = create_valid_jwt_token("test@example.com")
    managed_identity_token = create_jwt_token_with_xms_mirid(
        "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity"
    )
    fallback_user_token = create_valid_jwt_token("fallback@example.com")
    
    setup_commands = [
        f'CREATE USER "test@example.com" WITH PASSWORD \'{test_user_token}\';',
        f'CREATE USER "managed-identity" WITH PASSWORD \'{managed_identity_token}\';',
        f'CREATE USER "fallback@example.com" WITH PASSWORD \'{fallback_user_token}\';',
        'GRANT CONNECT ON DATABASE test TO "test@example.com";',
        'GRANT CONNECT ON DATABASE test TO "managed-identity";',
        'GRANT CONNECT ON DATABASE test TO "fallback@example.com";',
        'GRANT ALL PRIVILEGES ON DATABASE test TO "test@example.com";',
        'GRANT ALL PRIVILEGES ON DATABASE test TO "managed-identity";',
        'GRANT ALL PRIVILEGES ON DATABASE test TO "fallback@example.com";',
        'GRANT ALL ON SCHEMA public TO "test@example.com";',
        'GRANT ALL ON SCHEMA public TO "managed-identity";',
        'GRANT ALL ON SCHEMA public TO "fallback@example.com";',
        'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "test@example.com";',
        'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "managed-identity";',
        'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "fallback@example.com";',
        'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "test@example.com";',
        'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "managed-identity";',
        'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "fallback@example.com";',
    ]
    
    engine = create_engine(connection_url)
    with engine.connect() as conn:
        for sql in setup_commands:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                # Ignore errors if user already exists
                conn.rollback()
    engine.dispose()


def assert_sqlalchemy_entra_works(
    base_url: str,
    token: str,
    expected_username: str
) -> None:
    """Helper to test synchronous SQLAlchemy Entra connection works end-to-end.
    
    Verifies username extraction, connection establishment, and database operations.
    """
    # Create credential
    credential = TestTokenCredential(token)
    
    # Create engine with Entra authentication
    engine = create_engine(base_url, connect_args={"credential": credential})
    enable_entra_authentication(engine)
    
    # Connect and verify
    with engine.connect() as conn:
        result = conn.execute(text("SELECT current_user, current_database()"))
        current_user, current_db = result.fetchone()
        
        assert current_user == expected_username
        assert current_db == "test"
    
    engine.dispose()


async def assert_async_sqlalchemy_entra_works(
    base_url: str,
    token: str,
    expected_username: str
) -> None:
    """Helper to test asynchronous SQLAlchemy Entra connection works end-to-end.
    
    Verifies username extraction, connection establishment, and database operations.
    """
    # Create credential
    credential = TestTokenCredential(token)
    
    # Create async engine with Entra authentication
    engine = create_async_engine(base_url, connect_args={"credential": credential})
    enable_entra_authentication_async(engine)
    
    # Connect and verify
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT current_user, current_database()"))
        row = result.fetchone()
        current_user, current_db = row
        
        assert current_user == expected_username
        assert current_db == "test"
    
    await engine.dispose()


class TestSQLAlchemyEntraConnection:
    """Tests for synchronous SQLAlchemy with enable_entra_authentication."""
    
    def test_connect_with_entra_user(self, connection_url, setup_entra_users):
        """Showcases connecting with an Entra user using enable_entra_authentication.
        Demonstrates: End-to-end connection with token-based authentication.
        """
        # Remove credentials from URL
        # Format: postgresql+psycopg2://user:pass@host:port/db -> postgresql+psycopg2://host:port/db
        parts = connection_url.split('@')
        base_url = f"postgresql+psycopg2://{parts[1]}"
        
        test_token = create_valid_jwt_token("test@example.com")
        assert_sqlalchemy_entra_works(base_url, test_token, "test@example.com")
    
    def test_connect_with_managed_identity(self, connection_url, setup_entra_users):
        """Showcases connecting with a managed identity using enable_entra_authentication.
        Demonstrates: End-to-end MI authentication with token-based authentication.
        """
        # Remove credentials from URL
        parts = connection_url.split('@')
        base_url = f"postgresql+psycopg2://{parts[1]}"
        
        xms_mirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity"
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        assert_sqlalchemy_entra_works(base_url, mi_token, "managed-identity")

class TestAsyncSQLAlchemyEntraConnection:
    """Tests for asynchronous SQLAlchemy with enable_entra_authentication_async."""
    
    @pytest.mark.asyncio
    async def test_connect_with_entra_user_async(self, async_connection_url, setup_entra_users):
        """Showcases connecting with an Entra user using enable_entra_authentication_async.
        Demonstrates: Async version of end-to-end connection with token-based authentication.
        """
        # Remove credentials from URL
        parts = async_connection_url.split('@')
        base_url = f"postgresql+psycopg://{parts[1]}"
        
        test_token = create_valid_jwt_token("test@example.com")
        await assert_async_sqlalchemy_entra_works(base_url, test_token, "test@example.com")
    
    @pytest.mark.asyncio
    async def test_connect_with_managed_identity_async(self, async_connection_url, setup_entra_users):
        """Showcases connecting with a managed identity using enable_entra_authentication_async.
        Demonstrates: Async version of end-to-end MI authentication with token-based authentication.
        """
        # Remove credentials from URL
        parts = async_connection_url.split('@')
        base_url = f"postgresql+psycopg://{parts[1]}"
        
        xms_mirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity"
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        await assert_async_sqlalchemy_entra_works(base_url, mi_token, "managed-identity")