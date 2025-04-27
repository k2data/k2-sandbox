"""Data models for the K2 Sandbox SDK."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import base64


@dataclass
class Logs:
    """Represents stdout and stderr logs from code execution."""

    stdout: List[Dict[str, Union[str, bool, float]]]
    stderr: List[Dict[str, Union[str, bool, float]]]


@dataclass
class Error:
    """Represents an error from code execution."""

    name: str
    value: str
    traceback: Optional[List[str]] = None


@dataclass
class Result:
    """Represents a rich result (e.g., plot, table) from code execution."""

    type: str  # The mime type or result type (e.g., "image", "text/html", "application/json")
    value: Any  # The actual content/data

    # For backward compatibility
    mime_type: Optional[str] = None
    text: Optional[str] = None
    html: Optional[str] = None
    png: Optional[str] = None
    jpeg: Optional[str] = None
    pdf: Optional[str] = None
    svg: Optional[str] = None
    latex: Optional[str] = None
    json: Optional[Any] = None
    markdown: Optional[str] = None
    raw: Optional[Any] = None

    @property
    def image_data(self) -> Optional[bytes]:
        """Return decoded image data if available."""
        if (
            self.type == "image"
            and isinstance(self.value, dict)
            and "data" in self.value
        ):
            return base64.b64decode(self.value["data"])
        if self.png:
            return base64.b64decode(self.png)
        if self.jpeg:
            return base64.b64decode(self.jpeg)
        return None


@dataclass
class Execution:
    """Represents the result of a code execution."""

    text: Optional[str] = None
    logs: Optional[Logs] = None
    results: List[Result] = None
    error: Optional[Error] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def is_error(self) -> bool:
        """Return True if execution resulted in an error."""
        return self.error is not None

    @property
    def stdout(self) -> str:
        """Return concatenated stdout lines."""
        if not self.logs or not self.logs.stdout:
            return ""
        return "\n".join([log.get("line", "") for log in self.logs.stdout])

    @property
    def stderr(self) -> str:
        """Return concatenated stderr lines."""
        if not self.logs or not self.logs.stderr:
            return ""
        return "\n".join([log.get("line", "") for log in self.logs.stderr])


@dataclass
class FileInfo:
    """Information about a file or directory in the sandbox."""

    name: str
    is_dir: bool
    size: Optional[int] = None
    path: Optional[str] = None


@dataclass
class ProcessExecution:
    """Result of a process execution."""

    stdout: str
    stderr: str
    exit_code: int


@dataclass
class ProcessInfo:
    """Information about a running process in the sandbox."""

    pid: int
    cmd: str
    user: Optional[str] = None
    cwd: Optional[str] = None
    envs: Optional[Dict[str, str]] = None


@dataclass
class WatchHandle:
    """Handle for watching a directory for filesystem events."""

    id: str
    path: str

    def stop(self):
        """Stop watching the directory."""
        pass


@dataclass
class ProcessHandle:
    """Handle for a running process in the sandbox."""

    pid: int
    cmd: str

    def wait(self) -> ProcessExecution:
        """Wait for the process to complete and return its output."""
        pass

    def send_stdin(self, data: str):
        """Send data to the process stdin."""
        pass

    def kill(self) -> bool:
        """Kill the process."""
        pass


@dataclass
class PtyHandle:
    """Handle for a PTY session in the sandbox."""

    pid: int

    def send_data(self, data: bytes):
        """Send data to the PTY."""
        pass

    def resize(self, rows: int, cols: int):
        """Resize the PTY."""
        pass

    def kill(self) -> bool:
        """Kill the PTY session."""
        pass


@dataclass
class FilesystemEvent:
    """Represents a filesystem event."""

    event_type: str  # "create", "delete", "modify"
    path: str
    is_dir: bool
    timestamp: float
