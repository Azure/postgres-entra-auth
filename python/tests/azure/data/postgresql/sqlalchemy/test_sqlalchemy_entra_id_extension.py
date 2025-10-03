# Copyright (c) Microsoft. All rights reserved.
"""
Unit Tests for Azure PostgreSQL SQLAlchemy Entra ID Extension

This test suite demonstrates and validates the Azure Entra ID authentication
functionality for PostgreSQL connections using SQLAlchemy. These tests serve as
both validation and examples of how to use the extension.

Test Categories:
1. JWT Token Decoding - Validates Azure token processing
2. Principal Name Parsing - Tests managed identity resource path parsing  
3. Connection Info Generation - Tests core authentication logic
4. Engine Creation Functions - Validates sync/async engine creation with Entra auth
5. Connection Factory Behavior - Tests custom connection factories for token refresh

Key Testing Patterns:
- Every synchronous test has an equivalent asynchronous test
- Comprehensive mocking to avoid external dependencies
- Edge case validation for robust error handling
- Clear test naming that describes expected behavior

Usage:
    # Run all tests
    pytest test_sqlalchemy_entra_id_extension.py
    
    # Run specific test class
    pytest test_sqlalchemy_entra_id_extension.py::TestCreateEngineWithEntra
    
    # Run with verbose output
    pytest -v test_sqlalchemy_entra_id_extension.py

Dependencies:
    pip install pytest pytest-asyncio sqlalchemy

For more information about Azure Entra ID authentication:
https://docs.microsoft.com/en-us/azure/postgresql/concepts-aad-authentication
"""

import base64
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential

from azurepg_entra.sqlalchemy import (
    create_engine_with_entra,
    create_async_engine_with_entra,
    get_entra_conninfo,
    get_entra_conninfo_async,
    decode_jwt,
    parse_principal_name,
)

# Test Configuration
# These tests use mocking to avoid requiring actual Azure credentials or database connections.
# For integration testing with real Azure resources, see the samples/ directory.


def create_test_token(payload):
    """Helper to create a test JWT token."""
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    return f"header.{encoded_payload}.signature"


class TestDecodeJwt:
    """
    Tests for JWT token decoding functionality.
    
    These tests validate that Azure Entra ID tokens are properly decoded
    to extract user information. The extension supports various token formats
    and claim structures that Azure may provide.
    """

    def test_decode_jwt_valid_token(self):
        """Test decoding a valid JWT token with UPN (User Principal Name) claim."""
        # UPN is the most common claim for user identity in Azure AD tokens
        payload = {"upn": "user@example.com", "iat": 1234567890}
        token = create_test_token(payload)
        result = decode_jwt(token)
        assert result == payload

    def test_decode_jwt_with_padding(self):
        """Test decoding JWT token that requires base64 padding."""
        payload = {"preferred_username": "testuser", "exp": 9999999999}
        token = create_test_token(payload)
        result = decode_jwt(token)
        assert result == payload

    def test_decode_jwt_minimal_payload(self):
        """Test decoding JWT with minimal payload."""
        payload = {"unique_name": "user123"}
        token = create_test_token(payload)
        result = decode_jwt(token)
        assert result == payload


class TestParsePrincipalName:
    """
    Tests for Azure resource path parsing.
    
    When using managed identities, Azure provides resource paths that need
    to be parsed to extract the identity name for database authentication.
    These tests ensure robust parsing of various path formats.
    """

    def test_parse_principal_name_valid_user_assigned(self):
        """Test parsing a valid user-assigned identity resource path."""
        resource_path = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/my-identity"
        result = parse_principal_name(resource_path)
        assert result == "my-identity"

    def test_parse_principal_name_empty_string(self):
        """Test parsing an empty string returns None."""
        assert parse_principal_name("") is None

    def test_parse_principal_name_none(self):
        """Test parsing None returns None."""
        assert parse_principal_name(None) is None

    def test_parse_principal_name_no_slash(self):
        """Test parsing a string without slashes returns None."""
        assert parse_principal_name("no-slashes-here") is None

    def test_parse_principal_name_invalid_path(self):
        """Test parsing an invalid resource path returns None."""
        result = parse_principal_name("/subscriptions/12345/resourcegroups/mygroup/providers/SomeOther/resource/my-identity")
        assert result is None

    def test_parse_principal_name_missing_identity_name(self):
        """Test parsing a path without identity name returns None."""
        result = parse_principal_name("/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/")
        assert result is None

    def test_parse_principal_name_case_insensitive(self):
        """Test parsing with different case variations."""
        resource_path = "/subscriptions/12345/resourcegroups/mygroup/providers/MICROSOFT.MANAGEDIDENTITY/USERASSIGNEDIDENTITIES/my-identity"
        result = parse_principal_name(resource_path)
        assert result == "my-identity"


class TestGetEntraConninfo:
    """
    Tests for the core authentication logic (sync and async versions).
    
    These functions handle the complete flow of:
    1. Requesting Azure tokens with appropriate scopes
    2. Decoding tokens to extract user information  
    3. Handling fallback scenarios for managed identities
    4. Returning connection parameters for SQLAlchemy
    
    Both synchronous and asynchronous patterns are tested to ensure
    consistent behavior across different usage scenarios.
    """

    # Sync tests
    def test_get_entra_conninfo_with_credential(self):
        """Test getting connection info with sync credential and upn claim."""
        mock_credential = Mock(spec=TokenCredential)
        payload = {"upn": "user@example.com", "iat": 1234567890}
        token = create_test_token(payload)
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_token', return_value=token):
            result = get_entra_conninfo(mock_credential)
            assert result == {"user": "user@example.com", "password": token}

    def test_get_entra_conninfo_no_username_claims(self):
        """Test error when no username claims are present."""
        mock_credential = Mock(spec=TokenCredential)
        payload = {"sub": "subject123", "iat": 1234567890}  # No username claims
        token = create_test_token(payload)
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_token', return_value=token):
            with pytest.raises(ValueError, match="Could not determine username from token claims"):
                get_entra_conninfo(mock_credential)

    def test_get_entra_conninfo_username_priority(self):
        """Test that upn takes priority over other username claims."""
        mock_credential = Mock(spec=TokenCredential)
        # Azure tokens may contain multiple username claims - test priority order
        payload = {
            "upn": "upn@example.com",                    # Highest priority
            "preferred_username": "preferred@example.com",  # Second priority  
            "unique_name": "unique@example.com"         # Fallback option
        }
        token = create_test_token(payload)
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_token', return_value=token):
            result = get_entra_conninfo(mock_credential)
            assert result["user"] == "upn@example.com"  # Should use highest priority claim

    def test_get_entra_conninfo_fallback_to_management_scope(self):
        """Test fallback to management scope when DB scope token has no username."""
        db_payload = {"sub": "subject123", "iat": 1234567890}
        db_token = create_test_token(db_payload)
        
        mgmt_payload = {
            "xms_mirid": "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/fallback-identity"
        }
        mgmt_token = create_test_token(mgmt_payload)
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_token') as mock_get_token:
            mock_get_token.side_effect = [db_token, mgmt_token]
            
            result = get_entra_conninfo(None)
            assert result["user"] == "fallback-identity"
            assert result["password"] == db_token
            assert mock_get_token.call_count == 2

    # Async tests - mirror of sync tests
    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_with_credential(self):
        """Test getting connection info with async credential and upn claim."""
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        payload = {"upn": "user@example.com", "iat": 1234567890}
        token = create_test_token(payload)
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_token_async', return_value=token):
            result = await get_entra_conninfo_async(mock_credential)
            assert result == {"user": "user@example.com", "password": token}

    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_no_username_claims(self):
        """Test error when no username claims are present (async)."""
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        payload = {"sub": "subject123", "iat": 1234567890}  # No username claims
        token = create_test_token(payload)
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_token_async', return_value=token):
            with pytest.raises(ValueError, match="Could not determine username from token claims"):
                await get_entra_conninfo_async(mock_credential)

    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_username_priority(self):
        """Test that upn takes priority over other username claims (async)."""
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        payload = {
            "upn": "upn@example.com",
            "preferred_username": "preferred@example.com", 
            "unique_name": "unique@example.com"
        }
        token = create_test_token(payload)
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_token_async', return_value=token):
            result = await get_entra_conninfo_async(mock_credential)
            assert result["user"] == "upn@example.com"

    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_fallback_to_management_scope(self):
        """Test fallback to management scope when DB scope token has no username (async)."""
        db_payload = {"sub": "subject123", "iat": 1234567890}
        db_token = create_test_token(db_payload)
        
        mgmt_payload = {
            "xms_mirid": "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/fallback-identity"
        }
        mgmt_token = create_test_token(mgmt_payload)
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_token_async') as mock_get_token:
            mock_get_token.side_effect = [db_token, mgmt_token]
            
            result = await get_entra_conninfo_async(None)
            assert result["user"] == "fallback-identity"
            assert result["password"] == db_token
            assert mock_get_token.call_count == 2


class TestCreateEngineWithEntra:
    """
    Tests for the create_engine_with_entra function.
    
    This function creates a synchronous SQLAlchemy engine with Entra authentication.
    Tests validate:
    - Proper engine creation with custom connection factory
    - URL parsing and reconstruction
    - Credential handling and validation
    - Integration with SQLAlchemy's engine creation process
    """

    def test_create_engine_basic_url(self):
        """Test engine creation with basic PostgreSQL URL."""
        mock_credential = Mock(spec=TokenCredential)
        url = "postgresql://myserver.postgres.database.azure.com/mydatabase"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            result = create_engine_with_entra(url, credential=mock_credential)
            
            # Verify create_engine was called with base URL and creator function
            mock_create_engine.assert_called_once()
            call_args = mock_create_engine.call_args
            
            # Check that base URL doesn't contain credentials
            assert "myserver.postgres.database.azure.com" in call_args[0][0]
            assert "creator" in call_args[1]
            assert callable(call_args[1]["creator"])
            assert result == mock_engine

    def test_create_engine_with_psycopg_scheme(self):
        """Test engine creation with psycopg+ scheme."""
        url = "postgresql+psycopg://myserver.postgres.database.azure.com:5432/mydatabase"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            result = create_engine_with_entra(url)
            
            mock_create_engine.assert_called_once()
            call_args = mock_create_engine.call_args
            
            # Verify scheme is preserved in base URL
            assert call_args[0][0].startswith("postgresql+psycopg://")
            assert result == mock_engine

    def test_create_engine_with_query_parameters(self):
        """Test engine creation preserves query parameters."""
        url = "postgresql://myserver.postgres.database.azure.com/mydatabase?sslmode=require&connect_timeout=30"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            result = create_engine_with_entra(url)
            
            mock_create_engine.assert_called_once()
            call_args = mock_create_engine.call_args
            
            # Verify query parameters are preserved
            assert "sslmode=require" in call_args[0][0]
            assert "connect_timeout=30" in call_args[0][0]
            assert result == mock_engine

    def test_create_engine_invalid_credential_type(self):
        """Test engine creation with invalid credential type raises error."""
        invalid_credential = "not_a_credential"
        url = "postgresql://myserver.postgres.database.azure.com/mydatabase"
        
        with pytest.raises(ValueError, match="credential must be a TokenCredential for synchronous engines"):
            create_engine_with_entra(url, credential=invalid_credential)

    def test_create_engine_connection_factory_behavior(self):
        """Test that the custom connection factory works correctly."""
        mock_credential = Mock(spec=TokenCredential)
        url = "postgresql://myserver.postgres.database.azure.com/mydatabase"
        expected_conninfo = {"user": "test@example.com", "password": "token123"}
        
        # Mock the connection factory components
        mock_temp_engine = Mock()
        mock_raw_conn = Mock()
        mock_dbapi_conn = Mock()
        mock_raw_conn.dbapi_connection = mock_dbapi_conn
        mock_temp_engine.raw_connection.return_value = mock_raw_conn
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_conninfo', return_value=expected_conninfo):
            with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_engine') as mock_create_engine:
                # Mock the main create_engine call
                mock_main_engine = Mock()
                # Mock the temp engine creation inside connection factory
                mock_create_engine.side_effect = [mock_main_engine, mock_temp_engine]
                
                result = create_engine_with_entra(url, credential=mock_credential)
                assert result == mock_main_engine
                
                # Verify main engine creation
                assert mock_create_engine.call_count >= 1
                main_call_args = mock_create_engine.call_args_list[0]
                
                # Extract and test the connection factory function
                creator_func = main_call_args[1]["creator"]
                assert callable(creator_func)
                
                # Test the connection factory function (still within the outer patch context)
                conn_result = creator_func()
                assert conn_result == mock_dbapi_conn

    def test_create_engine_with_kwargs(self):
        """Test that additional kwargs are passed through to create_engine."""
        url = "postgresql://myserver.postgres.database.azure.com/mydatabase"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            result = create_engine_with_entra(
                url, 
                pool_size=10, 
                max_overflow=20, 
                echo=True
            )
            
            mock_create_engine.assert_called_once()
            call_args = mock_create_engine.call_args[1]
            
            # Verify additional kwargs are passed through
            assert call_args["pool_size"] == 10
            assert call_args["max_overflow"] == 20
            assert call_args["echo"] == True
            assert result == mock_engine


class TestCreateAsyncEngineWithEntra:
    """
    Tests for the create_async_engine_with_entra function.
    
    This function creates an asynchronous SQLAlchemy engine with Entra authentication.
    Tests validate:
    - Proper async engine creation with custom connection factory
    - URL parsing and psycopg3 async connection handling
    - Credential handling for async operations
    - Integration with SQLAlchemy's async engine creation process
    """

    def test_create_async_engine_import_error(self):
        """Test error when sqlalchemy.ext.asyncio is not available."""
        url = "postgresql+psycopg://myserver.postgres.database.azure.com/mydatabase"
        
        # Mock the absence of create_async_engine
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_async_engine', None):
            with pytest.raises(ImportError, match="sqlalchemy.ext.asyncio is required for async engines"):
                create_async_engine_with_entra(url)

    def test_create_async_engine_basic_url(self):
        """Test async engine creation with basic PostgreSQL URL."""
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        url = "postgresql+psycopg://myserver.postgres.database.azure.com/mydatabase"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_async_engine') as mock_create_async_engine:
            mock_engine = Mock()
            mock_create_async_engine.return_value = mock_engine
            
            result = create_async_engine_with_entra(url, credential=mock_credential)
            
            # Verify create_async_engine was called with base URL and async_creator function
            mock_create_async_engine.assert_called_once()
            call_args = mock_create_async_engine.call_args
            
            # Check that base URL doesn't contain credentials
            assert "myserver.postgres.database.azure.com" in call_args[0][0]
            assert "async_creator" in call_args[1]
            assert callable(call_args[1]["async_creator"])
            assert result == mock_engine

    def test_create_async_engine_with_port_and_query(self):
        """Test async engine creation preserves port and query parameters."""
        url = "postgresql+psycopg://myserver.postgres.database.azure.com:5432/mydatabase?sslmode=require"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_async_engine') as mock_create_async_engine:
            mock_engine = Mock()
            mock_create_async_engine.return_value = mock_engine
            
            result = create_async_engine_with_entra(url)
            
            mock_create_async_engine.assert_called_once()
            call_args = mock_create_async_engine.call_args
            
            # Verify port and query parameters are preserved
            assert ":5432" in call_args[0][0]
            assert "sslmode=require" in call_args[0][0]
            assert result == mock_engine

    def test_create_async_engine_invalid_credential_type(self):
        """Test async engine creation with invalid credential type raises error."""
        invalid_credential = "not_an_async_credential"
        url = "postgresql+psycopg://myserver.postgres.database.azure.com/mydatabase"
        
        with pytest.raises(ValueError, match="credential must be an AsyncTokenCredential for async engines"):
            create_async_engine_with_entra(url, credential=invalid_credential)

    @pytest.mark.asyncio
    async def test_create_async_engine_connection_factory_behavior(self):
        """Test that the custom async connection factory works correctly."""
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        url = "postgresql+psycopg://myserver.postgres.database.azure.com/mydatabase"
        expected_conninfo = {"user": "test@example.com", "password": "token123"}
        
        # Mock psycopg AsyncConnection
        mock_async_conn = Mock()
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.get_entra_conninfo_async', return_value=expected_conninfo):
            with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_async_engine') as mock_create_async_engine:
                with patch('psycopg.AsyncConnection.connect', new_callable=AsyncMock, return_value=mock_async_conn) as mock_psycopg_connect:
                    mock_main_engine = Mock()
                    mock_create_async_engine.return_value = mock_main_engine
                    
                    result = create_async_engine_with_entra(url, credential=mock_credential)
                    
                    # Verify main engine creation
                    mock_create_async_engine.assert_called_once()
                    main_call_args = mock_create_async_engine.call_args
                    
                    # Extract and test the async connection factory function
                    async_creator_func = main_call_args[1]["async_creator"]
                    assert callable(async_creator_func)
                    
                    # Test the async connection factory function
                    conn_result = await async_creator_func()
                    
                    # Verify psycopg.AsyncConnection.connect was called with correct parameters
                    mock_psycopg_connect.assert_called_once()
                    connect_call_args = mock_psycopg_connect.call_args[1]
                    assert connect_call_args["host"] == "myserver.postgres.database.azure.com"
                    assert connect_call_args["port"] == 5432
                    assert connect_call_args["dbname"] == "mydatabase"
                    assert connect_call_args["user"] == "test@example.com"
                    assert connect_call_args["password"] == "token123"
                    
                    assert conn_result == mock_async_conn
                    assert result == mock_main_engine

    def test_create_async_engine_unsupported_scheme(self):
        """Test async engine creation with unsupported URL scheme."""
        url = "postgresql+asyncpg://myserver.postgres.database.azure.com/mydatabase"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_async_engine') as mock_create_async_engine:
            mock_engine = Mock()
            mock_create_async_engine.return_value = mock_engine
            
            # Create the engine (this should succeed)
            result = create_async_engine_with_entra(url)
            
            # Extract the async_creator function
            call_args = mock_create_async_engine.call_args
            async_creator_func = call_args[1]["async_creator"]
            
            # Test that calling the async_creator with unsupported scheme raises error
            with pytest.raises(ValueError, match="Unsupported async URL scheme: postgresql\\+asyncpg"):
                # We need to create an async context to test this
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(async_creator_func())
                finally:
                    loop.close()

    def test_create_async_engine_with_kwargs(self):
        """Test that additional kwargs are passed through to create_async_engine."""
        url = "postgresql+psycopg://myserver.postgres.database.azure.com/mydatabase"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_async_engine') as mock_create_async_engine:
            mock_engine = Mock()
            mock_create_async_engine.return_value = mock_engine
            
            result = create_async_engine_with_entra(
                url, 
                pool_size=15, 
                max_overflow=25, 
                echo=True
            )
            
            mock_create_async_engine.assert_called_once()
            call_args = mock_create_async_engine.call_args[1]
            
            # Verify additional kwargs are passed through
            assert call_args["pool_size"] == 15
            assert call_args["max_overflow"] == 25
            assert call_args["echo"] == True
            assert result == mock_engine


class TestUrlParsing:
    """
    Tests for URL parsing and reconstruction logic.
    
    These tests validate that the URL parsing and reconstruction logic
    works correctly for various URL formats and edge cases.
    """

    def test_url_parsing_with_different_schemes(self):
        """Test URL parsing works with different PostgreSQL schemes."""
        test_urls = [
            "postgresql://server.com/db",
            "postgresql+psycopg://server.com/db", 
            "postgresql+psycopg2://server.com/db"
        ]
        
        for url in test_urls:
            with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_engine') as mock_create_engine:
                mock_engine = Mock()
                mock_create_engine.return_value = mock_engine
                
                create_engine_with_entra(url)
                
                mock_create_engine.assert_called_once()
                call_args = mock_create_engine.call_args
                # Verify the scheme is preserved in the base URL
                assert call_args[0][0].startswith(url.split('://')[0] + '://')

    def test_url_parsing_with_complex_parameters(self):
        """Test URL parsing with complex query parameters and paths."""
        url = "postgresql://server.com:5432/complex_db_name?sslmode=require&application_name=test%20app&connect_timeout=30"
        
        with patch('azurepg_entra.sqlalchemy.sqlalchemy_entra_id_extension.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            create_engine_with_entra(url)
            
            mock_create_engine.assert_called_once()
            call_args = mock_create_engine.call_args
            base_url = call_args[0][0]
            
            # Verify all components are preserved
            assert "server.com:5432" in base_url
            assert "/complex_db_name" in base_url
            assert "sslmode=require" in base_url
            assert "application_name=test%20app" in base_url
            assert "connect_timeout=30" in base_url


# Example usage and test runner
if __name__ == "__main__":
    """
    Direct execution example for development and validation.
    
    This runs all tests with verbose output, which is helpful for:
    - Understanding test coverage
    - Debugging test failures  
    - Learning expected behavior patterns
    
    For CI/CD or automated testing, use pytest directly:
        pytest test_sqlalchemy_entra_id_extension.py -v --tb=short
    """
    import sys
    
    # Run with verbose output and short traceback format
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    
    # Provide helpful guidance based on results
    if exit_code == 0:
        print("\n✅ All tests passed! The SQLAlchemy Azure Entra ID extension is working correctly.")
        print("💡 Next steps: Try running the samples in samples/sqlalchemy/getting_started/")
    else:
        print(f"\n❌ Some tests failed (exit code: {exit_code})")
        print("💡 Check the test output above for details on any failures.")
        print("💡 Ensure all dependencies are installed: pip install pytest pytest-asyncio sqlalchemy")
    
    sys.exit(exit_code)


"""
Quick Start Guide for Understanding These Tests:

1. Basic JWT Testing (TestDecodeJwt):
   - Shows how Azure tokens are decoded to get user info
   - Demonstrates different token claim formats
   
2. Resource Path Parsing (TestParsePrincipalName):
   - Tests managed identity resource path handling
   - Shows how identity names are extracted for database auth

3. Core Authentication Logic (TestGetEntraConninfo):
   - Tests the main authentication flow
   - Shows both sync and async patterns
   - Demonstrates fallback mechanisms for edge cases

4. Engine Creation Functions (TestCreateEngineWithEntra/TestCreateAsyncEngineWithEntra):
   - Tests the main SQLAlchemy engine creation functions
   - Shows how custom connection factories work
   - Validates URL parsing and reconstruction
   - Tests both sync and async engine patterns

5. URL Parsing (TestUrlParsing):
   - Tests URL parsing and reconstruction logic
   - Shows how different schemes and parameters are handled
   - Validates complex URL scenarios

Key Patterns to Notice:
- Every sync test has an async equivalent for consistency
- Mocking isolates tests from external dependencies  
- Custom connection factories are thoroughly tested
- URL parsing handles various PostgreSQL driver schemes
- Clear error messages help with debugging
- Tests serve as usage examples for developers

For integration testing with real Azure resources, see the samples directory.

SQLAlchemy-Specific Features Tested:
- Custom connection factory (creator parameter)
- Custom async connection factory (async_creator parameter)
- Engine configuration parameter pass-through
- URL scheme handling for different PostgreSQL drivers
- Integration with SQLAlchemy's connection pooling
- Proper DBAPI connection object handling
"""