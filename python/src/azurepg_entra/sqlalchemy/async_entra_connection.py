from typing import Any

from azure.core.credentials import TokenCredential
from azure.core.credentials_async import AsyncTokenCredential
from sqlalchemy import event
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.asyncio import AsyncEngine

from azurepg_entra.core import get_entra_conninfo
from azurepg_entra.errors import (
    CredentialValueError,
    EntraConnectionValueError,
    ScopePermissionError,
    TokenDecodeError,
    UsernameExtractionError,
)


def enable_entra_authentication_async(engine: AsyncEngine) -> None:
    """
    Enable Azure Entra ID authentication for an async SQLAlchemy engine.

    This function registers an event listener that automatically provides
    Entra ID credentials for each database connection if they are not already set.

    Args:
        engine: The async SQLAlchemy Engine to enable Entra authentication for
    """

    @event.listens_for(engine.sync_engine, "do_connect")
    def provide_token_async(
        dialect: Dialect, conn_rec: Any, cargs: Any, cparams: dict[str, Any]
    ) -> None:
        """Event handler that provides Entra credentials for each async connection.

        Raises:
            CredentialValueError: If the provided credential is not a valid TokenCredential.
            EntraConnectionValueError: If Entra connection credentials cannot be retrieved
        """
        credential = cparams.get("credential", None)
        if credential and not isinstance(
            credential, (AsyncTokenCredential, TokenCredential)
        ):
            raise CredentialValueError(
                "credential must be an AsyncTokenCredential or TokenCredential for async connections"
            )
        # Check if credentials are already present
        has_user = "user" in cparams
        has_password = "password" in cparams

        # Only get Entra credentials if user or password is missing
        if not has_user or not has_password:
            try:
                # Cast to TokenCredential since SQLAlchemy events are synchronous
                sync_credential: TokenCredential | None = (
                    credential
                    if isinstance(credential, TokenCredential) or credential is None
                    else None
                )
                entra_creds = get_entra_conninfo(sync_credential)
            except (
                TokenDecodeError,
                UsernameExtractionError,
                ScopePermissionError,
            ) as e:
                print(repr(e))
                raise EntraConnectionValueError(
                    "Could not retrieve Entra credentials"
                ) from e
            # Only update missing credentials
            if not has_user and "user" in entra_creds:
                cparams["user"] = entra_creds["user"]
            if not has_password and "password" in entra_creds:
                cparams["password"] = entra_creds["password"]
