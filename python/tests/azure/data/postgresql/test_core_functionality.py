# Copyright (c) Microsoft. All rights reserved.
import base64
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential

from azurepg_entra.core import (
    decode_jwt,
    get_entra_conninfo,
    get_entra_conninfo_async,
    parse_principal_name,
)
from azurepg_entra.errors import TokenDecodeError, UsernameExtractionError


def create_test_token(payload):
    """Helper to create a test JWT token manually."""
    # Create a simple JWT-like token with header.payload.signature format
    header = {"alg": "none", "typ": "JWT"}
    header_encoded = (
        base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    )
    payload_encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    )
    signature = ""
    return f"{header_encoded}.{payload_encoded}.{signature}"


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

    def test_decode_jwt_invalid_format_raises_exception(self):
        with pytest.raises(TokenDecodeError, match="Invalid JWT token format"):
            decode_jwt("invalid.token")

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

        with patch("azurepg_entra.core.get_entra_token", return_value=token):
            result = get_entra_conninfo(mock_credential)
            assert result == {"user": "user@example.com", "password": token}

    def test_get_entra_conninfo_no_username_throws(self):
        mock_credential = Mock(spec=TokenCredential)
        payload = {"sub": "subject123"}
        token = create_test_token(payload)

        # Mock both the DB token and the management token to have no username claims
        with patch("azurepg_entra.core.get_entra_token", return_value=token):
            with pytest.raises(
                UsernameExtractionError,
                match="Could not determine username from token claims",
            ):
                get_entra_conninfo(mock_credential)

    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_with_upn(self):
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        payload = {"upn": "user@example.com"}
        token = create_test_token(payload)

        with patch("azurepg_entra.core.get_entra_token_async", return_value=token):
            result = await get_entra_conninfo_async(mock_credential)
            assert result == {"user": "user@example.com", "password": token}

    @pytest.mark.asyncio
    async def test_get_entra_conninfo_async_no_username_throws(self):
        mock_credential = AsyncMock(spec=AsyncTokenCredential)
        payload = {"sub": "subject123"}
        token = create_test_token(payload)

        # Mock both the DB token and the management token to have no username claims
        with patch("azurepg_entra.core.get_entra_token_async", return_value=token):
            with pytest.raises(
                UsernameExtractionError,
                match="Could not determine username from token claims",
            ):
                await get_entra_conninfo_async(mock_credential)


if __name__ == "__main__":
    import sys

    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    sys.exit(exit_code)
