from sqlalchemy import Engine, event
from azure.core.credentials import TokenCredential
from azurepg_entra.errors import CredentialValueError, TokenDecodeError, UsernameExtractionError, EntraConnectionValueError, ScopePermissionError
from azurepg_entra.core import get_entra_conninfo

def enable_entra_authentication(engine: Engine):
    """
    Enable Azure Entra ID authentication for a SQLAlchemy engine.
    
    This function registers an event listener that automatically provides
    Entra ID credentials for each database connection if they are not already set.
    
    Args:
        engine: The SQLAlchemy Engine to enable Entra authentication for
    """
    
    @event.listens_for(engine, "do_connect")
    def provide_token(dialect, conn_rec, cargs, cparams):
        """Event handler that provides Entra credentials for each connection.
        
        Raises:
            CredentialValueError: If the provided credential is not a valid TokenCredential.
            EntraConnectionValueError: If Entra connection credentials cannot be retrieved
        """
        credential = cparams.get("credential", None)
        if credential and not isinstance(credential, (TokenCredential)):
            raise CredentialValueError("credential must be a TokenCredential for sync connections")
        # Check if credentials are already present
        has_user = "user" in cparams
        has_password = "password" in cparams
        
        # Only get Entra credentials if user or password is missing
        if not has_user or not has_password:
            try:
                entra_creds = get_entra_conninfo(credential)
            except (TokenDecodeError, UsernameExtractionError, ScopePermissionError) as e:
                print(repr(e))
                raise EntraConnectionValueError("Could not retrieve Entra credentials") from e
            # Only update missing credentials
            if not has_user and "user" in entra_creds:
                cparams["user"] = entra_creds["user"]
            if not has_password and "password" in entra_creds:
                cparams["password"] = entra_creds["password"]