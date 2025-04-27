"""Main Sandbox class for the K2 Sandbox SDK."""

import os
import uuid
import docker
import requests
import json
from typing import Any, Callable, Dict, List, Optional, Union
import tempfile
import asyncio
import atexit

from k2_sandbox.models import (
    Execution,
    FileInfo,
    ProcessExecution,
    ProcessInfo,
    PtyHandle,
    ProcessHandle,
    Result,
    Logs,
)
from k2_sandbox.exceptions import (
    K2Exception,
    SandboxException,
    TimeoutException,
    NotFoundError,
)

# Import these later to avoid circular imports
# from k2_sandbox.filesystem import Filesystem
# from k2_sandbox.process import Process
# from k2_sandbox.terminal import Terminal
# from k2_sandbox.notebook import Notebook


class Sandbox:
    """
    The main class for creating and interacting with a Docker-based sandbox.

    Provides methods for executing code, managing files, and running processes
    within an isolated Docker container environment.
    """

    def __init__(
        self,
        template: Optional[str] = None,
        api_key: Optional[str] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = 300,
        metadata: Optional[Dict[str, str]] = None,
        sandbox_id: Optional[str] = None,
        request_timeout: Optional[float] = None,
    ):
        """
        Initialize a new Sandbox instance.

        Args:
            template: Docker image template to use
            api_key: K2 Sandbox API key (defaults to K2_API_KEY env var)
            cwd: Initial working directory
            envs: Environment variables to set in the container
            timeout: Sandbox inactivity timeout in seconds
            metadata: Custom metadata for the sandbox
            sandbox_id: ID of an existing sandbox to connect to
            request_timeout: Timeout for API requests in seconds
        """
        self.client = docker.from_env()
        self.api_key = api_key or os.environ.get("K2_API_KEY")
        self.template = template or "k2data/sandbox-base:latest"
        self.cwd = cwd or "/home/user"
        self.envs = envs or {}
        self.timeout = timeout
        self.metadata = metadata or {}
        self.request_timeout = request_timeout

        self._sandbox_id = sandbox_id or str(uuid.uuid4())
        self._container = None
        self._closed = False
        self._filesystem = None
        self._process = None
        self._terminal = None
        self._notebook = None

        # If not connecting to existing sandbox, create a new one
        if not sandbox_id:
            self._create_container()
        else:
            self._connect_container(sandbox_id)

        # Register cleanup handler
        atexit.register(self.close)

    def _create_container(self):
        """Create a new Docker container for the sandbox."""
        try:
            self._container = self.client.containers.run(
                self.template,
                detach=True,
                environment=self.envs,
                working_dir=self.cwd,
                labels={"k2_sandbox_id": self._sandbox_id, **self.metadata},
            )
        except Exception as e:
            raise SandboxException(f"Failed to create sandbox: {str(e)}")

    def _connect_container(self, sandbox_id):
        """Connect to an existing Docker container."""
        try:
            containers = self.client.containers.list(
                filters={"label": f"k2_sandbox_id={sandbox_id}"}
            )
            if not containers:
                raise NotFoundError(f"Sandbox with ID {sandbox_id} not found")
            self._container = containers[0]
        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise SandboxException(f"Failed to connect to sandbox: {str(e)}")

    @classmethod
    def create(cls, template: Optional[str] = None, **kwargs):
        """
        Create a new Sandbox asynchronously.

        Args:
            template: Docker image template to use
            **kwargs: Additional arguments to pass to Sandbox constructor

        Returns:
            A new Sandbox instance
        """
        return cls(template=template, **kwargs)

    @classmethod
    def connect(cls, sandbox_id: str, api_key: Optional[str] = None, **kwargs):
        """
        Connect to an existing Sandbox.

        Args:
            sandbox_id: ID of the sandbox to connect to
            api_key: K2 Sandbox API key
            **kwargs: Additional arguments to pass to Sandbox constructor

        Returns:
            A Sandbox instance connected to the existing sandbox
        """
        return cls(sandbox_id=sandbox_id, api_key=api_key, **kwargs)

    def run_code(
        self,
        code: str,
        language: Optional[str] = None,
        on_stdout: Optional[Callable[[Dict], Any]] = None,
        on_stderr: Optional[Callable[[Dict], Any]] = None,
        on_results: Optional[Callable[[Dict], Any]] = None,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
    ) -> Execution:
        """
        Execute code in the sandbox.

        Args:
            code: Code to execute
            language: Language to use (e.g., "python", "javascript", "r")
            on_stdout: Callback for stdout lines
            on_stderr: Callback for stderr lines
            on_results: Callback for rich results (plots, etc.)
            timeout: Execution timeout in seconds
            cwd: Working directory for execution
            envs: Environment variables for execution

        Returns:
            An Execution object with the results
        """
        from k2_sandbox.models import Execution, Logs, Result

        # Get the container's port mapping for the code interpreter service
        container_info = self._container.attrs
        port_bindings = container_info.get("NetworkSettings", {}).get("Ports", {})
        host_port = 49999  # Default port

        print("run code", code)

        # Check if there's a port mapping
        port_key = "49999/tcp"
        if port_key in port_bindings and port_bindings[port_key]:
            host_ip = port_bindings[port_key][0].get("HostIp", "127.0.0.1")
            host_port = int(port_bindings[port_key][0].get("HostPort", host_port))
            service_url = f"http://{host_ip}:{host_port}/execute"
        else:
            # Try to use the container's IP address directly
            ip_address = container_info.get("NetworkSettings", {}).get("IPAddress")
            if not ip_address:
                # Fallback to localhost with default port
                service_url = "http://localhost:49999/execute"
            else:
                service_url = f"http://{ip_address}:49999/execute"

        print("service_url", service_url)

        # Prepare request payload
        payload = {"code": code, "env_vars": envs or {}}

        # Add language if specified
        if language:
            payload["language"] = language.lower()

        # Set working directory if provided
        if cwd:
            code = f"import os\nos.chdir('{cwd}')\n{code}"

        try:
            # Make request to the code interpreter service
            response = requests.post(
                service_url, json=payload, timeout=timeout or self.timeout
            )

            response.raise_for_status()

            # Parse results
            results = response.json()

            # Collect stdout and stderr
            stdout_lines = []
            stderr_lines = []
            other_results = []
            error = None

            for item in results:
                item_type = item.get("type", "")

                if item_type == "stdout":
                    line = item.get("data", {}).get("text", "")
                    stdout_lines.append(line)
                    if on_stdout:
                        on_stdout({"line": line, "error": False, "timestamp": 0})

                elif item_type == "stderr":
                    line = item.get("data", {}).get("text", "")
                    stderr_lines.append(line)
                    if on_stderr:
                        on_stderr({"line": line, "error": True, "timestamp": 0})

                elif item_type == "error":
                    error = {
                        "name": item.get("data", {}).get("ename", "ExecutionError"),
                        "value": item.get("data", {}).get("evalue", "Unknown error"),
                    }

                    traceback_lines = item.get("data", {}).get("traceback", [])
                    if traceback_lines:
                        for line in traceback_lines:
                            if isinstance(line, str):
                                stderr_lines.append(line)
                                if on_stderr:
                                    on_stderr(
                                        {"line": line, "error": True, "timestamp": 0}
                                    )

                # Handle rich outputs like images, HTML, JSON
                elif on_results and item_type in [
                    "image",
                    "text/html",
                    "application/json",
                ]:
                    result = Result(type=item_type, value=item.get("data", {}))
                    other_results.append(result)
                    on_results(item)

            # Create logs object
            logs = Logs(
                stdout=[
                    {"line": line, "error": False, "timestamp": 0}
                    for line in stdout_lines
                ],
                stderr=[
                    {"line": line, "error": True, "timestamp": 0}
                    for line in stderr_lines
                ],
            )

            return Execution(
                text="\n".join(stdout_lines) if stdout_lines else None,
                logs=logs,
                results=other_results,
                error=error,
            )

        except requests.RequestException as e:
            # Handle request errors
            error_msg = f"Error connecting to code execution service: {str(e)}"
            return Execution(
                text=None,
                logs=Logs(
                    stdout=[],
                    stderr=[{"line": error_msg, "error": True, "timestamp": 0}],
                ),
                results=[],
                error={"name": "RequestError", "value": error_msg},
            )

    def close(self) -> None:
        """Close the sandbox and release resources."""
        if not self._closed and self._container:
            try:
                self._container.stop()
                self._container.remove()
                self._closed = True
                atexit.unregister(self.close)
            except Exception as e:
                raise SandboxException(f"Failed to close sandbox: {str(e)}")

    def kill(self, request_timeout: Optional[float] = None) -> bool:
        """Forcefully terminate the sandbox."""
        if not self._closed and self._container:
            try:
                self._container.kill()
                self._container.remove()
                self._closed = True
                atexit.unregister(self.close)
                return True
            except Exception as e:
                raise SandboxException(f"Failed to kill sandbox: {str(e)}")
        return False

    @classmethod
    def kill(cls, sandbox_id: str, api_key: Optional[str] = None) -> bool:
        """
        Forcefully terminate a sandbox by ID.

        Args:
            sandbox_id: ID of the sandbox to kill
            api_key: K2 Sandbox API key

        Returns:
            True if the sandbox was killed successfully
        """
        client = docker.from_env()
        try:
            containers = client.containers.list(
                filters={"label": f"k2_sandbox_id={sandbox_id}"}
            )
            if not containers:
                return False
            container = containers[0]
            container.kill()
            container.remove()
            return True
        except Exception as e:
            raise SandboxException(f"Failed to kill sandbox: {str(e)}")

    def set_timeout(
        self, timeout: int, request_timeout: Optional[float] = None
    ) -> None:
        """
        Set the inactivity timeout for the sandbox.

        Args:
            timeout: New timeout in seconds
            request_timeout: API request timeout
        """
        self.timeout = timeout

    @classmethod
    def set_timeout(cls, sandbox_id: str, timeout: int) -> None:
        """
        Set the inactivity timeout for a sandbox by ID.

        Args:
            sandbox_id: ID of the sandbox
            timeout: New timeout in seconds
        """
        # Connect to the sandbox and set its timeout
        sandbox = cls.connect(sandbox_id)
        sandbox.set_timeout(timeout)
        sandbox.close()

    def is_running(self, request_timeout: Optional[float] = None) -> bool:
        """
        Check if the sandbox is currently running.

        Args:
            request_timeout: API request timeout

        Returns:
            True if the sandbox is running
        """
        if self._closed or not self._container:
            return False

        try:
            container = self.client.containers.get(self._container.id)
            return container.status == "running"
        except Exception:
            return False

    @classmethod
    def list(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all running sandboxes.

        Args:
            api_key: K2 Sandbox API key

        Returns:
            List of sandbox information dictionaries
        """
        client = docker.from_env()
        containers = client.containers.list(filters={"label": "k2_sandbox_id"})

        return [
            {
                "sandbox_id": container.labels.get("k2_sandbox_id"),
                "status": container.status,
                "created_at": container.attrs["Created"],
                "image": (
                    container.image.tags[0]
                    if container.image.tags
                    else container.image.id
                ),
            }
            for container in containers
        ]

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and close the sandbox."""
        self.close()

    @property
    def sandbox_id(self) -> str:
        """Get the sandbox ID."""
        return self._sandbox_id

    @property
    def filesystem(self):
        """Get the filesystem interface."""
        if not self._filesystem:
            from k2_sandbox.filesystem import Filesystem

            self._filesystem = Filesystem(self)
        return self._filesystem

    @property
    def process(self):
        """Get the process interface."""
        if not self._process:
            from k2_sandbox.process import Process

            self._process = Process(self)
        return self._process

    @property
    def terminal(self):
        """Get the terminal interface."""
        if not self._terminal:
            from k2_sandbox.terminal import Terminal

            self._terminal = Terminal(self)
        return self._terminal

    @property
    def notebook(self):
        """Get the notebook interface."""
        if not self._notebook:
            from k2_sandbox.notebook import Notebook

            self._notebook = Notebook(self)
        return self._notebook
