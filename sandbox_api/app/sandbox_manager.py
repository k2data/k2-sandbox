import docker
import uuid
import os
import requests
import json
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import tempfile

from app.models import (
    SandboxInfo,
    Logs,
    LogLine,
    Error,
    Result,
    ExecutionResponse,
    FileInfo,
    CommandResponse,
)


class SandboxManager:
    """Manager for Docker-based sandboxes"""

    def __init__(self):
        """Initialize the sandbox manager with a Docker client"""
        self.client = docker.from_env()

    def create_sandbox(
        self,
        template: Optional[str] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Create a new sandbox container

        Args:
            template: Docker image template to use
            cwd: Initial working directory
            envs: Environment variables to set in the container
            timeout: Sandbox inactivity timeout in seconds
            metadata: Custom metadata for the sandbox

        Returns:
            The ID of the created sandbox
        """
        template = template or "k2data/sandbox-base:latest"
        cwd = cwd or "/home/user"
        envs = envs or {}
        timeout = timeout or 300
        metadata = metadata or {}

        sandbox_id = str(uuid.uuid4())

        try:
            container = self.client.containers.run(
                template,
                detach=True,
                environment=envs,
                working_dir=cwd,
                labels={"k2_sandbox_id": sandbox_id, **metadata},
            )

            # Store creation time as metadata
            container.reload()

            return sandbox_id
        except Exception as e:
            raise Exception(f"Failed to create sandbox: {str(e)}")

    def list_sandboxes(self) -> List[SandboxInfo]:
        """List all available sandboxes

        Returns:
            A list of sandbox information objects
        """
        try:
            containers = self.client.containers.list(
                all=True, filters={"label": "k2_sandbox_id"}
            )

            sandboxes = []
            for container in containers:
                container.reload()

                # Extract sandbox ID from labels
                sandbox_id = container.labels.get("k2_sandbox_id")
                if not sandbox_id:
                    continue

                # Extract metadata (all labels except k2_sandbox_id)
                metadata = {
                    k: v for k, v in container.labels.items() if k != "k2_sandbox_id"
                }

                # Determine status
                status = "running" if container.status == "running" else "stopped"

                # Get created time
                created_at = datetime.fromisoformat(
                    container.attrs["Created"].replace("Z", "+00:00")
                )

                sandboxes.append(
                    SandboxInfo(
                        sandbox_id=sandbox_id,
                        status=status,
                        template=(
                            container.image.tags[0]
                            if container.image.tags
                            else "unknown"
                        ),
                        created_at=created_at,
                        metadata=metadata,
                    )
                )

            return sandboxes
        except Exception as e:
            raise Exception(f"Failed to list sandboxes: {str(e)}")

    def is_sandbox_running(self, sandbox_id: str) -> bool:
        """Check if a sandbox is running

        Args:
            sandbox_id: ID of the sandbox to check

        Returns:
            True if the sandbox is running, False otherwise
        """
        try:
            containers = self.client.containers.list(
                all=True, filters={"label": f"k2_sandbox_id={sandbox_id}"}
            )

            if not containers:
                return False

            container = containers[0]
            return container.status == "running"
        except Exception as e:
            raise Exception(f"Failed to check sandbox status: {str(e)}")

    def get_container(self, sandbox_id: str) -> docker.models.containers.Container:
        """Get the Docker container for a sandbox

        Args:
            sandbox_id: ID of the sandbox

        Returns:
            The Docker container

        Raises:
            Exception: If the sandbox is not found
        """
        containers = self.client.containers.list(
            all=True, filters={"label": f"k2_sandbox_id={sandbox_id}"}
        )

        if not containers:
            raise Exception(f"Sandbox with ID {sandbox_id} not found")

        return containers[0]

    def stop_sandbox(self, sandbox_id: str) -> None:
        """Stop a sandbox

        Args:
            sandbox_id: ID of the sandbox to stop
        """
        try:
            container = self.get_container(sandbox_id)
            container.stop()
        except Exception as e:
            raise Exception(f"Failed to stop sandbox: {str(e)}")

    def kill_sandbox(self, sandbox_id: str) -> None:
        """Kill a sandbox

        Args:
            sandbox_id: ID of the sandbox to kill
        """
        try:
            container = self.get_container(sandbox_id)
            container.kill()
            container.remove(force=True)
        except Exception as e:
            raise Exception(f"Failed to kill sandbox: {str(e)}")

    def restart_sandbox(self, sandbox_id: str) -> None:
        """Restart a sandbox

        Args:
            sandbox_id: ID of the sandbox to restart
        """
        try:
            container = self.get_container(sandbox_id)
            container.restart()
        except Exception as e:
            raise Exception(f"Failed to restart sandbox: {str(e)}")

    def set_timeout(self, sandbox_id: str, timeout: int) -> None:
        """Set the inactivity timeout for a sandbox

        Args:
            sandbox_id: ID of the sandbox
            timeout: New timeout value in seconds
        """
        # For a real implementation, you'd need to store this in the container's metadata
        # or use a database to track timeouts
        try:
            container = self.get_container(sandbox_id)
            container.reload()

            # Update the container's labels
            new_labels = container.labels
            new_labels["timeout"] = str(timeout)

            # Apply the new labels
            container.update(labels=new_labels)
        except Exception as e:
            raise Exception(f"Failed to set timeout: {str(e)}")

    def execute_command(
        self,
        sandbox_id: str,
        command: str,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> CommandResponse:
        """Execute a command in the sandbox

        Args:
            sandbox_id: ID of the sandbox
            command: Command to execute
            cwd: Working directory for execution
            envs: Environment variables for execution
            timeout: Command execution timeout in seconds

        Returns:
            A CommandResponse object with execution results
        """
        try:
            container = self.get_container(sandbox_id)

            # Prepare the command with working directory if specified
            exec_command = command
            if cwd:
                # Change to the specified directory before executing the command
                exec_command = f"cd {cwd} && {command}"

            # Prepare environment variables if specified
            environment = {}
            if envs:
                environment.update(envs)

            # Record start time
            start_time = time.time()

            # Execute the command
            exec_id = container.client.api.exec_create(
                container.id,
                exec_command,
                environment=environment,
            )

            # Run the command with timeout
            exec_output = container.client.api.exec_start(exec_id["Id"])
            exec_info = container.client.api.exec_inspect(exec_id["Id"])

            # Calculate execution time
            execution_time = time.time() - start_time

            # Get exit code
            exit_code = exec_info.get("ExitCode", 0)

            # Decode output (assuming UTF-8 encoding)
            try:
                output = exec_output.decode("utf-8")
                # For simplicity, we're putting all output to stdout
                # In a real implementation, you might want to separate stdout and stderr
                stdout = output
                stderr = ""
            except UnicodeDecodeError:
                stdout = "Output contains non-UTF-8 characters"
                stderr = "Error decoding output"

            return CommandResponse(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time=execution_time,
            )

        except Exception as e:
            raise Exception(f"Failed to execute command: {str(e)}")

    def run_code(
        self,
        sandbox_id: str,
        code: str,
        language: Optional[str] = None,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
    ) -> ExecutionResponse:
        """Execute code in the sandbox

        Args:
            sandbox_id: ID of the sandbox
            code: Code to execute
            language: Language to use (e.g., "python", "javascript", "r")
            timeout: Execution timeout in seconds
            cwd: Working directory for execution
            envs: Environment variables for execution

        Returns:
            An ExecutionResponse object with execution results
        """
        try:
            container = self.get_container(sandbox_id)

            # Get the container's port mapping for the code interpreter service
            container.reload()
            port_bindings = container.attrs.get("NetworkSettings", {}).get("Ports", {})

            # Check if there's a port mapping
            port_key = "49999/tcp"
            if port_key in port_bindings and port_bindings[port_key]:
                host_ip = port_bindings[port_key][0].get("HostIp", "127.0.0.1")
                host_port = int(port_bindings[port_key][0].get("HostPort", 49999))
                service_url = f"http://{host_ip}:{host_port}/execute"
            else:
                # Try to use the container's IP address directly
                ip_address = container.attrs.get("NetworkSettings", {}).get("IPAddress")
                if not ip_address:
                    # Fallback to localhost with default port
                    service_url = "http://localhost:49999/execute"
                else:
                    service_url = f"http://{ip_address}:49999/execute"

            # Prepare request payload
            payload = {"code": code, "env_vars": envs or {}}

            # Add language if specified
            if language:
                payload["language"] = language.lower()

            # Set working directory if provided
            if cwd:
                code = f"import os\nos.chdir('{cwd}')\n{code}"

            # Make request to the code interpreter service
            response = requests.post(service_url, json=payload, timeout=timeout or 300)

            response.raise_for_status()

            # Parse results
            results = response.json()

            # Collect stdout and stderr
            stdout_lines = []
            stderr_lines = []
            result_objects = []
            error = None

            for item in results:
                item_type = item.get("type", "")

                if item_type == "stdout":
                    line = item.get("data", {}).get("text", "")
                    stdout_lines.append(
                        LogLine(line=line, error=False, timestamp=time.time())
                    )

                elif item_type == "stderr":
                    line = item.get("data", {}).get("text", "")
                    stderr_lines.append(
                        LogLine(line=line, error=True, timestamp=time.time())
                    )

                elif item_type == "error":
                    error = Error(
                        name=item.get("data", {}).get("ename", "ExecutionError"),
                        value=item.get("data", {}).get("evalue", "Unknown error"),
                        traceback=item.get("data", {}).get("traceback", []),
                    )

                elif item_type in ["display_data", "execute_result"]:
                    data = item.get("data", {})
                    for mime_type, value in data.items():
                        result_objects.append(
                            Result(type=mime_type, value=value, mime_type=mime_type)
                        )

            # Create logs object
            logs = Logs(stdout=stdout_lines, stderr=stderr_lines)

            # Create and return execution response
            return ExecutionResponse(
                text="\n".join([log.line for log in stdout_lines]),
                logs=logs,
                results=result_objects,
                error=error,
                created_at=datetime.now(),
                finished_at=datetime.now(),
            )

        except Exception as e:
            raise Exception(f"Failed to execute code: {str(e)}")

    def list_files(self, sandbox_id: str, path: Optional[str] = None) -> List[FileInfo]:
        """List files in a sandbox

        Args:
            sandbox_id: ID of the sandbox
            path: Path to list (defaults to working directory)

        Returns:
            A list of FileInfo objects
        """
        try:
            container = self.get_container(sandbox_id)

            # Default to working directory if path is not specified
            if not path:
                # Get the working directory from the container config
                container.reload()
                path = container.attrs.get("Config", {}).get("WorkingDir", "/home/user")

            # Run ls command to list files
            exit_code, output = container.exec_run(f"ls -la {path}")

            if exit_code != 0:
                raise Exception(f"Failed to list files: {output.decode()}")

            # Parse the output
            lines = output.decode().strip().split("\n")

            # Skip the first line (total) and the current/parent directory entries
            files = []
            for line in lines[1:]:
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) < 9:
                    continue

                # Check if it's a directory
                is_dir = parts[0].startswith("d")

                # Get the size
                size = int(parts[4])

                # Get the name (everything after the date and time)
                name = " ".join(parts[8:])

                # Skip . and .. entries
                if name in [".", ".."]:
                    continue

                # Construct full path
                full_path = os.path.join(path, name)

                files.append(
                    FileInfo(name=name, is_dir=is_dir, size=size, path=full_path)
                )

            return files

        except Exception as e:
            raise Exception(f"Failed to list files: {str(e)}")

    def read_file(self, sandbox_id: str, path: str) -> str:
        """Read a file from a sandbox

        Args:
            sandbox_id: ID of the sandbox
            path: Path to the file

        Returns:
            The contents of the file
        """
        try:
            container = self.get_container(sandbox_id)

            # Use cat to read the file
            exit_code, output = container.exec_run(f"cat {path}")

            if exit_code != 0:
                raise Exception(f"Failed to read file: {output.decode()}")

            return output.decode()

        except Exception as e:
            raise Exception(f"Failed to read file: {str(e)}")

    def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        """Write to a file in a sandbox

        Args:
            sandbox_id: ID of the sandbox
            path: Path to the file
            content: Content to write
        """
        try:
            container = self.get_container(sandbox_id)

            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp:
                temp.write(content)
                temp_path = temp.name

            try:
                # Copy the file to the container
                with open(temp_path, "rb") as src:
                    container.put_archive(
                        os.path.dirname(path),
                        container.client.api.tar(os.path.basename(path), src.read()),
                    )
            finally:
                # Delete the temporary file
                os.unlink(temp_path)

        except Exception as e:
            raise Exception(f"Failed to write file: {str(e)}")

    def delete_file(self, sandbox_id: str, path: str) -> None:
        """Delete a file or directory in a sandbox

        Args:
            sandbox_id: ID of the sandbox
            path: Path to the file or directory
        """
        try:
            container = self.get_container(sandbox_id)

            # Use rm to delete the file
            exit_code, output = container.exec_run(f"rm -rf {path}")

            if exit_code != 0:
                raise Exception(f"Failed to delete file: {output.decode()}")

        except Exception as e:
            raise Exception(f"Failed to delete file: {str(e)}")
