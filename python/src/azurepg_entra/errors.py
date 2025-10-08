class EntraIdBaseError(Exception):
    """Base class for all custom exceptions in the project."""

    pass


class TokenDecodeError(EntraIdBaseError):
    """Raised when a token value is invalid."""

    pass


class UsernameExtractionError(EntraIdBaseError):
    """Raised when username cannot be extracted from token."""

    pass


class CredentialValueError(EntraIdBaseError):
    """Raised when token credential is invalid."""

    pass


class EntraConnectionValueError(EntraIdBaseError):
    """Raised when Entra connection credentials are invalid."""

    pass


class ScopePermissionError(EntraIdBaseError):
    """Raised when the provided scope does not have sufficient permissions."""

    pass
