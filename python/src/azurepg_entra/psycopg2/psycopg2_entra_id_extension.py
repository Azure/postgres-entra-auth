# Copyright (c) Microsoft. All rights reserved.
"""
Connection classes for using Entra auth with Azure DB for PostgreSQL (psycopg2 + aiopg version).
This module provides both synchronous and asynchronous connection classes that allow you to connect to Azure DB for PostgreSQL
using Entra authentication. Uses psycopg2 for sync connections and aiopg for async connections.

Sync Example (psycopg2):
    from azurepg_entra.psycopg2 import connect_with_entra
    
    conn = connect_with_entra(host="myserver.postgres.database.azure.com", dbname="mydatabase")

Async Example (aiopg):
    from azurepg_entra.psycopg2 import connect_with_entra_async
    
    conn = await connect_with_entra_async(host="myserver.postgres.database.azure.com", dbname="mydatabase")

Note: Async functionality requires aiopg: pip install aiopg
"""

import base64
import json
import logging
from typing import Optional

import psycopg2
try:
    import aiopg
except ImportError:
    aiopg = None

from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity import DefaultAzureCredential as DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

AZURE_DB_FOR_POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"

logger = logging.getLogger(__name__)

async def get_entra_token_async(credential: AsyncTokenCredential | None, scope: str) -> str:
    """Asynchronously acquires an Entra authentication token for Azure PostgreSQL.

    Parameters:
        credential (AsyncTokenCredential or None): Asynchronous credential used to obtain the token.
            If None, the default Azure credentials are used.
        scope (str): The scope for the token request.

    Returns:
        str: The acquired authentication token to be used as the database password.
    """
    logger.info("Acquiring Entra token for postgres password")

    credential = credential or AsyncDefaultAzureCredential()
    async with credential:
        cred = await credential.get_token(scope)
        return cred.token

def get_entra_token(credential: TokenCredential | None, scope: str) -> str:
    """Acquires an Entra authentication token for Azure PostgreSQL synchronously.

    Parameters:
        credential (TokenCredential or None): Credential object used to obtain the token. 
            If None, the default Azure credentials are used.
        scope (str): The scope for the token request.

    Returns:
        str: The acquired authentication token to be used as the database password.
    """
    logger.info("Acquiring Entra token for postgres password")

    credential = credential or DefaultAzureCredential()
    cred = credential.get_token(scope)
    return cred.token

def decode_jwt(token):
    """Decodes a JWT token to extract its payload claims.

    Parameters:
        token (str): The JWT token string in the standard three-part format.

    Returns:
        dict: A dictionary containing the claims extracted from the token payload.
    """
    payload = token.split(".")[1]
    padding = "=" * (4 - len(payload) % 4)
    decoded_payload = base64.urlsafe_b64decode(payload + padding)
    return json.loads(decoded_payload)

def parse_principal_name(xms_mirid: str) -> str | None:
    """Parses the principal name from an Azure resource path.

    Parameters:
        xms_mirid (str): The xms_mirid claim value containing the Azure resource path.

    Returns:
        str | None: The extracted principal name, or None if parsing fails.
    """
    if not xms_mirid:
        return None
    
    # Parse the xms_mirid claim which looks like
    # /subscriptions/{subId}/resourcegroups/{resourceGroup}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{principalName}
    last_slash_index = xms_mirid.rfind('/')
    if last_slash_index == -1:
        return None

    beginning = xms_mirid[:last_slash_index]
    principal_name = xms_mirid[last_slash_index + 1:]

    if not principal_name or not beginning.lower().endswith("providers/microsoft.managedidentity/userassignedidentities"):
        return None

    return principal_name

def get_entra_conninfo(credential: TokenCredential | None) -> dict[str, str]:
    """Synchronously obtains connection information from Entra authentication for Azure PostgreSQL.

    Parameters:
        credential (TokenCredential or None): The credential used for token acquisition.
            If None, the default Azure credentials are used.

    Returns:
        dict[str, str]: A dictionary with 'user' and 'password' keys containing the username and token.
    
    Raises:
        ValueError: If the username cannot be extracted from the token payload.
    """
    credential = credential or DefaultAzureCredential()

    # Always get the DB-scope token for password
    db_token = get_entra_token(credential, AZURE_DB_FOR_POSTGRES_SCOPE)
    db_claims = decode_jwt(db_token)
    username = (
        parse_principal_name(db_claims.get("xms_mirid"))
        or db_claims.get("upn")
        or db_claims.get("preferred_username")
        or db_claims.get("unique_name")
    )

    if not username:
        # Fall back to management scope ONLY to discover username
        mgmt_token = get_entra_token(credential, AZURE_MANAGEMENT_SCOPE)
        mgmt_claims = decode_jwt(mgmt_token)
        username = (
            parse_principal_name(mgmt_claims.get("xms_mirid"))
            or mgmt_claims.get("upn")
            or mgmt_claims.get("preferred_username")
            or mgmt_claims.get("unique_name")
        )

    if not username:
        raise ValueError(
            "Could not determine username from token claims. "
            "Ensure the identity has the proper Azure AD attributes."
        )

    return {"user": username, "password": db_token}

async def get_entra_conninfo_async(credential: AsyncTokenCredential | None) -> dict[str, str]:
    """Asynchronously obtains connection information from Entra authentication for Azure PostgreSQL.

    Parameters:
        credential (AsyncTokenCredential or None): The async credential used for token acquisition.
            If None, the default Azure credentials are used.

    Returns:
        dict[str, str]: A dictionary with 'user' and 'password' keys containing the username and token.
    
    Raises:
        ValueError: If the username cannot be extracted from the token payload.
    """
    credential = credential or AsyncDefaultAzureCredential()

    db_token = await get_entra_token_async(credential, AZURE_DB_FOR_POSTGRES_SCOPE)
    db_claims = decode_jwt(db_token)
    username = (
        parse_principal_name(db_claims.get("xms_mirid"))
        or db_claims.get("upn")
        or db_claims.get("preferred_username")
        or db_claims.get("unique_name")
    )

    if not username:
        mgmt_token = await get_entra_token_async(credential, AZURE_MANAGEMENT_SCOPE)
        mgmt_claims = decode_jwt(mgmt_token)
        username = (
            parse_principal_name(mgmt_claims.get("xms_mirid"))
            or mgmt_claims.get("upn")
            or mgmt_claims.get("preferred_username")
            or mgmt_claims.get("unique_name")
        )

    if not username:
        raise ValueError("Could not determine username from token claims.")

    return {"user": username, "password": db_token}

def connect_with_entra(credential: Optional[TokenCredential] = None, **kwargs) -> psycopg2.extensions.connection:
    """Creates a synchronous PostgreSQL connection using Entra authentication.

    This function handles Azure Entra ID token acquisition and creates a psycopg2 connection
    with the appropriate user and password parameters.

    Parameters:
        credential (TokenCredential, optional): The credential used for token acquisition.
            If None, the default Azure credentials are used.
        **kwargs: Additional connection parameters (host, port, dbname, etc.)

    Returns:
        psycopg2.extensions.connection: An open synchronous connection to PostgreSQL.

    Raises:
        ValueError: If the provided credential is not a valid TokenCredential.
    """
    credential = credential or DefaultAzureCredential()
    if credential and not isinstance(credential, TokenCredential):
        raise ValueError("credential must be a TokenCredential for synchronous connections")
    
    # Check if we need to acquire Entra authentication info
    if not kwargs.get("user") or not kwargs.get("password"):
        entra_conninfo = get_entra_conninfo(credential)
        # Always use the token password when Entra authentication is needed
        kwargs["password"] = entra_conninfo["password"]
        if not kwargs.get("user"):
            # If user isn't already set, use the username from the token
            kwargs["user"] = entra_conninfo["user"]
    
    return psycopg2.connect(**kwargs)

async def connect_with_entra_async(credential: Optional[AsyncTokenCredential] = None, **kwargs):
    """Creates an asynchronous PostgreSQL connection using Entra authentication.

    This function handles Azure Entra ID token acquisition and creates an aiopg connection
    with the appropriate user and password parameters.

    Parameters:
        credential (AsyncTokenCredential, optional): The async credential used for token acquisition.
            If None, the default Azure credentials are used.
        **kwargs: Additional connection parameters (host, port, dbname, etc.)

    Returns:
        aiopg connection: An open asynchronous connection to PostgreSQL.

    Raises:
        ImportError: If aiopg is not installed.
        ValueError: If the provided credential is not a valid AsyncTokenCredential.
    """
    if aiopg is None:
        raise ImportError(
            "aiopg is required for async connections. Install with: pip install aiopg"
        )
    
    credential = credential or AsyncDefaultAzureCredential()    
    if credential and not isinstance(credential, AsyncTokenCredential):
        raise ValueError("credential must be an AsyncTokenCredential for async connections")
    
    # Check if we need to acquire Entra authentication info
    if not kwargs.get("user") or not kwargs.get("password"):
        entra_conninfo = await get_entra_conninfo_async(credential)
        # Always use the token password when Entra authentication is needed
        kwargs["password"] = entra_conninfo["password"]
        if not kwargs.get("user"):
            # If user isn't already set, use the username from the token
            kwargs["user"] = entra_conninfo["user"]
    
    return await aiopg.connect(**kwargs)