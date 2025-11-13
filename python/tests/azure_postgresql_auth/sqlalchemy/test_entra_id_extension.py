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

from azure_postgresql_auth.sqlalchemy.async_entra_connection import (
    enable_entra_authentication_async,
)
from azure_postgresql_auth.sqlalchemy.entra_connection import (
    enable_entra_authentication,
)
from tests.azure_postgresql_auth.test_utils import (
    TEST_USERS,
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
    
    engine = create_engine(connection_url)
    with engine.connect() as conn:
        for sql in setup_commands:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                conn.rollback()
                # Only ignore "user already exists" error (code 42710)
                # SQLAlchemy wraps the original exception, so we need to check the original error
                orig_error = e.orig if hasattr(e, 'orig') else e
                if hasattr(orig_error, 'pgcode') and orig_error.pgcode == '42710':
                    # User already exists, this is expected in test reruns
                    continue
                # Log unexpected errors to help debugging
                print(f"Setup command failed: {sql}", file=sys.stderr)
                print(f"Error: {e}", file=sys.stderr)
                raise
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
        """Showcases connecting with an Entra user using enable_entra_authentication."""
        # Remove credentials from URL
        # Format: postgresql+psycopg2://user:pass@host:port/db -> postgresql+psycopg2://host:port/db
        parts = connection_url.split('@')
        base_url = f"postgresql+psycopg2://{parts[1]}"
        
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        assert_sqlalchemy_entra_works(base_url, test_token, TEST_USERS["ENTRA_USER"])
    
    def test_connect_with_managed_identity(self, connection_url, setup_entra_users):
        """Showcases connecting with a managed identity using enable_entra_authentication."""
        # Remove credentials from URL
        parts = connection_url.split('@')
        base_url = f"postgresql+psycopg2://{parts[1]}"
        
        xms_mirid = TEST_USERS["MANAGED_IDENTITY_PATH"]
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        assert_sqlalchemy_entra_works(base_url, mi_token, TEST_USERS["MANAGED_IDENTITY_NAME"])
    
    def test_throw_meaningful_error_for_invalid_jwt_token_format(self, connection_url, setup_entra_users):
        """Showcases error handling for invalid JWT token format."""
        invalid_token = "not.a.valid.token"
        credential = TestTokenCredential(invalid_token)
        
        # Remove credentials from URL
        parts = connection_url.split('@')
        base_url = f"postgresql+psycopg2://{parts[1]}"
        
        # Intentionally catch broad Exception to verify any authentication error occurs
        with pytest.raises(Exception):  # noqa: B017
            engine = create_engine(base_url, connect_args={"credential": credential})
            enable_entra_authentication(engine)
            with engine.connect():
                pass
            engine.dispose()
    
    def test_handle_connection_failure_with_clear_error(self, connection_url, setup_entra_users):
        """Showcases error handling for connection failures.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # Invalid connection URL
        parts = connection_url.split('@')
        dbname = parts[1].split('/')[-1]
        invalid_url = f"postgresql+psycopg2://invalid-host:9999/{dbname}"
        
        # Intentionally catch broad Exception to verify any connection error occurs
        with pytest.raises(Exception):  # noqa: B017
            engine = create_engine(invalid_url, connect_args={"credential": credential})
            enable_entra_authentication(engine)
            with engine.connect():
                pass
            engine.dispose()
    
    def test_token_caching_behavior(self, connection_url, setup_entra_users):
        """Showcases that credentials are invoked for each connection.
        
        Token caching should be implemented by the credential itself.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # Remove credentials from URL
        parts = connection_url.split('@')
        base_url = f"postgresql+psycopg2://{parts[1]}"
        
        # Create engine with Entra authentication
        engine = create_engine(base_url, connect_args={"credential": credential})
        enable_entra_authentication(engine)
        
        # Open first connection
        with engine.connect() as conn1:
            result = conn1.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        
        # Open second connection
        with engine.connect() as conn2:
            result = conn2.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        
        # Verify credential was called at least once
        # Note: SQLAlchemy connection pooling may reuse connections
        assert credential.get_call_count() >= 1
        
        engine.dispose()
    
    def test_preserve_existing_credentials(self, connection_url, setup_entra_users):
        """Documents that existing credentials in URL are preserved when provided.
        
        When user and password are already set in the URL, Entra auth should not override them.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # URL already has username and password
        # enable_entra_authentication should preserve them and not call credential
        engine = create_engine(connection_url, connect_args={"credential": credential})
        enable_entra_authentication(engine)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_user, current_database()"))
            current_user, current_db = result.fetchone()
            
            # Should connect with the original URL credentials
            assert current_db == "test"
        
        # Verify credential was NOT called because user/password were already in URL
        assert credential.get_call_count() == 0
        
        engine.dispose()
    

class TestAsyncSQLAlchemyEntraConnection:
    """Tests for asynchronous SQLAlchemy with enable_entra_authentication_async."""
    
    @pytest.mark.asyncio
    async def test_connect_with_entra_user_async(self, async_connection_url, setup_entra_users):
        """Showcases connecting with an Entra user using enable_entra_authentication_async."""
        # Remove credentials from URL
        parts = async_connection_url.split('@')
        base_url = f"postgresql+psycopg://{parts[1]}"
        
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        await assert_async_sqlalchemy_entra_works(base_url, test_token, TEST_USERS["ENTRA_USER"])
    
    @pytest.mark.asyncio
    async def test_connect_with_managed_identity_async(self, async_connection_url, setup_entra_users):
        """Showcases connecting with a managed identity using enable_entra_authentication_async."""
        # Remove credentials from URL
        parts = async_connection_url.split('@')
        base_url = f"postgresql+psycopg://{parts[1]}"
        
        xms_mirid = TEST_USERS["MANAGED_IDENTITY_PATH"]
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        await assert_async_sqlalchemy_entra_works(base_url, mi_token, TEST_USERS["MANAGED_IDENTITY_NAME"])
    
    @pytest.mark.asyncio
    async def test_throw_meaningful_error_for_invalid_jwt_token_format_async(self, async_connection_url, setup_entra_users):
        """Showcases error handling for invalid JWT token format (async)."""
        invalid_token = "not.a.valid.token"
        credential = TestTokenCredential(invalid_token)
        
        # Remove credentials from URL
        parts = async_connection_url.split('@')
        base_url = f"postgresql+psycopg://{parts[1]}"
        
        # Intentionally catch broad Exception to verify any authentication error occurs
        with pytest.raises(Exception):  # noqa: B017
            engine = create_async_engine(base_url, connect_args={"credential": credential})
            enable_entra_authentication_async(engine)
            async with engine.connect():
                pass
            await engine.dispose()
    
    @pytest.mark.asyncio
    async def test_handle_connection_failure_with_clear_error_async(self, async_connection_url, setup_entra_users):
        """Showcases error handling for connection failures (async)."""
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # Invalid connection URL
        parts = async_connection_url.split('@')
        dbname = parts[1].split('/')[-1]
        invalid_url = f"postgresql+psycopg://invalid-host:9999/{dbname}"
        
        # Intentionally catch broad Exception to verify any connection error occurs
        with pytest.raises(Exception):  # noqa: B017
            engine = create_async_engine(invalid_url, connect_args={"credential": credential})
            enable_entra_authentication_async(engine)
            async with engine.connect():
                pass
            await engine.dispose()
    
    @pytest.mark.asyncio
    async def test_token_caching_behavior_async(self, async_connection_url, setup_entra_users):
        """Showcases that credentials are invoked for each connection (async).
        
        Token caching should be implemented by the credential itself.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # Remove credentials from URL
        parts = async_connection_url.split('@')
        base_url = f"postgresql+psycopg://{parts[1]}"
        
        # Create async engine with Entra authentication
        engine = create_async_engine(base_url, connect_args={"credential": credential})
        enable_entra_authentication_async(engine)
        
        # Open first connection
        async with engine.connect() as conn1:
            result = await conn1.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row[0] == 1
        
        # Open second connection
        async with engine.connect() as conn2:
            result = await conn2.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row[0] == 1
        
        # Verify credential was called at least once
        # Note: SQLAlchemy connection pooling may reuse connections
        assert credential.get_call_count() >= 1
        
        await engine.dispose()
    
    @pytest.mark.asyncio
    async def test_preserve_existing_credentials_async(self, async_connection_url, setup_entra_users):
        """Documents that existing credentials in URL are preserved when provided (async).
        
        When user and password are already set in the URL, Entra auth should not override them.
        """
        test_token = create_valid_jwt_token(TEST_USERS["ENTRA_USER"])
        credential = TestTokenCredential(test_token)
        
        # URL already has username and password
        # enable_entra_authentication_async should preserve them and not call credential
        engine = create_async_engine(async_connection_url, connect_args={"credential": credential})
        enable_entra_authentication_async(engine)
        
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT current_user, current_database()"))
            row = result.fetchone()
            current_user, current_db = row
            
            # Should connect with the original URL credentials
            assert current_db == "test"
        
        # Verify credential was NOT called because user/password were already in URL
        assert credential.get_call_count() == 0
        
        await engine.dispose()

