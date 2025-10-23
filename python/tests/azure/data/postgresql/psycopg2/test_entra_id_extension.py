# Copyright (c) Microsoft. All rights reserved.

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

from azurepg_entra.psycopg2.entra_connection import EntraConnection
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
    
    with psycopg2.connect(connection_dsn) as conn:
        with conn.cursor() as cur:
            for sql in setup_commands:
                try:
                    cur.execute(sql)
                    conn.commit()
                except Exception:
                    # Ignore errors if user already exists
                    conn.rollback()


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
        """Showcases connecting with an Entra user using EntraConnection.
        Demonstrates: End-to-end connection with token-based authentication.
        """
        test_token = create_valid_jwt_token("test@example.com")
        assert_entra_connection_works(connection_dsn, test_token, "test@example.com")
    
    def test_connect_with_managed_identity(self, connection_dsn, setup_entra_users):
        """Showcases connecting with a managed identity using EntraConnection.
        Demonstrates: End-to-end MI authentication with token-based authentication.
        """
        xms_mirid = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/managed-identity"
        mi_token = create_jwt_token_with_xms_mirid(xms_mirid)
        assert_entra_connection_works(connection_dsn, mi_token, "managed-identity")
    
    def test_connect_with_kwargs_override(self, connection_dsn, setup_entra_users):
        """Showcases that kwargs can override DSN parameters.
        Demonstrates: Parameter precedence (kwargs > DSN).
        """
        # Parse DSN but we'll override user via kwargs
        dsn_params = parse_dsn(connection_dsn)
        host = dsn_params['host']
        port = dsn_params['port']
        dbname = dsn_params['dbname']
        
        base_dsn = f"host={host} port={port} dbname={dbname}"
        
        # Create token for fallback user
        test_token = create_valid_jwt_token("fallback@example.com")
        credential = TestTokenCredential(test_token)
        
        # Connect - credential will extract username from token
        with EntraConnection(base_dsn, credential=credential) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user")
                current_user = cur.fetchone()[0]
                assert current_user == "fallback@example.com"
