"""Process management for the K2 Sandbox."""

import os
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union, Tuple

from k2_sandbox.models import ProcessExecution, ProcessInfo, ProcessHandle
from k2_sandbox.exceptions import ProcessError, NotFoundError, TimeoutException


class Process:
    """
    Interface for process management within a Docker sandbox.

    Provides methods to start, list, and manage processes in the sandbox.
    """

    def __init__(self, sandbox):
        """
        Initialize the Process interface.

        Args:
            sandbox: The Sandbox instance to operate on
        """
        self.sandbox = sandbox
        self._running_processes = {}  # pid -> ProcessHandle

    def start(
        self,
        cmd: str,
        on_stdout: Optional[Callable] = None,
        on_stderr: Optional[Callable] = None,
        timeout: Optional[float] = 60,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        user: Optional[str] = "user",
        background: bool = False,
    ) -> Union[ProcessExecution, ProcessHandle]:
        """
        Start a new process in the sandbox.

        Args:
            cmd: Command to execute
            on_stdout: Callback for stdout lines
            on_stderr: Callback for stderr lines
            timeout: Execution timeout in seconds
            cwd: Working directory for the process
            envs: Environment variables for the process
            user: User context (usually ignored in Docker implementation)
            background: Whether to run in background

        Returns:
            ProcessExecution if background=False, ProcessHandle if background=True
        """
        try:
            # Build the command environment
            working_dir = cwd or self.sandbox.cwd
            env_str = ""
            if envs:
                env_str = " ".join([f"{k}={v}" for k, v in envs.items()]) + " "

            # Run the command
            if background:
                # For background processes, we need to get a PID and detach
                full_cmd = f"cd {working_dir} && {env_str}{cmd} & echo $!"
                exit_code, output = self.sandbox._container.exec_run(full_cmd)
                if exit_code != 0:
                    raise ProcessError(
                        f"Failed to start background process: {output.decode('utf-8')}"
                    )

                # Extract the PID
                pid = int(output.decode("utf-8").strip())

                # Create a handle for the process
                handle = _DockerProcessHandle(
                    self.sandbox, pid, cmd, on_stdout, on_stderr
                )
                self._running_processes[pid] = handle

                return handle
            else:
                # For foreground processes, we run and wait for completion
                full_cmd = f"cd {working_dir} && {env_str}{cmd}"
                exec_result = self.sandbox._container.exec_run(
                    full_cmd,
                    demux=True,
                    tty=False,
                    environment=envs,
                    workdir=working_dir,
                    stream=True,
                )

                # Stream the output if callbacks are provided
                stdout_chunks = []
                stderr_chunks = []

                start_time = time.time()
                for stream_type, chunk in exec_result.output:
                    if timeout and time.time() - start_time > timeout:
                        raise TimeoutException(
                            f"Process execution timed out after {timeout} seconds"
                        )

                    if stream_type == 1:  # stdout
                        stdout_chunks.append(chunk)
                        if on_stdout:
                            lines = chunk.decode("utf-8", errors="replace").splitlines()
                            for line in lines:
                                if line:
                                    on_stdout(
                                        {
                                            "line": line,
                                            "error": False,
                                            "timestamp": time.time(),
                                        }
                                    )
                    elif stream_type == 2:  # stderr
                        stderr_chunks.append(chunk)
                        if on_stderr:
                            lines = chunk.decode("utf-8", errors="replace").splitlines()
                            for line in lines:
                                if line:
                                    on_stderr(
                                        {
                                            "line": line,
                                            "error": True,
                                            "timestamp": time.time(),
                                        }
                                    )

                # Combine the output
                stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")

                return ProcessExecution(
                    stdout=stdout, stderr=stderr, exit_code=exec_result.exit_code
                )

        except Exception as e:
            if isinstance(e, TimeoutException):
                raise
            raise ProcessError(f"Error starting process: {str(e)}")

    def list(self) -> List[ProcessInfo]:
        """
        List running processes started via this interface.

        Returns:
            List of ProcessInfo objects representing running processes
        """
        try:
            # Use ps to list processes
            exit_code, output = self.sandbox._container.exec_run(
                "ps -eo pid,cmd,cwd --no-headers"
            )
            if exit_code != 0:
                raise ProcessError(
                    f"Failed to list processes: {output.decode('utf-8')}"
                )

            # Parse the output
            lines = output.decode("utf-8").splitlines()
            result = []

            for line in lines:
                if not line.strip():
                    continue

                parts = line.split(None, 2)
                if len(parts) < 2:
                    continue

                pid = int(parts[0])
                cmd = parts[1]
                cwd = parts[2] if len(parts) > 2 else None

                # Only include user processes (PID > 100 is a heuristic)
                if pid > 100:
                    result.append(
                        ProcessInfo(
                            pid=pid,
                            cmd=cmd,
                            user="user",  # Default user in Docker
                            cwd=cwd,
                            envs=None,  # Not easily available
                        )
                    )

            return result

        except Exception as e:
            raise ProcessError(f"Error listing processes: {str(e)}")

    def kill(self, pid: int) -> bool:
        """
        Kill a running process by PID.

        Args:
            pid: Process ID to kill

        Returns:
            True if the process was killed successfully
        """
        try:
            # Check if the PID exists
            exit_code, _ = self.sandbox._container.exec_run(f"kill -0 {pid}")
            if exit_code != 0:
                raise NotFoundError(f"Process with PID {pid} not found")

            # Kill the process
            exit_code, output = self.sandbox._container.exec_run(f"kill -9 {pid}")
            if exit_code != 0:
                raise ProcessError(f"Failed to kill process: {output.decode('utf-8')}")

            # Remove from running processes if tracked
            if pid in self._running_processes:
                del self._running_processes[pid]

            return True

        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise ProcessError(f"Error killing process: {str(e)}")

    def send_stdin(self, pid: int, data: str) -> None:
        """
        Send data to the standard input of a running process.

        This is a placeholder. Docker doesn't easily support this for exec_run,
        but we could implement it for long-running processes using PTY or pipes.

        Args:
            pid: Process ID
            data: String data to send
        """
        # Check if we have a handle for this process
        if pid in self._running_processes:
            handle = self._running_processes[pid]
            handle.send_stdin(data)
            return

        raise ProcessError(
            "Cannot send stdin to a process not started with background=True"
        )


class _DockerProcessHandle(ProcessHandle):
    """Internal implementation of ProcessHandle for Docker."""

    def __init__(
        self,
        sandbox,
        pid: int,
        cmd: str,
        on_stdout: Optional[Callable] = None,
        on_stderr: Optional[Callable] = None,
    ):
        """Initialize the handle."""
        super().__init__(pid=pid, cmd=cmd)
        self.sandbox = sandbox
        self.on_stdout = on_stdout
        self.on_stderr = on_stderr
        self._stopped = False
        self._output_thread = None

        # Start output monitoring if callbacks are provided
        if on_stdout or on_stderr:
            self._start_output_monitoring()

    def _start_output_monitoring(self):
        """Start a thread to monitor process output."""

        def monitor_output():
            try:
                while not self._stopped:
                    # Check if process is still running
                    exit_code, _ = self.sandbox._container.exec_run(
                        f"kill -0 {self.pid}"
                    )
                    if exit_code != 0:
                        self._stopped = True
                        break

                    # Get stdout if callback provided
                    if self.on_stdout:
                        try:
                            # Try to read stdout (this is a simplified approach)
                            exit_code, output = self.sandbox._container.exec_run(
                                f"tail -n 10 /proc/{self.pid}/fd/1 2>/dev/null"
                            )
                            if exit_code == 0 and output:
                                for line in output.decode("utf-8").splitlines():
                                    self.on_stdout(
                                        {
                                            "line": line,
                                            "error": False,
                                            "timestamp": time.time(),
                                        }
                                    )
                        except Exception:
                            pass

                    # Get stderr if callback provided
                    if self.on_stderr:
                        try:
                            # Try to read stderr (this is a simplified approach)
                            exit_code, output = self.sandbox._container.exec_run(
                                f"tail -n 10 /proc/{self.pid}/fd/2 2>/dev/null"
                            )
                            if exit_code == 0 and output:
                                for line in output.decode("utf-8").splitlines():
                                    self.on_stderr(
                                        {
                                            "line": line,
                                            "error": True,
                                            "timestamp": time.time(),
                                        }
                                    )
                        except Exception:
                            pass

                    # Sleep to avoid excessive CPU usage
                    time.sleep(0.5)
            except Exception:
                # Ignore errors in monitoring thread
                pass

        self._output_thread = threading.Thread(target=monitor_output)
        self._output_thread.daemon = True
        self._output_thread.start()

    def wait(self) -> ProcessExecution:
        """
        Wait for the process to complete and return its output.

        Returns:
            ProcessExecution with stdout, stderr, and exit code
        """
        try:
            # Wait for the process to finish
            stdout = []
            stderr = []
            exit_code = None

            while True:
                # Check if process is still running
                check_code, _ = self.sandbox._container.exec_run(f"kill -0 {self.pid}")
                if check_code != 0:
                    # Process has finished, get its exit code
                    exit_code, output = self.sandbox._container.exec_run(f"echo $?")
                    try:
                        exit_code = int(output.decode("utf-8").strip())
                    except (ValueError, TypeError):
                        exit_code = -1
                    break

                # Sleep to avoid excessive CPU usage
                time.sleep(0.1)

            # Get any remaining output
            try:
                _, output = self.sandbox._container.exec_run(
                    f"cat /tmp/pid_{self.pid}_stdout.log 2>/dev/null"
                )
                if output:
                    stdout.append(output.decode("utf-8"))
            except Exception:
                pass

            try:
                _, output = self.sandbox._container.exec_run(
                    f"cat /tmp/pid_{self.pid}_stderr.log 2>/dev/null"
                )
                if output:
                    stderr.append(output.decode("utf-8"))
            except Exception:
                pass

            # Stop monitoring
            self._stopped = True
            if self._output_thread and self._output_thread.is_alive():
                self._output_thread.join(1)

            return ProcessExecution(
                stdout="".join(stdout), stderr="".join(stderr), exit_code=exit_code or 0
            )

        except Exception as e:
            raise ProcessError(f"Error waiting for process: {str(e)}")

    def send_stdin(self, data: str) -> None:
        """
        Send data to the process stdin.

        Args:
            data: String data to send
        """
        try:
            # This is a placeholder. Proper implementation would involve PTY or pipes.
            # For now, we'll just write to a temp file and use cat with FIFO.
            # This won't work for all processes but demonstrates the concept.
            exit_code, _ = self.sandbox._container.exec_run(
                f"test -e /tmp/pid_{self.pid}_stdin.fifo || mkfifo /tmp/pid_{self.pid}_stdin.fifo"
            )
            if exit_code != 0:
                raise ProcessError("Failed to create FIFO for stdin")

            # Write data to a temporary file
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                f.write(data)
                tmp_path = f.name

            # Copy the file to the container
            with open(tmp_path, "rb") as f:
                self.sandbox._container.put_archive("/tmp", f.read())

            # Cat the file to the FIFO
            self.sandbox._container.exec_run(
                f"cat /tmp/{os.path.basename(tmp_path)} > /tmp/pid_{self.pid}_stdin.fifo &"
            )

        except Exception as e:
            raise ProcessError(f"Error sending stdin to process: {str(e)}")

    def kill(self) -> bool:
        """
        Kill the process.

        Returns:
            True if the process was killed successfully
        """
        try:
            # Stop monitoring
            self._stopped = True

            # Kill the process
            exit_code, output = self.sandbox._container.exec_run(f"kill -9 {self.pid}")
            if exit_code != 0 and "No such process" not in output.decode("utf-8"):
                raise ProcessError(f"Failed to kill process: {output.decode('utf-8')}")

            return True

        except Exception as e:
            raise ProcessError(f"Error killing process: {str(e)}")
