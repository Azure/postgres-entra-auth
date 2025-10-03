# Copyright (c) Microsoft. All rights reserved.
"""
Unit Tests for Azure PostgreSQL psycopg Entra ID Extension

This test suite demonstrates and validates the Azure Entra ID authentication
functionality for PostgreSQL connections using psycopg3. These tests serve as
both validation and examples of how to use the extension.

Test Categories:
1. JWT Token Decoding - Validates Azure token processing
2. Principal Name Parsing - Tests managed identity resource path parsing  
3. Connection Info Generation - Tests core authentication logic
4. Sync/Async Connection Classes - Validates connection establishment

Key Testing Patterns:
- Every synchronous test has an equivalent asynchronous test
- Comprehensive mocking to avoid external dependencies
- Edge case validation for robust error handling
- Clear test naming that describes expected behavior

Usage:
    # Run all tests
    pytest test_psycopg_entra_id_extension.py
    
    # Run specific test class
    pytest test_psycopg_entra_id_extension.py::TestSyncEntraConnection
    
    # Run with verbose output
    pytest -v test_psycopg_entra_id_extension.py

Dependencies:
    pip install pytest pytest-asyncio

For more information about Azure Entra ID authentication:
https://docs.microsoft.com/en-us/azure/postgresql/concepts-aad-authentication
"""

import base64
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential

from azurepg_entra.psycopg3 import (
    AsyncEntraConnection,
    SyncEntraConnection,
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
    4. Returning connection parameters for psycopg
    
    Both synchronous and asynchronous patterns are tested to ensure
    consistent behavior across different usage scenarios.
    """

    # Sync tests
    def test_get_entra_conninfo_with_credential(self):
        """Test getting connection info with sync credential and upn claim."""
        mock_credential = Mock(spec=TokenCredential)
        payload = {"upn": "user@example.com", "iat": 1234567890}
        token = create_test_token(payload)
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_token', return_value=token):
            result = get_entra_conninfo(mock_credential)
            assert result == {"user": "user@example.com", "password": token}

    def test_get_entra_conninfo_no_username_claims(self):
        """Test error when no username claims are present."""
        mock_credential = Mock(spec=TokenCredential)
        payload = {"sub": "subject123", "iat": 1234567890}  # No username claims
        token = create_test_token(payload)
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_token', return_value=token):
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
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_token', return_value=token):
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
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_token') as mock_get_token:
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
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_token_async', return_value=token):
            result = await get_entra_conninfo_async(mock_credential)
            assert result == {"user": "user@example.com", "password": token}

    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_no_username_claims(self):
        """Test error when no username claims are present (async)."""
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        payload = {"sub": "subject123", "iat": 1234567890}  # No username claims
        token = create_test_token(payload)
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_token_async', return_value=token):
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
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_token_async', return_value=token):
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
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_token_async') as mock_get_token:
            mock_get_token.side_effect = [db_token, mgmt_token]
            
            result = await get_entra_conninfo_async(None)
            assert result["user"] == "fallback-identity"
            assert result["password"] == db_token
            assert mock_get_token.call_count == 2


class TestSyncEntraConnection:
    """
    Tests for the SyncEntraConnection class.
    
    This class extends psycopg's Connection to automatically handle
    Azure Entra ID authentication. Tests validate:
    - Proper credential handling and validation
    - Fallback to standard authentication when credentials exist
    - Integration with the underlying psycopg connection logic
    """

    def test_connect_with_user_and_password(self):
        """Test connection when user and password are already provided (passthrough)."""
        kwargs = {
            "host": "localhost",
            "port": 5432,
            "user": "existing_user",
            "password": "existing_password",
            "dbname": "testdb"
        }
        
        with patch('psycopg.Connection.connect') as mock_super_connect:
            mock_connection = Mock()
            mock_super_connect.return_value = mock_connection
            
            result = SyncEntraConnection.connect(**kwargs)
            
            mock_super_connect.assert_called_once()
            call_args = mock_super_connect.call_args[1]
            assert call_args["user"] == "existing_user"
            assert call_args["password"] == "existing_password"
            assert "credential" not in call_args
            assert result == mock_connection

    def test_connect_without_user_password_with_credential(self):
        """Test connection using Entra authentication with provided credential."""
        mock_credential = Mock(spec=TokenCredential)
        kwargs = {
            "host": "localhost", 
            "port": 5432,
            "dbname": "testdb",
            "credential": mock_credential
        }
        
        expected_conninfo = {"user": "test@example.com", "password": "token123"}
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_conninfo', return_value=expected_conninfo) as mock_get_conninfo:
            with patch('psycopg.Connection.connect') as mock_super_connect:
                mock_connection = Mock()
                mock_super_connect.return_value = mock_connection
                
                result = SyncEntraConnection.connect(**kwargs)
                
                mock_get_conninfo.assert_called_once_with(mock_credential)
                mock_super_connect.assert_called_once()
                call_args = mock_super_connect.call_args[1]
                assert call_args["user"] == "test@example.com"
                assert call_args["password"] == "token123"
                assert "credential" not in call_args
                assert result == mock_connection

    def test_connect_invalid_credential_type(self):
        """Test connection with invalid credential type raises error."""
        invalid_credential = "not_a_credential"
        kwargs = {"host": "localhost", "credential": invalid_credential}
        
        with pytest.raises(ValueError, match="credential must be a TokenCredential for synchronous connections"):
            SyncEntraConnection.connect(**kwargs)


class TestAsyncEntraConnection:
    """
    Tests for the AsyncEntraConnection class.
    
    This class extends psycopg's AsyncConnection to automatically handle
    Azure Entra ID authentication in async contexts. Tests mirror the
    synchronous tests to ensure consistent behavior between sync/async
    usage patterns.
    """

    @pytest.mark.asyncio
    async def test_connect_with_user_and_password(self):
        """Test connection when user and password are already provided (passthrough)."""
        kwargs = {
            "host": "localhost",
            "port": 5432,
            "user": "existing_user",
            "password": "existing_password",
            "dbname": "testdb"
        }
        
        with patch('psycopg.AsyncConnection.connect', new_callable=AsyncMock) as mock_super_connect:
            mock_connection = Mock()
            mock_super_connect.return_value = mock_connection
            
            result = await AsyncEntraConnection.connect(**kwargs)
            
            mock_super_connect.assert_called_once()
            call_args = mock_super_connect.call_args[1]
            assert call_args["user"] == "existing_user"
            assert call_args["password"] == "existing_password"
            assert "credential" not in call_args
            assert result == mock_connection

    @pytest.mark.asyncio
    async def test_connect_without_user_password_with_credential(self):
        """Test connection using Entra authentication with provided credential."""
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        kwargs = {
            "host": "localhost", 
            "port": 5432,
            "dbname": "testdb",
            "credential": mock_credential
        }
        
        expected_conninfo = {"user": "test@example.com", "password": "token123"}
        
        with patch('azurepg_entra.psycopg3.psycopg3_entra_id_extension.get_entra_conninfo_async', return_value=expected_conninfo) as mock_get_conninfo:
            with patch('psycopg.AsyncConnection.connect', new_callable=AsyncMock) as mock_super_connect:
                mock_connection = Mock()
                mock_super_connect.return_value = mock_connection
                
                result = await AsyncEntraConnection.connect(**kwargs)
                
                mock_get_conninfo.assert_called_once_with(mock_credential)
                mock_super_connect.assert_called_once()
                call_args = mock_super_connect.call_args[1]
                assert call_args["user"] == "test@example.com"
                assert call_args["password"] == "token123"
                assert "credential" not in call_args
                assert result == mock_connection

    @pytest.mark.asyncio
    async def test_connect_invalid_credential_type(self):
        """Test connection with invalid credential type raises error."""
        invalid_credential = "not_a_credential"
        kwargs = {"host": "localhost", "credential": invalid_credential}
        
        with pytest.raises(ValueError, match="credential must be an AsyncTokenCredential for async connections"):
            await AsyncEntraConnection.connect(**kwargs)


# Example usage and test runner
if __name__ == "__main__":
    """
    Direct execution example for development and validation.
    
    This runs all tests with verbose output, which is helpful for:
    - Understanding test coverage
    - Debugging test failures  
    - Learning expected behavior patterns
    
    For CI/CD or automated testing, use pytest directly:
        pytest test_psycopg_entra_id_extension.py -v --tb=short
    """
    import sys
    
    # Run with verbose output and short traceback format
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    
    # Provide helpful guidance based on results
    if exit_code == 0:
        print("\n✅ All tests passed! The Azure Entra ID extension is working correctly.")
        print("💡 Next steps: Try running the samples in samples/psycopg/getting_started/")
    else:
        print(f"\n❌ Some tests failed (exit code: {exit_code})")
        print("💡 Check the test output above for details on any failures.")
        print("💡 Ensure all dependencies are installed: pip install pytest pytest-asyncio")
    
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

4. Connection Classes (TestSyncEntraConnection/TestAsyncEntraConnection):
   - Tests the customer-facing connection classes
   - Shows how existing psycopg code can be easily adapted
   - Validates credential handling and error cases

Key Patterns to Notice:
- Every sync test has an async equivalent for consistency
- Mocking isolates tests from external dependencies  
- Clear error messages help with debugging
- Tests serve as usage examples for developers

For integration testing with real Azure resources, see the samples directory.
"""