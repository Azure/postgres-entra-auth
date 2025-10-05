import logging
import jwt
from typing import Any, cast
from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity import DefaultAzureCredential as DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

logger = logging.getLogger(__name__)
AZURE_DB_FOR_POSTGRES_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"

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
    
def decode_jwt(token: str) -> dict[str, Any] | None:
    """Decodes a JWT token to extract its payload claims.

    Parameters:
        token (str): The JWT token string in the standard three-part format.

    Returns:
        dict | None: A dictionary containing the claims extracted from the token payload, 
                     or None if the token is invalid.
    """
    try:
        # Decode without verification since we only need the payload claims
        # Azure tokens are already validated by the credential provider
        return cast(dict[str, Any], jwt.decode(token, options={"verify_signature": False}))
    except Exception:
        return None

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
    if not db_claims:
        raise ValueError("Invalid DB token format")
    xms_mirid = db_claims.get("xms_mirid")
    username = (
        parse_principal_name(xms_mirid) if isinstance(xms_mirid, str) else None
        or db_claims.get("upn")
        or db_claims.get("preferred_username")
        or db_claims.get("unique_name")
    )

    if not username:
        # Fall back to management scope ONLY to discover username
        mgmt_token = get_entra_token(credential, AZURE_MANAGEMENT_SCOPE)
        mgmt_claims = decode_jwt(mgmt_token)
        if not mgmt_claims:
            raise ValueError("Invalid management token format")
        xms_mirid = mgmt_claims.get("xms_mirid")
        username = (
            parse_principal_name(xms_mirid) if isinstance(xms_mirid, str) else None
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
    if not db_claims:
        raise ValueError("Invalid DB token format")
    xms_mirid = db_claims.get("xms_mirid")
    username = (
        parse_principal_name(xms_mirid) if isinstance(xms_mirid, str) else None
        or db_claims.get("upn")
        or db_claims.get("preferred_username")
        or db_claims.get("unique_name")
    )

    if not username:
        mgmt_token = await get_entra_token_async(credential, AZURE_MANAGEMENT_SCOPE)
        mgmt_claims = decode_jwt(mgmt_token)
        if not mgmt_claims:
            raise ValueError("Invalid management token format")
        xms_mirid = mgmt_claims.get("xms_mirid")
        username = (
            parse_principal_name(xms_mirid) if isinstance(xms_mirid, str) else None
            or mgmt_claims.get("upn")
            or mgmt_claims.get("preferred_username")
            or mgmt_claims.get("unique_name")
        )

    if not username:
        raise ValueError("Could not determine username from token claims.")

    return {"user": username, "password": db_token}