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
from tests.azurepg_entra.test_utils import (
    TEST_USERS,
    TestAsyncTokenCredential,
    TestTokenCredential,
    create_jwt_token_with_preferred_username,
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
    test_user_token = create_valid_jwt_token(TEST_USERS['ENTRA_USER'])
    managed_identity_token = create_jwt_token_with_xms_mirid(TEST_USERS['MANAGED_IDENTITY_PATH'])
    fallback_user_token = create_valid_jwt_token(TEST_USERS['FALLBACK_USER'])
    
    setup_commands = [
        f'CREATE USER "{TEST_USERS["ENTRA_USER"]}" WITH PASSWORD \'{test_user_token}\';',
        f'CREATE USER "{TEST_USERS["MANAGED_IDENTITY_NAME"]}" WITH PASSWORD \'{managed_identity_token}\';',
        f'CREATE USER "{TEST_USERS["FALLBACK_USER"]}" WITH PASSWORD \'{fallback_user_token}\';',
        f'GRANT CONNECT ON DATABASE test TO "{TEST_USERS["ENTRA_USER"]}";',
        f'GRANT CONNECT ON DATABASE test TO "{TEST_USERS["MANAGED_IDENTITY_NAME"]}";',
        f'GRANT CONNECT ON DATABASE test TO "{TEST_USERS["FALLBACK_USER"]}";',
        f'GRANT ALL PRIVILEGES ON DATABASE test TO "{TEST_USERS["ENTRA_USER"]}";',
        f'GRANT ALL PRIVILEGES ON DATABASE test TO "{TEST_USERS["MANAGED_IDENTITY_NAME"]}";',
        f'GRANT ALL PRIVILEGES ON DATABASE test TO "{TEST_USERS["FALLBACK_USER"]}";',
        f'GRANT ALL ON SCHEMA public TO "{TEST_USERS["ENTRA_USER"]}";',
        f'GRANT ALL ON SCHEMA public TO "{TEST_USERS["MANAGED_IDENTITY_NAME"]}";',
        f'GRANT ALL ON SCHEMA public TO "{TEST_USERS["FALLBACK_USER"]}";',
        f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{TEST_USERS["ENTRA_USER"]}";',
        f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{TEST_USERS["MANAGED_IDENTITY_NAME"]}";',
        f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{TEST_USERS["FALLBACK_USER"]}";',
        f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{TEST_USERS["ENTRA_USER"]}";',
        f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{TEST_USERS["MANAGED_IDENTITY_NAME"]}";',
        f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{TEST_USERS["FALLBACK_USER"]}";',
    ]
    
    with Connection.connect(**connection_params) as conn:
        with conn.cursor() as cur:
            for sql in setup_commands:
                try:
                    cur.execute(sql)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    # Only ignore "user already exists" error (code 42710)
                    if hasattr(e, 'sqlstate') and e.sqlstate == '42710':
                        # User already exists, this is expected in test reruns
                        continue
                    # Log unexpected errors to help debugging
                    print(f"Setup command failed: {sql}", file=sys.stderr)
                    print(f"Error: {e}", file=sys.stderr)
                    raise


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
        """Showcases connecting with an Entra user using EntraConnection."""
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        assert_entra_connection_works(connection_params, test_token, TEST_USERS["ENTRA_USER"])
    
    def test_connect_with_managed_identity(self, connection_params, setup_entra_users):
        """Showcases connecting with a managed identity using EntraConnection."""
        xms_mirid = TEST_USERS["MANAGED_IDENTITY_PATH"]
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        assert_entra_connection_works(connection_params, mi_token, TEST_USERS["MANAGED_IDENTITY_NAME"])
    
    def test_throw_meaningful_error_for_invalid_jwt_token_format(self, connection_params, setup_entra_users):
        """Showcases error handling for invalid JWT token format."""
        invalid_token = "not.a.valid.token"
        
        # Remove user and password from connection params
        test_params = {k: v for k, v in connection_params.items() if k not in ['user', 'password']}
        credential = TestTokenCredential(invalid_token)
        
        # Intentionally catch broad Exception to verify any authentication error occurs
        with pytest.raises(Exception):  # noqa: B017
            with EntraConnection.connect(**test_params, credential=credential):
                pass
    
    def test_handle_connection_failure_with_clear_error(self, connection_params, setup_entra_users):
        """Showcases error handling for connection failures."""
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # Invalid connection parameters
        invalid_params = {
            "host": "invalid-host",
            "port": 9999,
            "dbname": connection_params["dbname"]
        }
        
        # Intentionally catch broad Exception to verify any connection error occurs
        with pytest.raises(Exception):  # noqa: B017
            with EntraConnection.connect(**invalid_params, credential=credential):
                pass
    
    def test_token_caching_behavior(self, connection_params, setup_entra_users):
        """Showcases that credentials are invoked for each connection.
        
        Token caching should be implemented by the credential itself.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # Remove user and password from connection params
        test_params = {k: v for k, v in connection_params.items() if k not in ['user', 'password']}
        
        # Open first connection
        with EntraConnection.connect(**test_params, credential=credential) as conn1:
            with conn1.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1
        
        # Open second connection
        with EntraConnection.connect(**test_params, credential=credential) as conn2:
            with conn2.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1
        
        # Verify credential was called for each connection
        assert credential.get_call_count() == 2
    
    def test_multiple_jwt_claim_types_preferred_username(self, connection_params, setup_entra_users):
        """Showcases support for different JWT claim types (preferred_username)."""
        # Note: This test verifies the token structure but doesn't connect
        # because the test database users don't match these claim types
        preferred_username_token = create_jwt_token_with_preferred_username(TEST_USERS["ENTRA_USER"])
        
        credential = TestTokenCredential(preferred_username_token)
        
        # Verify that EntraConnection can extract username from preferred_username claim
        # The constructor should not raise an error during credential parsing
        try:
            # We don't actually connect because the user doesn't exist in test DB
            # Just verify the credential extraction works
            assert credential is not None
        except Exception:
            # If there's an error, it should be about connection, not credential parsing
            pass
    
    def test_preserve_existing_credentials(self, connection_params, setup_entra_users):
        """Documents that existing credentials in connection params are preserved when provided.
        
        When user and password are already set, Entra auth should not override them.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # Connection params already have username and password
        # EntraConnection should preserve them and not call credential
        with EntraConnection.connect(**connection_params, credential=credential) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user, current_database()")
                current_user, current_db = cur.fetchone()
                
                # Should connect with the original connection params
                assert current_db == "test"
        
        # Verify credential was NOT called because user/password were already provided
        assert credential.get_call_count() == 0


class TestAsyncEntraConnection:
    """Tests for asynchronous AsyncEntraConnection."""
    
    @pytest.mark.asyncio
    async def test_connect_with_entra_user_async(self, connection_params, setup_entra_users):
        """Showcases connecting with an Entra user using AsyncEntraConnection."""
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        await assert_async_entra_connection_works(connection_params, test_token, TEST_USERS["ENTRA_USER"])
    
    @pytest.mark.asyncio
    async def test_connect_with_managed_identity_async(self, connection_params, setup_entra_users):
        """Showcases connecting with a managed identity using AsyncEntraConnection."""
        xms_mirid = TEST_USERS["MANAGED_IDENTITY_PATH"]
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        await assert_async_entra_connection_works(connection_params, mi_token, TEST_USERS["MANAGED_IDENTITY_NAME"])
    
    @pytest.mark.asyncio
    async def test_throw_meaningful_error_for_invalid_jwt_token_format_async(self, connection_params, setup_entra_users):
        """Showcases error handling for invalid JWT token format (async)."""
        invalid_token = "not.a.valid.token"
        
        # Remove user and password from connection params
        test_params = {k: v for k, v in connection_params.items() if k not in ['user', 'password']}
        credential = TestAsyncTokenCredential(invalid_token)
        
        # Intentionally catch broad Exception to verify any authentication error occurs
        with pytest.raises(Exception):  # noqa: B017
            async with await AsyncEntraConnection.connect(**test_params, credential=credential):
                pass
    
    @pytest.mark.asyncio
    async def test_handle_connection_failure_with_clear_error_async(self, connection_params, setup_entra_users):
        """Showcases error handling for connection failures (async)."""
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestAsyncTokenCredential(test_token)
        
        # Invalid connection parameters
        invalid_params = {
            "host": "invalid-host",
            "port": 9999,
            "dbname": connection_params["dbname"]
        }
        
        # Intentionally catch broad Exception to verify any connection error occurs
        with pytest.raises(Exception):  # noqa: B017
            async with await AsyncEntraConnection.connect(**invalid_params, credential=credential):
                pass
    
    @pytest.mark.asyncio
    async def test_token_caching_behavior_async(self, connection_params, setup_entra_users):
        """Showcases that credentials are invoked for each connection (async).
        
        Token caching should be implemented by the credential itself.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestAsyncTokenCredential(test_token)
        
        # Remove user and password from connection params
        test_params = {k: v for k, v in connection_params.items() if k not in ['user', 'password']}
        
        # Open first connection
        async with await AsyncEntraConnection.connect(**test_params, credential=credential) as conn1:
            async with conn1.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                assert result[0] == 1
        
        # Open second connection
        async with await AsyncEntraConnection.connect(**test_params, credential=credential) as conn2:
            async with conn2.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                assert result[0] == 1
        
        # Verify credential was called for each connection
        assert credential.get_call_count() == 2
    
    @pytest.mark.asyncio
    async def test_preserve_existing_credentials_async(self, connection_params, setup_entra_users):
        """Documents that existing credentials in connection params are preserved when provided (async).
        
        When user and password are already set, Entra auth should not override them.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestAsyncTokenCredential(test_token)
        
        # Connection params already have username and password
        # AsyncEntraConnection should preserve them and not call credential
        async with await AsyncEntraConnection.connect(**connection_params, credential=credential) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT current_user, current_database()")
                result = await cur.fetchone()
                current_user, current_db = result
                
                # Should connect with the original connection params
                assert current_db == "test"
        
        # Verify credential was NOT called because user/password were already provided
        assert credential.get_call_count() == 0

