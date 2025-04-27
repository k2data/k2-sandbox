from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from datetime import datetime


class SandboxCreate(BaseModel):
    """Request model for creating a new sandbox"""

    template: Optional[str] = Field(
        default="k2data/sandbox-base:latest", description="Docker image template to use"
    )
    cwd: Optional[str] = Field(
        default="/home/user", description="Initial working directory"
    )
    envs: Optional[Dict[str, str]] = Field(
        default={}, description="Environment variables to set in the container"
    )
    timeout: Optional[int] = Field(
        default=300, description="Sandbox inactivity timeout in seconds"
    )
    metadata: Optional[Dict[str, str]] = Field(
        default={}, description="Custom metadata for the sandbox"
    )


class SandboxResponse(BaseModel):
    """Response model for sandbox operations"""

    sandbox_id: str
    status: str
    timeout: Optional[int] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, str]] = None


class SandboxInfo(BaseModel):
    """Information about a sandbox"""

    sandbox_id: str
    status: str
    template: str
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, str]] = None


class SandboxList(BaseModel):
    """Response model for listing sandboxes"""

    sandboxes: List[SandboxInfo]


class SandboxAction(BaseModel):
    """Request model for performing an action on a sandbox"""

    action: str = Field(
        ..., description="Action to perform: stop, kill, restart, set_timeout"
    )
    timeout: Optional[int] = Field(
        None, description="New timeout value (for set_timeout action)"
    )


class Error(BaseModel):
    """Represents an error from code execution"""

    name: str
    value: str
    traceback: Optional[List[str]] = None


class LogLine(BaseModel):
    """Represents a line of stdout or stderr output"""

    line: str
    error: bool
    timestamp: float


class Logs(BaseModel):
    """Represents stdout and stderr logs from code execution"""

    stdout: List[LogLine] = []
    stderr: List[LogLine] = []


class Result(BaseModel):
    """Represents a rich result from code execution"""

    type: str
    value: Any
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


class CommandExecution(BaseModel):
    """Request model for executing a command in a sandbox"""

    command: str = Field(..., description="Command to execute")
    cwd: Optional[str] = Field(None, description="Working directory for execution")
    envs: Optional[Dict[str, str]] = Field(
        None, description="Environment variables for execution"
    )
    timeout: Optional[float] = Field(
        None, description="Command execution timeout in seconds"
    )


class CommandResponse(BaseModel):
    """Response model for command execution"""

    stdout: str
    stderr: str
    exit_code: int
    execution_time: float


class CodeExecution(BaseModel):
    """Request model for executing code in a sandbox"""

    code: str = Field(..., description="Code to execute")
    language: Optional[str] = Field(
        None, description="Language to use (e.g., python, javascript, r)"
    )
    timeout: Optional[float] = Field(None, description="Execution timeout in seconds")
    cwd: Optional[str] = Field(None, description="Working directory for execution")
    envs: Optional[Dict[str, str]] = Field(
        None, description="Environment variables for execution"
    )


class ExecutionResponse(BaseModel):
    """Response model for code execution"""

    text: Optional[str] = None
    logs: Optional[Logs] = None
    results: List[Result] = []
    error: Optional[Error] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class FileInfo(BaseModel):
    """Information about a file or directory in the sandbox"""

    name: str
    is_dir: bool
    size: Optional[int] = None
    path: Optional[str] = None


class FileSystemAction(BaseModel):
    """Request model for performing filesystem operations in a sandbox"""

    action: str = Field(..., description="Action to perform: list, read, write, delete")
    path: Optional[str] = Field(None, description="Path to file or directory")
    content: Optional[str] = Field(
        None, description="Content to write to file (for write action)"
    )


class FileSystemResponse(BaseModel):
    """Response model for filesystem operations"""

    files: Optional[List[FileInfo]] = None
    content: Optional[str] = None
    message: Optional[str] = None
