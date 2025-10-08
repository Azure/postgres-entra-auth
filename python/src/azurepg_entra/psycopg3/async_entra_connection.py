# Copyright (c) Microsoft. All rights reserved.

from psycopg import AsyncConnection
from azure.core.credentials_async import AsyncTokenCredential
from azurepg_entra.errors import TokenDecodeError, UsernameExtractionError, EntraConnectionValueError, CredentialValueError, ScopePermissionError
from azurepg_entra.core import get_entra_conninfo_async

from typing import Any
try:
    from typing import Self 
except ImportError:
    from typing_extensions import Self  # fallback for older Python

class AsyncEntraConnection(AsyncConnection[tuple[Any, ...]]):
    """Asynchronous connection class for using Entra authentication with Azure PostgreSQL."""
    
    @classmethod
    async def connect(cls, *args: Any, **kwargs: Any) -> Self:
        """Establishes an asynchronous PostgreSQL connection using Entra authentication.

        This method automatically acquires Azure Entra ID credentials when user or password 
        are not provided in the connection parameters. Authentication errors are printed to 
        console for debugging purposes.

        Parameters:
            *args: Positional arguments to be forwarded to the parent connection method.
            **kwargs: Keyword arguments including:
                - credential (AsyncTokenCredential, optional): Async Azure credential for token acquisition.
                - user (str, optional): Database username. If not provided, extracted from Entra token.
                - password (str, optional): Database password. If not provided, uses Entra access token.

        Returns:
            AsyncEntraConnection: An open asynchronous connection to the PostgreSQL database.

        Raises:
            CredentialValueError: If the provided credential is not a valid AsyncTokenCredential.
            EntraConnectionValueError: If Entra connection credentials are invalid.
        """
        credential = kwargs.pop("credential", None)
        if credential and not isinstance(credential, (AsyncTokenCredential)):
            raise CredentialValueError("credential must be an AsyncTokenCredential for async connections")
        
        # Check if we need to acquire Entra authentication info
        if not kwargs.get("user") or not kwargs.get("password"):
            try:
                entra_conninfo = await get_entra_conninfo_async(credential)
            except (TokenDecodeError, UsernameExtractionError, ScopePermissionError) as e:
                print(repr(e))
                raise EntraConnectionValueError("Could not retrieve Entra credentials") from e
            # Always use the token password when Entra authentication is needed
            kwargs["password"] = entra_conninfo["password"]
            if not kwargs.get("user"):
                # If user isn't already set, use the username from the token
                kwargs["user"] = entra_conninfo["user"]
        return await super().connect(*args, **kwargs)