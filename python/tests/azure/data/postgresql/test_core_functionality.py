# Copyright (c) Microsoft. All rights reserved.
import jwt
import pytest
from unittest.mock import AsyncMock, Mock, patch
from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential

from azurepg_entra.core import (
    decode_jwt,
    parse_principal_name,
    get_entra_conninfo,
    get_entra_conninfo_async,
)

def create_test_token(payload):
    """Helper to create a test JWT token."""
    return jwt.encode(payload, key="", algorithm="none")

class TestJwtParsing:
    def test_decode_jwt_with_upn(self):
        payload = {"upn": "user@example.com"}
        token = create_test_token(payload)
        result = decode_jwt(token)
        assert result == payload

    def test_decode_jwt_with_preferred_username(self):
        payload = {"preferred_username": "testuser@example.com"}
        token = create_test_token(payload)
        result = decode_jwt(token)
        assert result == payload

    def test_decode_jwt_invalid_format_returns_none(self):
        result = decode_jwt("invalid.token")
        assert result is None

    def test_parse_principal_name_valid_path(self):
        path = "/subscriptions/12345/resourcegroups/mygroup/providers/Microsoft.ManagedIdentity/userAssignedIdentities/my-identity"
        result = parse_principal_name(path)
        assert result == "my-identity"

    def test_parse_principal_name_invalid_path_returns_none(self):
        assert parse_principal_name("") is None
        assert parse_principal_name(None) is None
        assert parse_principal_name("/invalid/path") is None


class TestEntraAuthentication:
    def test_get_entra_conninfo_with_upn(self):
        mock_credential = Mock(spec=TokenCredential)
        payload = {"upn": "user@example.com"}
        token = create_test_token(payload)
        
        with patch('azurepg_entra.core.get_entra_token', return_value=token):
            result = get_entra_conninfo(mock_credential)
            assert result == {"user": "user@example.com", "password": token}

    def test_get_entra_conninfo_no_username_throws(self):
        mock_credential = Mock(spec=TokenCredential)
        payload = {"sub": "subject123"}
        token = create_test_token(payload)
        
        with patch('azurepg_entra.core.get_entra_token', return_value=token):
            with pytest.raises(ValueError, match="Could not determine username from token claims"):
                get_entra_conninfo(mock_credential)

    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_with_upn(self):
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        payload = {"upn": "user@example.com"}
        token = create_test_token(payload)
        
        with patch('azurepg_entra.core.get_entra_token_async', return_value=token):
            result = await get_entra_conninfo_async(mock_credential)
            assert result == {"user": "user@example.com", "password": token}

    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_no_username_throws(self):
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        payload = {"sub": "subject123"}
        token = create_test_token(payload)
        
        with patch('azurepg_entra.core.get_entra_token_async', return_value=token):
            with pytest.raises(ValueError, match="Could not determine username from token claims"):
                await get_entra_conninfo_async(mock_credential)


if __name__ == "__main__":
    import sys
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)