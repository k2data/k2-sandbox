"""K2 Sandbox - A Python SDK for running code in isolated Docker containers."""

__version__ = "0.1.0"

from k2_sandbox.sandbox import Sandbox
from k2_sandbox.exceptions import (
    K2Exception,
    SandboxException,
    TimeoutException,
    APIError,
    AuthenticationError,
    RateLimitException,
    NotFoundError,
    FilesystemError,
    ProcessError,
    TerminalError,
    CodeExecutionError,
)
