"""Main Sandbox class for the K2 Sandbox SDK."""

import os

import requests
import httpx
import json
from typing import Any, Dict, List, Optional
import atexit

from k2_sandbox.models import (
    Execution,
    ExecutionError,
    parse_output,
    OutputMessage,
    OutputHandler,
    Logs,
    Result,
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


class BaseSandbox:
    """
    The base class for creating and interacting with a K2 Sandbox via a REST API.

    Provides common methods for managing sandboxes. Specialized sandboxes
    should inherit from this class.
    """

    DEFAULT_API_BASE_URL = "http://localhost:3000"

    def __init__(
        self,
        template: Optional[str] = None,
        api_key: Optional[str] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = 300,
        metadata: Optional[Dict[str, str]] = None,
        sandbox_id: Optional[str] = None,
        request_timeout: Optional[float] = 60.0,
        api_base_url: Optional[str] = None,
    ):
        """
        Initialize a BaseSandbox instance.

        Args:
            template: Docker image template to use (e.g., 'k2-sandbox/base:latest').
                      Specialized subclasses may provide their own defaults.
            api_key: K2 Sandbox API key
            cwd: Initial working directory
            envs: Environment variables to set in the container
            timeout: Sandbox inactivity timeout in seconds (passed during creation)
            metadata: Custom metadata for the sandbox
            sandbox_id: ID of an existing sandbox to connect to
            request_timeout: Timeout for API requests in seconds
            api_base_url: Base URL of the K2 Sandbox Server API
        """
        self.api_key = api_key or os.environ.get("K2_API_KEY")
        self.api_base_url = api_base_url or os.environ.get(
            "K2_API_BASE_URL", BaseSandbox.DEFAULT_API_BASE_URL  # Updated reference
        )
        # If template is None here, it means either it's a connection (sandbox_id given)
        # or a direct BaseSandbox instantiation without a template.
        # Specialized classes' __init__ should provide a default template if needed.
        self.template = template or "k2-sandbox/base:latest"  # Default for generic base
        self.cwd = cwd
        self.envs = envs or {"E2B_LOCAL": "True"}
        self._initial_timeout = timeout
        self.metadata = metadata or {}
        self.request_timeout = request_timeout

        self._sandbox_id = sandbox_id
        self._closed = False
        self._filesystem = None
        self._process = None
        self._terminal = None
        self._notebook = None
        self._container_info = None  # To store basic info fetched from the API

        # If not connecting to existing sandbox, create a new one
        if not sandbox_id:
            self._create_sandbox()
        else:
            self._connect_sandbox(sandbox_id)

        # Register cleanup handler
        atexit.register(self.close)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Helper method to make requests to the sandbox API."""
        url = f"{self.api_base_url}{endpoint}"
        # Add headers for API key if needed in the future
        headers = {"Content-Type": "application/json"}
        # if self.api_key:
        #     headers["Authorization"] = f"Bearer {self.api_key}" # Example auth

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=self.request_timeout,
                **kwargs,
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response
        except requests.exceptions.Timeout:
            raise TimeoutException(
                f"API request to {url} timed out after {self.request_timeout} seconds"
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise NotFoundError(
                    f"Sandbox resource not found at {url}: {e.response.text}"
                )
            else:
                raise SandboxException(
                    f"API request failed: {e.response.status_code} {e.response.text}"
                )
        except requests.exceptions.RequestException as e:
            raise SandboxException(
                f"Failed to connect to Sandbox API at {url}: {str(e)}"
            )

    def _create_sandbox(self):
        """Create a new sandbox via the API."""
        payload = {
            "image": self.template,
            "environment": self.envs,
            "timeout": self._initial_timeout,
            # 'command' is not specified here, assuming default entrypoint/cmd
        }
        try:
            response = self._make_request("post", "/sandboxes", json=payload)
            data = response.json()
            self._sandbox_id = data.get("id")
            self._container_info = data  # Store initial info
            if not self._sandbox_id:
                raise SandboxException("API did not return a sandbox ID upon creation.")
        except (K2Exception, json.JSONDecodeError) as e:
            raise SandboxException(f"Failed to create sandbox via API: {str(e)}")

    def _connect_sandbox(self, sandbox_id):
        """Connect to an existing sandbox by verifying its existence via the API."""
        try:
            response = self._make_request("get", f"/sandboxes/{sandbox_id}")
            self._sandbox_id = sandbox_id
            self._container_info = response.json()
        except NotFoundError:
            raise NotFoundError(f"Sandbox with ID {sandbox_id} not found via API.")
        except K2Exception as e:
            raise SandboxException(
                f"Failed to connect to sandbox {sandbox_id} via API: {str(e)}"
            )

    def close(self) -> None:
        """Close the sandbox by deleting it via the API."""
        if not self._closed and self._sandbox_id:
            try:
                # Use the API to delete the sandbox
                self._make_request("delete", f"/sandboxes/{self._sandbox_id}")
                self._closed = True
                self._sandbox_id = None
                self._container_info = None
                # Try to unregister the atexit handler if it was registered for this instance
                try:
                    atexit.unregister(self.close)
                except (
                    ValueError
                ):  # Might happen if called multiple times or not registered
                    pass
            except K2Exception as e:
                # Don't raise, maybe just log? Or define behavior.
                # Raising here prevents __exit__ from completing smoothly.
                print(
                    f"Warning: Failed to close sandbox {self._sandbox_id} via API: {str(e)}"
                )
                # We might still want to mark it as closed locally
                self._closed = True
                self._sandbox_id = None  # Assume it's gone or unusable
                self._container_info = None

    def kill(self) -> bool:
        """
        Forcefully terminate the sandbox by deleting it via the API.
        NOTE: The API spec only provides a DELETE endpoint, which likely stops
        and removes. There's no specific "kill" signal via the API.
        """
        if not self._closed and self._sandbox_id:
            try:
                # Use the same DELETE endpoint as close()
                self._make_request("delete", f"/sandboxes/{self._sandbox_id}")
                self._closed = True
                sandbox_id = self._sandbox_id
                self._sandbox_id = None
                self._container_info = None
                try:
                    atexit.unregister(self.close)  # Also unregister here
                except ValueError:
                    pass
                print(f"Sandbox {sandbox_id} deleted via API (kill action).")
                return True
            except K2Exception as e:
                # Raising might be appropriate for kill, unlike close
                raise SandboxException(
                    f"Failed to kill sandbox {self._sandbox_id} via API delete: {str(e)}"
                )
        return False

    @classmethod
    def kill(
        cls,
        sandbox_id: str,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
    ) -> bool:
        """
        Forcefully terminate a sandbox by ID using the API.

        Args:
            sandbox_id: ID of the sandbox to kill
            api_key: K2 Sandbox API key (currently unused)
            api_base_url: Base URL for the API

        Returns:
            True if the sandbox was deleted successfully via API, False otherwise.
            Note: Returns False immediately if the sandbox is not found (404).
        """
        url = f"{api_base_url or os.environ.get('K2_API_BASE_URL', cls.DEFAULT_API_BASE_URL)}/sandboxes/{sandbox_id}"
        headers = {"Content-Type": "application/json"}
        # Add auth header if needed:
        # if api_key: headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.delete(
                url, headers=headers, timeout=60.0
            )  # Use a reasonable default timeout
            if response.status_code == 204:  # Successfully deleted
                return True
            elif response.status_code == 404:  # Not found, already gone
                return False
            else:
                # Raise for other errors (e.g., 500)
                response.raise_for_status()
                return False  # Should not be reached if raise_for_status works
        except requests.exceptions.Timeout:
            print(f"Warning: API request to kill sandbox {sandbox_id} timed out.")
            return False  # Indicate kill might not have succeeded
        except requests.exceptions.RequestException as e:
            # More specific error handling might be needed
            raise SandboxException(
                f"Failed to kill sandbox {sandbox_id} via API: {str(e)}"
            )

    # def set_timeout(
    #     self, timeout: int, request_timeout: Optional[float] = None
    # ) -> None:
    #     """
    #     Set the inactivity timeout for the sandbox.
    #     NOTE: This functionality is NOT supported by the provided API specification.
    #     The timeout can typically only be set during creation.

    #     Args:
    #         timeout: New timeout in seconds
    #         request_timeout: API request timeout (unused)
    #     """
    #     # self.timeout = timeout # Update local state if desired, but cannot push to server
    #     raise NotImplementedError("Setting timeout after sandbox creation is not supported by the API.")

    # @classmethod
    # def set_timeout(cls, sandbox_id: str, timeout: int) -> None:
    #     """
    #     Set the inactivity timeout for a sandbox by ID.
    #     NOTE: This functionality is NOT supported by the provided API specification.

    #     Args:
    #         sandbox_id: ID of the sandbox
    #         timeout: New timeout in seconds
    #     """
    #     raise NotImplementedError("Setting timeout after sandbox creation is not supported by the API.")

    def is_running(self, request_timeout: Optional[float] = None) -> bool:
        """
        Check if the sandbox is currently running by querying the API.

        Args:
            request_timeout: API request timeout (overrides default instance timeout)

        Returns:
            True if the sandbox state is 'running' according to the API.
        """
        if self._closed or not self._sandbox_id:
            return False

        try:
            # Use provided request_timeout or the instance default
            timeout = request_timeout or self.request_timeout
            response = self._make_request(
                "get", f"/sandboxes/{self._sandbox_id}", timeout=timeout
            )
            data = response.json()
            self._container_info = data  # Update cached info
            # Check the 'state' or 'status' field based on the API response `models.SandboxResponse`
            # The spec shows 'state' and 'status', let's prioritize 'state' if available
            state = data.get("state", "").lower()
            status = data.get("status", "").lower()  # Fallback if state is missing

            # Consider 'running' as the primary indicator
            return state == "running"  # Adjust based on actual API state values

        except NotFoundError:
            self._closed = True  # Mark as closed if API says it doesn't exist
            self._sandbox_id = None
            self._container_info = None
            return False
        except (K2Exception, json.JSONDecodeError) as e:
            print(
                f"Warning: Failed to get sandbox status from API for {self._sandbox_id}: {str(e)}"
            )
            # Uncertain state, maybe return False or raise? Returning False for now.
            return False

    @classmethod
    def list(
        cls, api_key: Optional[str] = None, api_base_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all running sandboxes by querying the API.

        Args:
            api_key: K2 Sandbox API key (currently unused)
            api_base_url: Base URL for the API

        Returns:
            List of sandbox information dictionaries, conforming to the previous structure.
        """
        url = f"{api_base_url or os.environ.get('K2_API_BASE_URL', cls.DEFAULT_API_BASE_URL)}/sandboxes"
        headers = {"Content-Type": "application/json"}
        # Add auth header if needed:
        # if api_key: headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.get(
                url, headers=headers, timeout=60.0
            )  # Use a reasonable default timeout
            response.raise_for_status()
            sandboxes_data = response.json()

            # Map API response (list of models.SandboxResponse) to the expected format
            result_list = []
            for sb_data in sandboxes_data:
                result_list.append(
                    {
                        "sandbox_id": sb_data.get("id"),
                        # Use state or status from API response
                        "status": sb_data.get("state") or sb_data.get("status"),
                        "created_at": sb_data.get(
                            "created"
                        ),  # Map 'created' to 'created_at'
                        "image": sb_data.get("image"),
                        # Add other relevant fields if needed, like 'command'
                    }
                )
            return result_list

        except requests.exceptions.RequestException as e:
            raise SandboxException(f"Failed to list sandboxes via API: {str(e)}")
        except json.JSONDecodeError as e:
            raise SandboxException(
                f"Failed to decode API response for listing sandboxes: {str(e)}"
            )

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager and close the sandbox."""
        self.close()

    @property
    def sandbox_id(self) -> Optional[str]:
        """Get the sandbox ID. Returns None if closed or not created."""
        return self._sandbox_id

    # Properties for filesystem, process, terminal, notebook remain the same,
    # but their underlying implementation might need changes if they relied
    # on direct docker access or specific network setups.

    @property
    def filesystem(self):
        """Get the filesystem interface."""
        if not self._filesystem:
            # Ensure this import doesn't cause circular dependency issues
            from k2_sandbox.filesystem import Filesystem

            # Filesystem likely needs self (Sandbox instance) to know the sandbox_id
            # and potentially the api_base_url or a way to execute commands/transfer files.
            # It might need significant refactoring depending on its implementation.
            self._filesystem = Filesystem(self)
        return self._filesystem

    @property
    def process(self):
        """Get the process interface."""
        if not self._process:
            from k2_sandbox.process import Process

            # Process might need similar refactoring as Filesystem.
            self._process = Process(self)
        return self._process

    @property
    def terminal(self):
        """Get the terminal interface."""
        if not self._terminal:
            from k2_sandbox.terminal import Terminal

            # Terminal might need similar refactoring.
            self._terminal = Terminal(self)
        return self._terminal

    @property
    def notebook(self):
        """Get the notebook interface."""
        if not self._notebook:
            from k2_sandbox.notebook import Notebook

            # Notebook might need similar refactoring.
            self._notebook = Notebook(self)
        return self._notebook

    @classmethod
    def create_code_interpreter(
        cls,
        api_key: Optional[str] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = 300,
        metadata: Optional[Dict[str, str]] = None,
        request_timeout: Optional[float] = 60.0,
        api_base_url: Optional[str] = None,
    ) -> "CodeInterpreterSandbox":
        """Creates a new CodeInterpreterSandbox instance."""
        return CodeInterpreterSandbox(
            api_key=api_key,
            cwd=cwd,
            envs=envs,
            timeout=timeout,
            metadata=metadata,
            request_timeout=request_timeout,
            api_base_url=api_base_url,
        )

    @classmethod
    def create(
        cls,
        template: Optional[str] = None,
        api_key: Optional[str] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = 300,
        metadata: Optional[Dict[str, str]] = None,
        request_timeout: Optional[float] = 60.0,
        api_base_url: Optional[str] = None,
    ) -> "BaseSandbox":
        """
        Create a new generic BaseSandbox instance.

        Args:
            template: Docker image template to use. If None, BaseSandbox's
                      default template ('k2-sandbox/base:latest') will be used.
            api_key: K2 Sandbox API key.
            cwd: Initial working directory.
            envs: Environment variables to set in the container.
            timeout: Sandbox inactivity timeout in seconds (passed during creation).
            metadata: Custom metadata for the sandbox.
            request_timeout: Timeout for API requests in seconds.
            api_base_url: Base URL of the K2 Sandbox Server API.

        Returns:
            A new BaseSandbox instance.
        """
        return cls(
            template=template,
            api_key=api_key,
            cwd=cwd,
            envs=envs,
            timeout=timeout,
            metadata=metadata,
            sandbox_id=None,  # Important: sandbox_id is None for creation
            request_timeout=request_timeout,
            api_base_url=api_base_url,
        )

    @classmethod
    def connect(
        cls,
        sandbox_id: str,
        api_key: Optional[str] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, str]] = None,
        request_timeout: Optional[float] = 60.0,
        api_base_url: Optional[str] = None,
    ) -> "BaseSandbox":
        """
        Connect to an existing generic Sandbox.

        Args:
            sandbox_id: ID of the sandbox to connect to.
            api_key: K2 Sandbox API key.
            cwd: Optional current working directory (for local state consistency).
            envs: Optional environment variables (for local state consistency).
            metadata: Optional metadata (for local state consistency).
            request_timeout: Timeout for API requests in seconds.
            api_base_url: Base URL of the K2 Sandbox Server API.

        Returns:
            A BaseSandbox instance connected to the existing sandbox.
        """
        return cls(
            sandbox_id=sandbox_id,
            api_key=api_key,
            cwd=cwd,
            envs=envs,
            metadata=metadata,
            request_timeout=request_timeout,
            api_base_url=api_base_url,
            template=None,  # Template is not used for connection logic by __init__
        )


class CodeInterpreterSandbox(BaseSandbox):
    """A sandbox specialized for code interpretation."""

    DEFAULT_TEMPLATE = "k2-sandbox/code-interpreter:latest"

    def __init__(
        self,
        template: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize a CodeInterpreterSandbox instance.

        Args:
            template: Docker image template. Defaults to CodeInterpreterSandbox.DEFAULT_TEMPLATE if creating.
            sandbox_id: ID of an existing sandbox to connect to.
            **kwargs: Additional arguments for BaseSandbox.
        """
        if sandbox_id is None and template is None:
            final_template = self.DEFAULT_TEMPLATE
        else:
            final_template = template
        super().__init__(template=final_template, sandbox_id=sandbox_id, **kwargs)

    def run_code(
        self,
        code: str,
        language: Optional[str] = None,
        on_stdout: Optional[OutputHandler[OutputMessage]] = None,
        on_stderr: Optional[OutputHandler[OutputMessage]] = None,
        on_result: Optional[OutputHandler[Result]] = None,
        on_error: Optional[OutputHandler[ExecutionError]] = None,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        request_timeout: Optional[float] = None,
    ) -> Execution:
        """
        Execute code in the sandbox using a streaming connection.

        Args:
            code: Code to execute
            language: Language to use (e.g., "python", "javascript", "r")
            on_stdout: Callback for stdout messages
            on_stderr: Callback for stderr messages
            on_result: Callback for rich results (plots, etc.)
            on_error: Callback for execution errors.
            timeout: Execution timeout in seconds (for the entire execution stream).
            cwd: Working directory for execution (prepended to code).
            envs: Environment variables for execution (passed in payload).
            request_timeout: Timeout for individual network requests (connect, write, pool) in seconds.

        Returns:
            An Execution object populated with results from the stream.
        """

        service_url = (
            f"{self.api_base_url}/sandboxes/{self._sandbox_id}/services/49999/execute"
        )

        print(f"Attempting to run code via streaming: {service_url}")

        payload = {
            "code": code,
            "env_vars": envs or {},
        }
        if language:
            payload["language"] = language.lower()

        effective_cwd = cwd or self.cwd
        if effective_cwd:
            code_prefix = f"import os\\ntry:\\n os.chdir(r'{effective_cwd}')\\nexcept FileNotFoundError:\\n print(f'Error: Directory not found: {effective_cwd}')\\n"
            payload["code"] = code_prefix + payload["code"]

        print(f"Payload: {payload}")

        exec_timeout = timeout
        req_timeout = request_timeout or self.request_timeout

        execution = Execution(logs=Logs(stdout=[], stderr=[]), results=[])

        try:
            with httpx.stream(
                "POST",
                service_url,
                json=payload,
                timeout=(req_timeout, exec_timeout, req_timeout, req_timeout),
            ) as response:
                if response.status_code >= 400:
                    error_body = response.read().decode()
                    if response.status_code == 404:
                        raise NotFoundError(
                            f"Execution service not found at {service_url}: {error_body}"
                        )
                    else:
                        raise SandboxException(
                            f"Execution request failed: {response.status_code} {error_body}"
                        )

                for line in response.iter_lines():
                    if line:
                        parse_output(
                            execution,
                            line,
                            on_stdout=on_stdout,
                            on_stderr=on_stderr,
                            on_result=on_result,
                            on_error=on_error,
                        )
            return execution
        except httpx.ReadTimeout:
            error_msg = f"Code execution timed out after {exec_timeout} seconds."
            execution.error = ExecutionError(
                name="TimeoutError", value=error_msg, traceback=[]
            )
            if on_error:
                on_error(execution.error)
            return execution
        except httpx.TimeoutException as e:
            error_msg = f"Network request timed out ({type(e).__name__}): {str(e)}"
            execution.error = ExecutionError(
                name="NetworkTimeoutError", value=error_msg, traceback=[]
            )
            if on_error:
                on_error(execution.error)
            return execution
        except httpx.RequestError as e:
            error_msg = f"Network error connecting to code execution service at {service_url}: {str(e)}"
            execution.error = ExecutionError(
                name="CodeExecutionConnectionError", value=error_msg, traceback=[]
            )
            if on_error:
                on_error(execution.error)
            return execution
        except Exception as e:
            error_msg = f"An unexpected error occurred during code execution stream processing: {str(e)}"
            print(f"Error: {error_msg}")
            if not execution.error:
                execution.error = ExecutionError(
                    name="StreamProcessingError", value=error_msg, traceback=[]
                )
                if on_error:
                    on_error(execution.error)
            return execution


class PythonAppSandbox(BaseSandbox):
    """A sandbox specialized for running Python applications."""

    DEFAULT_TEMPLATE = "k2-sandbox/python-app:latest"

    def __init__(
        self,
        template: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize a PythonAppSandbox instance.

        Args:
            template: Docker image template. Defaults to PythonAppSandbox.DEFAULT_TEMPLATE if creating.
            sandbox_id: ID of an existing sandbox to connect to.
            **kwargs: Additional arguments for BaseSandbox.
        """
        if sandbox_id is None and template is None:
            final_template = self.DEFAULT_TEMPLATE
        else:
            final_template = template
        super().__init__(template=final_template, sandbox_id=sandbox_id, **kwargs)

    # Add Python app specific methods here in the future if any


class TypeScriptAppSandbox(BaseSandbox):
    """A sandbox specialized for running TypeScript applications."""

    DEFAULT_TEMPLATE = "k2-sandbox/typescript-app:latest"

    def __init__(
        self,
        template: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize a TypeScriptAppSandbox instance.

        Args:
            template: Docker image template. Defaults to TypeScriptAppSandbox.DEFAULT_TEMPLATE if creating.
            sandbox_id: ID of an existing sandbox to connect to.
            **kwargs: Additional arguments for BaseSandbox.
        """
        if sandbox_id is None and template is None:
            final_template = self.DEFAULT_TEMPLATE
        else:
            final_template = template
        super().__init__(template=final_template, sandbox_id=sandbox_id, **kwargs)

    # Add TypeScript app specific methods here in the future if any


Sandbox = BaseSandbox
