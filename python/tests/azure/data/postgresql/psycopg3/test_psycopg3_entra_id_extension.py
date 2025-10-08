# Copyright (c) Microsoft. All rights reserved.
import pytest
from unittest.mock import AsyncMock, Mock, patch
from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential
from azurepg_entra.errors import CredentialValueError

from azurepg_entra.psycopg3 import (
    AsyncEntraConnection,
    EntraConnection,
)

class TestSyncConnection:
    def test_connect_with_existing_credentials(self):
        """Test that existing user/password credentials are used without fetching Entra credentials."""
        kwargs = {"host": "localhost", "user": "existing_user", "password": "existing_password"}
        
        with patch('psycopg.Connection.connect') as mock_connect:
            mock_connection = Mock()
            mock_connect.return_value = mock_connection
            
            result = EntraConnection.connect(**kwargs)
            
            assert result == mock_connection
            call_args = mock_connect.call_args[1]
            assert call_args["user"] == "existing_user"
            assert call_args["password"] == "existing_password"

    def test_connect_with_entra_credential(self):
        """Test that Entra credentials are fetched and used when no user/password provided."""
        mock_credential = Mock(spec=TokenCredential)
        kwargs = {"host": "localhost", "credential": mock_credential}
        
        with patch('azurepg_entra.psycopg3.entra_connection.get_entra_conninfo', 
                   return_value={"user": "test@example.com", "password": "token123"}):
            with patch('psycopg.Connection.connect') as mock_connect:
                mock_connection = Mock()
                mock_connect.return_value = mock_connection
                
                result = EntraConnection.connect(**kwargs)
                
                assert result == mock_connection
                call_args = mock_connect.call_args[1]
                assert call_args["user"] == "test@example.com"
                assert call_args["password"] == "token123"

    def test_connect_invalid_credential_type_throws(self):
        """Test that invalid credential type raises CredentialValueError."""
        with pytest.raises(CredentialValueError, match="credential must be a TokenCredential for sync connections"):
            EntraConnection.connect(host="localhost", credential="invalid")


class TestAsyncConnection:
    @pytest.mark.asyncio
    async def test_connect_with_existing_credentials(self):
        """Test that existing user/password credentials are used without fetching Entra credentials (async)."""
        kwargs = {"host": "localhost", "user": "existing_user", "password": "existing_password"}
        
        with patch('psycopg.AsyncConnection.connect', new_callable=AsyncMock) as mock_connect:
            mock_connection = Mock()
            mock_connect.return_value = mock_connection
            
            result = await AsyncEntraConnection.connect(**kwargs)
            
            assert result == mock_connection
            call_args = mock_connect.call_args[1]
            assert call_args["user"] == "existing_user"
            assert call_args["password"] == "existing_password"

    @pytest.mark.asyncio
    async def test_connect_with_entra_credential(self):
        """Test that Entra credentials are fetched and used when no user/password provided (async)."""
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        kwargs = {"host": "localhost", "credential": mock_credential}
        
        with patch('azurepg_entra.psycopg3.async_entra_connection.get_entra_conninfo_async', 
                   new_callable=AsyncMock, return_value={"user": "test@example.com", "password": "token123"}):
            with patch('psycopg.AsyncConnection.connect', new_callable=AsyncMock) as mock_connect:
                mock_connection = Mock()
                mock_connect.return_value = mock_connection
                
                result = await AsyncEntraConnection.connect(**kwargs)
                
                assert result == mock_connection
                call_args = mock_connect.call_args[1]
                assert call_args["user"] == "test@example.com"
                assert call_args["password"] == "token123"

    @pytest.mark.asyncio
    async def test_connect_invalid_credential_type_throws(self):
        """Test that invalid credential type raises CredentialValueError (async)."""
        with pytest.raises(CredentialValueError, match="credential must be an AsyncTokenCredential for async connections"):
            await AsyncEntraConnection.connect(host="localhost", credential="invalid")


if __name__ == "__main__":
    import sys
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)