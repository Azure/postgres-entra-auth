# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Integration tests showcasing Entra ID authentication with PostgreSQL Docker instance.
These tests demonstrate token-based authentication for psycopg2.
"""

import pytest

try:
    import psycopg2
    from psycopg2.extensions import parse_dsn
except ImportError as e:
    # Provide a helpful error message if psycopg2 dependencies are missing
    raise ImportError(
        "psycopg2 dependencies are not installed. "
        "Install them with: pip install azurepg-entra[psycopg2]"
    ) from e

from testcontainers.postgres import PostgresContainer

from azure_postgresql_auth.psycopg2.entra_connection import EntraConnection
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
def connection_dsn(postgres_container) -> str:
    """Fixture to get DSN connection string from the container."""
    return (
        f"host={postgres_container.get_container_host_ip()} "
        f"port={postgres_container.get_exposed_port(5432)} "
        f"dbname={postgres_container.dbname} "
        f"user={postgres_container.username} "
        f"password={postgres_container.password}"
    )


@pytest.fixture(scope="module")
def setup_entra_users(connection_dsn):
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
    
    with psycopg2.connect(connection_dsn) as conn:
        with conn.cursor() as cur:
            for sql in setup_commands:
                try:
                    cur.execute(sql)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    # Only ignore "user already exists" error (code 42710)
                    if hasattr(e, 'pgcode') and e.pgcode == '42710':
                        # User already exists, this is expected in test reruns
                        continue
                    # Log unexpected errors to help debugging
                    import sys
                    print(f"Setup command failed: {sql}", file=sys.stderr)
                    print(f"Error: {e}", file=sys.stderr)
                    raise


def assert_entra_connection_works(
    connection_dsn: str,
    token: str,
    expected_username: str
) -> None:
    """Helper to test Entra connection works end-to-end.
    
    Verifies username extraction, connection establishment, and database operations.
    """
    # Parse DSN and remove user/password
    dsn_params = parse_dsn(connection_dsn)
    dsn_params.pop('user', None)
    dsn_params.pop('password', None)
    
    # Build DSN without credentials
    base_dsn = ' '.join([f"{k}={v}" for k, v in dsn_params.items()])
    
    # Add credential
    credential = TestTokenCredential(token)
    
    # Connect using EntraConnection
    with EntraConnection(base_dsn, credential=credential) as conn:
        with conn.cursor() as cur:
            # Test basic operations
            cur.execute("SELECT current_user, current_database()")
            current_user, current_db = cur.fetchone()
            
            assert current_user == expected_username
            assert current_db == "test"


class TestPsycopg2EntraConnection:
    """Tests for psycopg2 EntraConnection."""
    
    def test_connect_with_entra_user(self, connection_dsn, setup_entra_users):
        """Showcases connecting with an Entra user using EntraConnection."""
        test_token = create_valid_jwt_token(TEST_USERS['ENTRA_USER'])
        assert_entra_connection_works(connection_dsn, test_token, TEST_USERS['ENTRA_USER'])
    
    def test_connect_with_managed_identity(self, connection_dsn, setup_entra_users):
        """Showcases connecting with a managed identity using EntraConnection."""
        mi_token = create_jwt_token_with_xms_mirid(TEST_USERS['MANAGED_IDENTITY_PATH'])
        assert_entra_connection_works(connection_dsn, mi_token, TEST_USERS['MANAGED_IDENTITY_NAME'])
    
    def test_connect_with_kwargs_override(self, connection_dsn, setup_entra_users):
        """Showcases that kwargs can override DSN parameters."""
        # Parse DSN but we'll override user via kwargs
        dsn_params = parse_dsn(connection_dsn)
        host = dsn_params['host']
        port = dsn_params['port']
        dbname = dsn_params['dbname']
        
        base_dsn = f"host={host} port={port} dbname={dbname}"
        
        # Create token for fallback user
        test_token = create_valid_jwt_token(TEST_USERS['FALLBACK_USER'])
        credential = TestTokenCredential(test_token)
        
        # Connect - credential will extract username from token
        with EntraConnection(base_dsn, credential=credential) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user")
                current_user = cur.fetchone()[0]
                assert current_user == TEST_USERS['FALLBACK_USER']
    
    def test_throw_meaningful_error_for_invalid_jwt_token_format(self, connection_dsn, setup_entra_users):
        """Showcases error handling for invalid JWT token format."""
        invalid_token = "not.a.valid.token"
        
        # Parse DSN and remove user/password
        dsn_params = parse_dsn(connection_dsn)
        dsn_params.pop('user', None)
        dsn_params.pop('password', None)
        base_dsn = ' '.join([f"{k}={v}" for k, v in dsn_params.items()])
        
        credential = TestTokenCredential(invalid_token)
        
        # Intentionally catch broad Exception to verify any authentication error occurs
        with pytest.raises(Exception):  # noqa: B017
            with EntraConnection(base_dsn, credential=credential):
                pass
    
    def test_handle_connection_failure_with_clear_error(self, connection_dsn, setup_entra_users):
        """Showcases error handling for connection failures."""
        test_token = create_valid_jwt_token(TEST_USERS['ENTRA_USER'])
        credential = TestTokenCredential(test_token)
        
        # Invalid connection parameters
        dsn_params = parse_dsn(connection_dsn)
        invalid_dsn = f"host=invalid-host port=9999 dbname={dsn_params['dbname']}"
        
        # Intentionally catch broad Exception to verify any connection error occurs
        with pytest.raises(Exception):  # noqa: B017
            with EntraConnection(invalid_dsn, credential=credential):
                pass
    
    def test_token_caching_behavior(self, connection_dsn, setup_entra_users):
        """Showcases that credentials are invoked for each connection.
        
        Token caching should be implemented by the credential itself.
        """
        test_token = create_valid_jwt_token(TEST_USERS['ENTRA_USER'])
        credential = TestTokenCredential(test_token)
        
        # Parse DSN and remove user/password
        dsn_params = parse_dsn(connection_dsn)
        dsn_params.pop('user', None)
        dsn_params.pop('password', None)
        base_dsn = ' '.join([f"{k}={v}" for k, v in dsn_params.items()])
        
        # Open first connection
        with EntraConnection(base_dsn, credential=credential) as conn1:
            with conn1.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1
        
        # Open second connection
        with EntraConnection(base_dsn, credential=credential) as conn2:
            with conn2.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1
        
        # Verify credential was called for each connection
        assert credential.get_call_count() == 2
    
    
    def test_preserve_existing_credentials(self, connection_dsn, setup_entra_users):
        """Documents that existing credentials in DSN are preserved when provided.
        
        When user and password are already set, Entra auth should not override them.
        """
        test_token = create_valid_jwt_token(TEST_USERS['ENTRA_USER'])
        credential = TestTokenCredential(test_token)
        
        # DSN already has username and password
        # EntraConnection should preserve them and not call credential
        with EntraConnection(connection_dsn, credential=credential) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user, current_database()")
                current_user, current_db = cur.fetchone()
                
                # Should connect with the original DSN credentials
                assert current_db == "test"
        
        # Verify credential was NOT called because user/password were already provided
        assert credential.get_call_count() == 0
