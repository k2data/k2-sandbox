"""Terminal (PTY) interaction for the K2 Sandbox."""

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from k2_sandbox.models import PtyHandle
from k2_sandbox.exceptions import TerminalError, NotFoundError


class Terminal:
    """
    Interface for terminal (PTY) interaction within a Docker sandbox.

    Provides methods to create and interact with pseudo-terminals in the sandbox.
    """

    def __init__(self, sandbox):
        """
        Initialize the Terminal interface.

        Args:
            sandbox: The Sandbox instance to operate on
        """
        self.sandbox = sandbox
        self._running_terminals = {}  # pid -> _DockerPtyHandle

    def start(
        self,
        on_data: Callable[[bytes], Any],
        size: Optional[Tuple[int, int]] = None,
        cmd: Optional[str] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        user: Optional[str] = "user",
        timeout: Optional[float] = 60,
    ) -> PtyHandle:
        """
        Start a new PTY session.

        Args:
            on_data: Callback for PTY output data
            size: Initial terminal dimensions (rows, cols)
            cmd: Optional command to run (defaults to shell)
            cwd: Working directory
            envs: Environment variables
            user: User context (usually ignored in Docker implementation)
            timeout: Session timeout

        Returns:
            A PtyHandle for the PTY session
        """
        try:
            # Prepare the environment
            working_dir = cwd or self.sandbox.cwd
            env_vars = self.sandbox.envs.copy()
            if envs:
                env_vars.update(envs)

            # Default command is bash or sh
            command = cmd or "bash || sh"

            # Set terminal size if provided
            term_env = {}
            if size:
                rows, cols = size
                term_env = {"LINES": str(rows), "COLUMNS": str(cols)}
                env_vars.update(term_env)

            # Start the process with a PTY
            exec_result = self.sandbox._container.exec_run(
                command,
                environment=env_vars,
                workdir=working_dir,
                tty=True,  # This is key for PTY
                stdin=True,
                socket=True,  # Get a socket for bidirectional communication
                privileged=True,
            )

            # Get the ID of the exec instance and container
            exec_id = exec_result.id
            container_id = self.sandbox._container.id

            # Use Docker API to get the PID (this is somewhat hacky and Docker-specific)
            # In a real implementation, we'd need to extract this from Docker's internals
            client = self.sandbox.client
            exec_details = client.api.exec_inspect(exec_id)
            pid = exec_details.get("Pid", 0)

            if pid <= 0:
                # If we can't get the PID from Docker API, fallback to a workaround
                # This assumes the container is running with a compatible init system
                exit_code, output = self.sandbox._container.exec_run(
                    "echo $$ && ps -o pid= | sort -n | tail -n 1"
                )
                if exit_code == 0:
                    lines = output.decode("utf-8").splitlines()
                    if len(lines) >= 2:
                        try:
                            # Use the most recently created PID as a heuristic
                            pid = int(lines[1].strip())
                        except (ValueError, IndexError):
                            pid = 999  # Placeholder PID

            # Create a socket wrapper
            socket = exec_result.output

            # Create a handle for the PTY
            handle = _DockerPtyHandle(
                self.sandbox, pid, socket, exec_id, container_id, on_data, size
            )

            # Store the handle
            self._running_terminals[pid] = handle

            # Start reading from the socket
            handle._start_reading()

            return handle

        except Exception as e:
            raise TerminalError(f"Error starting PTY: {str(e)}")

    def send_data(self, pid: int, data: bytes) -> None:
        """
        Send data to the PTY.

        Args:
            pid: PTY Process ID
            data: Bytes to send
        """
        try:
            # Check if we have a handle for this PTY
            if pid not in self._running_terminals:
                raise NotFoundError(f"PTY with PID {pid} not found")

            # Send data via the handle
            self._running_terminals[pid].send_data(data)

        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise TerminalError(f"Error sending data to PTY: {str(e)}")

    def resize(self, pid: int, size: Tuple[int, int]) -> None:
        """
        Resize the PTY.

        Args:
            pid: PTY Process ID
            size: New dimensions (rows, cols)
        """
        try:
            # Check if we have a handle for this PTY
            if pid not in self._running_terminals:
                raise NotFoundError(f"PTY with PID {pid} not found")

            # Resize via the handle
            self._running_terminals[pid].resize(size[0], size[1])

        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise TerminalError(f"Error resizing PTY: {str(e)}")

    def kill(self, pid: int) -> bool:
        """
        Terminate the PTY session.

        Args:
            pid: PTY Process ID

        Returns:
            True if the PTY was killed successfully
        """
        try:
            # Check if we have a handle for this PTY
            if pid not in self._running_terminals:
                raise NotFoundError(f"PTY with PID {pid} not found")

            # Kill via the handle
            result = self._running_terminals[pid].kill()

            # Remove from running terminals
            if result:
                del self._running_terminals[pid]

            return result

        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise TerminalError(f"Error killing PTY: {str(e)}")


class _DockerPtyHandle(PtyHandle):
    """Internal implementation of PtyHandle for Docker."""

    def __init__(
        self,
        sandbox,
        pid: int,
        socket,
        exec_id: str,
        container_id: str,
        on_data: Callable[[bytes], Any],
        size: Optional[Tuple[int, int]] = None,
    ):
        """Initialize the handle."""
        super().__init__(pid=pid)
        self.sandbox = sandbox
        self.socket = socket
        self.exec_id = exec_id
        self.container_id = container_id
        self.on_data = on_data
        self.size = size or (24, 80)  # Default terminal size
        self._running = True
        self._read_thread = None

    def _start_reading(self):
        """Start a thread to read from the PTY socket."""

        def read_loop():
            try:
                # Read in a loop while the PTY is active
                while self._running and self.socket:
                    try:
                        data = self.socket.recv(4096)
                        if not data:
                            # EOF - socket closed
                            self._running = False
                            break

                        # Call the data callback
                        if self.on_data:
                            self.on_data(data)
                    except Exception as e:
                        if self._running:
                            # Only log if we're still supposed to be running
                            print(f"Error reading from PTY: {str(e)}")
                        break
            except Exception as e:
                # Log the exception but don't crash the thread
                print(f"PTY read thread error: {str(e)}")
            finally:
                self._running = False

        self._read_thread = threading.Thread(target=read_loop)
        self._read_thread.daemon = True
        self._read_thread.start()

    def send_data(self, data: bytes) -> None:
        """
        Send data to the PTY.

        Args:
            data: Bytes to send
        """
        if not self._running:
            raise TerminalError("PTY session is no longer active")

        try:
            self.socket.send(data)
        except Exception as e:
            self._running = False
            raise TerminalError(f"Error sending data to PTY: {str(e)}")

    def resize(self, rows: int, cols: int) -> None:
        """
        Resize the PTY.

        Args:
            rows: Number of rows
            cols: Number of columns
        """
        if not self._running:
            raise TerminalError("PTY session is no longer active")

        try:
            # Update our stored size
            self.size = (rows, cols)

            # Use Docker API to resize the TTY
            # This is Docker-specific and requires access to the Docker API
            self.sandbox.client.api.resize(self.exec_id, height=rows, width=cols)
        except Exception as e:
            raise TerminalError(f"Error resizing PTY: {str(e)}")

    def kill(self) -> bool:
        """
        Kill the PTY session.

        Returns:
            True if the PTY was killed successfully
        """
        if not self._running:
            return True  # Already dead

        try:
            # Mark as not running first to stop the read thread
            self._running = False

            # Close the socket
            try:
                if self.socket:
                    self.socket.close()
            except Exception:
                pass

            # Kill the process in the container
            try:
                self.sandbox._container.exec_run(f"kill -9 {self.pid}")
            except Exception:
                pass

            # Wait for the read thread to exit
            if self._read_thread and self._read_thread.is_alive():
                self._read_thread.join(1)

            return True

        except Exception as e:
            raise TerminalError(f"Error killing PTY: {str(e)}")
