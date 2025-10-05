# Copyright (c) Microsoft. All rights reserved.

from typing import Any
try:
    from typing import Self 
except ImportError:
    from typing_extensions import Self  # fallback for older Python

from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential
from azurepg_entra.core import get_entra_conninfo, get_entra_conninfo_async
from psycopg import AsyncConnection, Connection

class SyncEntraConnection(Connection[tuple[Any, ...]]):
    """Synchronous connection class for using Entra authentication with Azure PostgreSQL."""
    
    @classmethod
    def connect(cls, *args: Any, **kwargs: Any) -> Self:
        """Establishes a synchronous PostgreSQL connection using Entra authentication.

        The method checks for provided credentials. If the 'user' or 'password' are not set
        in the keyword arguments, it acquires them from Entra via the provided or default credential.

        Parameters:
            *args: Positional arguments to be forwarded to the parent connection method.
            **kwargs: Keyword arguments including optional 'credential', and optionally 'user' and 'password'.

        Returns:
            SyncEntraConnection: An open synchronous connection to the PostgreSQL database.

        Raises:
            ValueError: If the provided credential is not a valid TokenCredential.
        """
        credential = kwargs.pop("credential", None)
        if credential and not isinstance(credential, (TokenCredential)):
            raise ValueError("credential must be a TokenCredential for sync connections")
        
        # Check if we need to acquire Entra authentication info
        if not kwargs.get("user") or not kwargs.get("password"):
            entra_conninfo = get_entra_conninfo(credential)
            # Always use the token password when Entra authentication is needed
            kwargs["password"] = entra_conninfo["password"]
            if not kwargs.get("user"):
                # If user isn't already set, use the username from the token
                kwargs["user"] = entra_conninfo["user"]
        return super().connect(*args, **kwargs)


class AsyncEntraConnection(AsyncConnection[tuple[Any, ...]]):
    """Asynchronous connection class for using Entra authentication with Azure PostgreSQL."""
    
    @classmethod
    async def connect(cls, *args: Any, **kwargs: Any) -> Self:
        """Establishes an asynchronous PostgreSQL connection using Entra authentication.

        The method checks for provided credentials. If the 'user' or 'password' are not set
        in the keyword arguments, it acquires them from Entra via the provided or default credential.

        Parameters:
            *args: Positional arguments to be forwarded to the parent connection method.
            **kwargs: Keyword arguments including optional 'credential', and optionally 'user' and 'password'.

        Returns:
            AsyncEntraConnection: An open asynchronous connection to the PostgreSQL database.

        Raises:
            ValueError: If the provided credential is not a valid AsyncTokenCredential.
        """
        credential = kwargs.pop("credential", None)
        if credential and not isinstance(credential, (AsyncTokenCredential)):
            raise ValueError("credential must be an AsyncTokenCredential for async connections")
        
        # Check if we need to acquire Entra authentication info
        if not kwargs.get("user") or not kwargs.get("password"):
            entra_conninfo = await get_entra_conninfo_async(credential)
            # Always use the token password when Entra authentication is needed
            kwargs["password"] = entra_conninfo["password"]
            if not kwargs.get("user"):
                # If user isn't already set, use the username from the token
                kwargs["user"] = entra_conninfo["user"]
        return await super().connect(*args, **kwargs)