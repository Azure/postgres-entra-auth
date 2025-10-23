# Copyright (c) Microsoft. All rights reserved.

"""
Common utility functions and test credentials for PostgreSQL Entra ID integration tests.
"""

import base64
import json
from datetime import datetime, timedelta, timezone

from azure.core.credentials import AccessToken, TokenCredential
from azure.core.credentials_async import AsyncTokenCredential


def create_base64_url_string(input_str: str) -> str:
    """Create a base64url encoded string."""
    encoded = base64.urlsafe_b64encode(input_str.encode()).decode()
    return encoded.rstrip('=')


def create_valid_jwt_token(username: str) -> str:
    """Create a fake JWT token with a UPN claim."""
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "upn": username,
        "iat": 1234567890,
        "exp": 9999999999
    }
    
    header_encoded = create_base64_url_string(json.dumps(header))
    payload_encoded = create_base64_url_string(json.dumps(payload))
    
    return f"{header_encoded}.{payload_encoded}.fake-signature"


def create_jwt_token_with_xms_mirid(xms_mirid: str) -> str:
    """Create a fake JWT token with an xms_mirid claim for managed identity."""
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "xms_mirid": xms_mirid,
        "iat": 1234567890,
        "exp": 9999999999
    }
    
    header_encoded = create_base64_url_string(json.dumps(header))
    payload_encoded = create_base64_url_string(json.dumps(payload))
    
    return f"{header_encoded}.{payload_encoded}.fake-signature"


class TestTokenCredential(TokenCredential):
    """Test token credential for synchronous operations."""
    
    def __init__(self, token: str):
        self._token = token
    
    def get_token(self, *scopes, **kwargs) -> AccessToken:
        """Return a fake access token."""
        expires_on = datetime.now(timezone.utc) + timedelta(hours=1)
        return AccessToken(self._token, int(expires_on.timestamp()))


class TestAsyncTokenCredential(AsyncTokenCredential):
    """Test token credential for asynchronous operations."""
    
    def __init__(self, token: str):
        self._token = token
    
    async def get_token(self, *scopes, **kwargs) -> AccessToken:
        """Return a fake access token asynchronously."""
        expires_on = datetime.now(timezone.utc) + timedelta(hours=1)
        return AccessToken(self._token, int(expires_on.timestamp()))
