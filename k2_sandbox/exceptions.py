"""Exceptions for the K2 Sandbox SDK."""


class K2Exception(Exception):
    """Base class for all exceptions raised by the K2 Sandbox SDK."""

    pass


class SandboxException(K2Exception):
    """General error related to sandbox operations."""

    pass


class TimeoutException(K2Exception):
    """Raised when an operation times out."""

    pass


class APIError(K2Exception):
    """Base class for errors originating from the K2 Sandbox API."""

    pass


class AuthenticationError(APIError):
    """Raised due to an invalid or missing API key."""

    pass


class RateLimitException(APIError):
    """Raised when the API rate limit is exceeded."""

    pass


class NotFoundError(K2Exception):
    """Raised when a requested resource is not found."""

    pass


class FilesystemError(SandboxException):
    """Raised during a failed filesystem operation within the sandbox."""

    pass


class ProcessError(SandboxException):
    """Raised during a failed process execution or management operation."""

    pass


class TerminalError(SandboxException):
    """Raised during a failed PTY interaction."""

    pass


class CodeExecutionError(SandboxException):
    """Raised when there's an error during code execution in the sandbox."""

    pass
