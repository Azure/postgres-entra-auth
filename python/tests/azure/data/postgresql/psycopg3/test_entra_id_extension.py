# Copyright (c) Microsoft. All rights reserved.

"""
Integration tests showcasing Entra ID authentication with PostgreSQL Docker instance.
These tests demonstrate token-based authentication for psycopg3.
"""

import asyncio
import sys

import pytest

# Configure asyncio to use SelectorEventLoop on Windows for psycopg3 compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    from psycopg import Connection
except ImportError as e:
    # Provide a helpful error message if psycopg3 dependencies are missing
    raise ImportError(
        "psycopg3 dependencies are not installed. "
        "Install them with: pip install azurepg-entra[psycopg3]"
    ) from e

from testcontainers.postgres import PostgresContainer

from azurepg_entra.psycopg3.async_entra_connection import AsyncEntraConnection
from azurepg_entra.psycopg3.entra_connection import EntraConnection
from tests.azure.data.postgresql.test_utils import (
    TestAsyncTokenCredential,
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
def connection_params(postgres_container) -> dict[str, str]:
    """Fixture to get connection parameters from the container."""
    return {
        "host": postgres_container.get_container_host_ip(),
        "port": postgres_container.get_exposed_port(5432),
        "dbname": postgres_container.dbname,
        "user": postgres_container.username,
        "password": postgres_container.password,
    }


@pytest.fixture(scope="module")
def setup_entra_users(connection_params):
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
    
    with Connection.connect(**connection_params) as conn:
        with conn.cursor() as cur:
            for sql in setup_commands:
                try:
                    cur.execute(sql)
                    conn.commit()
                except Exception:
                    # Ignore errors if user already exists
                    conn.rollback()


def assert_entra_connection_works(
    connection_params: dict[str, str],
    token: str,
    expected_username: str
) -> None:
    """Helper to test synchronous Entra connection works end-to-end."""
    # Remove user and password from connection params
    test_params = {k: v for k, v in connection_params.items() if k not in ['user', 'password']}
    
    # Add credential
    credential = TestTokenCredential(token)
    
    # Connect using EntraConnection
    with EntraConnection.connect(**test_params, credential=credential) as conn:
        with conn.cursor() as cur:
            # Test basic operations
            cur.execute("SELECT current_user, current_database()")
            current_user, current_db = cur.fetchone()
            
            assert current_user == expected_username
            assert current_db == "test"


async def assert_async_entra_connection_works(
    connection_params: dict[str, str],
    token: str,
    expected_username: str
) -> None:
    """Helper to test asynchronous Entra connection works end-to-end."""
    # Remove user and password from connection params
    test_params = {k: v for k, v in connection_params.items() if k not in ['user', 'password']}
    
    # Add credential
    credential = TestAsyncTokenCredential(token)
    
    # Connect using AsyncEntraConnection
    async with await AsyncEntraConnection.connect(**test_params, credential=credential) as conn:
        async with conn.cursor() as cur:
            # Test basic operations
            await cur.execute("SELECT current_user, current_database()")
            result = await cur.fetchone()
            current_user, current_db = result
            
            assert current_user == expected_username
            assert current_db == "test"


class TestEntraConnection:
    """Tests for synchronous EntraConnection."""
    
    def test_connect_with_entra_user(self, connection_params, setup_entra_users):
        """Showcases connecting with an Entra user using EntraConnection.
        Demonstrates: End-to-end connection with token-based authentication.
        """
        test_token = create_valid_jwt_token("test@example.com")
        assert_entra_connection_works(connection_params, test_token, "test@example.com")
    
    def test_connect_with_managed_identity(self, connection_params, setup_entra_users):
        """Showcases connecting with a managed identity using EntraConnection.
        Demonstrates: End-to-end MI authentication with token-based authentication.
        """
        xms_mirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity"
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        assert_entra_connection_works(connection_params, mi_token, "managed-identity")


class TestAsyncEntraConnection:
    """Tests for asynchronous AsyncEntraConnection."""
    
    @pytest.mark.asyncio
    async def test_connect_with_entra_user_async(self, connection_params, setup_entra_users):
        """Showcases connecting with an Entra user using AsyncEntraConnection.
        Demonstrates: Async version of end-to-end connection with token-based authentication.
        """
        test_token = create_valid_jwt_token("test@example.com")
        await assert_async_entra_connection_works(connection_params, test_token, "test@example.com")
    
    @pytest.mark.asyncio
    async def test_connect_with_managed_identity_async(self, connection_params, setup_entra_users):
        """Showcases connecting with a managed identity using AsyncEntraConnection.
        Demonstrates: Async version of end-to-end MI authentication with token-based authentication.
        """
        xms_mirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity"
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        await assert_async_entra_connection_works(connection_params, mi_token, "managed-identity")
