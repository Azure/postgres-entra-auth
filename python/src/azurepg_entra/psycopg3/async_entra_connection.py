# Copyright (c) Microsoft. All rights reserved.

from typing import Any

from azure.core.credentials_async import AsyncTokenCredential

try:
    from psycopg import AsyncConnection
except ImportError as e:
    # Provide a helpful error message if psycopg3 dependencies are missing
    raise ImportError(
        "psycopg3 dependencies are not installed. "
        "Install them with: pip install azurepg-entra[psycopg3]"
    ) from e

from azurepg_entra.core import get_entra_conninfo_async
from azurepg_entra.errors import (
    CredentialValueError,
    EntraConnectionValueError,
)

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # fallback for older Python


class AsyncEntraConnection(AsyncConnection[tuple[Any, ...]]):
    """Asynchronous connection class for using Entra authentication with Azure PostgreSQL."""

    @classmethod
    async def connect(cls, *args: Any, **kwargs: Any) -> "AsyncEntraConnection":
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
            raise CredentialValueError(
                "credential must be an AsyncTokenCredential for async connections"
            )

        # Check if we need to acquire Entra authentication info
        if not kwargs.get("user") or not kwargs.get("password"):
            try:
                entra_conninfo = await get_entra_conninfo_async(credential)
            except (Exception) as e:
                raise EntraConnectionValueError(
                    "Could not retrieve Entra credentials"
                ) from e
            # Always use the token password when Entra authentication is needed
            kwargs["password"] = entra_conninfo["password"]
            if not kwargs.get("user"):
                # If user isn't already set, use the username from the token
                kwargs["user"] = entra_conninfo["user"]
        return await super().connect(*args, **kwargs)
