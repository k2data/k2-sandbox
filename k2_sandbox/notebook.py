"""Jupyter-like notebook functionality for the K2 Sandbox."""

from typing import Any, Callable, Dict, List, Optional, Union
import json
import threading
import time

from k2_sandbox.models import Execution, Result, Logs, Error
from k2_sandbox.exceptions import CodeExecutionError, NotFoundError


class Notebook:
    """
    Interface for Jupyter-like code execution within a Docker sandbox.

    Provides methods to execute code with rich output like plots and tables,
    similar to executing cells in a Jupyter notebook.
    """

    def __init__(self, sandbox):
        """
        Initialize the Notebook interface.

        Args:
            sandbox: The Sandbox instance to operate on
        """
        self.sandbox = sandbox
        self._kernel_id = None
        self._installed = False

    def _ensure_jupyter_installed(self):
        """Ensure Jupyter and IPython are installed in the container."""
        if self._installed:
            return

        try:
            # Check if pip is available
            exit_code, _ = self.sandbox._container.exec_run("which pip || which pip3")

            if exit_code != 0:
                # Install pip if not available
                self.sandbox._container.exec_run(
                    "apt-get update && apt-get install -y python3-pip"
                )

            # Install Jupyter
            exit_code, output = self.sandbox._container.exec_run(
                "pip install jupyter ipykernel"
            )

            if exit_code != 0:
                raise CodeExecutionError(
                    f"Failed to install Jupyter: {output.decode('utf-8')}"
                )

            self._installed = True

        except Exception as e:
            raise CodeExecutionError(f"Error setting up Jupyter: {str(e)}")

    def _start_kernel(self):
        """Start a Jupyter kernel in the container."""
        if self._kernel_id:
            # Check if kernel is still running
            try:
                exit_code, _ = self.sandbox._container.exec_run(
                    f"jupyter kernelspec list | grep {self._kernel_id}"
                )
                if exit_code == 0:
                    return  # Kernel is still running
            except Exception:
                pass

        try:
            # Ensure Jupyter is installed
            self._ensure_jupyter_installed()

            # Start a new kernel
            exit_code, output = self.sandbox._container.exec_run(
                "jupyter kernel --no-stdout --no-stderr"
            )

            if exit_code != 0:
                raise CodeExecutionError(
                    f"Failed to start Jupyter kernel: {output.decode('utf-8')}"
                )

            # Extract kernel ID from output
            kernel_info = output.decode("utf-8")
            try:
                # Parse the kernel connection file path to get the kernel ID
                lines = kernel_info.splitlines()
                for line in lines:
                    if "Connection file:" in line:
                        conn_file = line.split("Connection file:")[1].strip()
                        self._kernel_id = conn_file.split("/")[-1].split(".")[0]
                        break
            except Exception:
                self._kernel_id = f"k2sandbox-kernel-{int(time.time())}"

        except Exception as e:
            if isinstance(e, CodeExecutionError):
                raise
            raise CodeExecutionError(f"Error starting Jupyter kernel: {str(e)}")

    def execute(
        self,
        code: str,
        on_stdout: Optional[Callable[[Dict], Any]] = None,
        on_stderr: Optional[Callable[[Dict], Any]] = None,
        on_results: Optional[Callable[[Dict], Any]] = None,
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Execution:
        """
        Execute code in a Jupyter-like environment.

        Args:
            code: Code to execute
            on_stdout: Callback for stdout lines
            on_stderr: Callback for stderr lines
            on_results: Callback for rich results
            timeout: Execution timeout in seconds
            cwd: Working directory for execution
            metadata: Additional metadata for execution

        Returns:
            An Execution object with results
        """
        try:
            # This is a placeholder implementation since we can't easily
            # communicate with a Jupyter kernel in this simplified model
            # A real implementation would use the Jupyter messaging protocol

            # For now, we'll execute the code using the standard run_code method,
            # but wrap the output in a richer structure

            # Start with a Python cell magic to handle different languages
            if code.strip().startswith("%%javascript") or code.strip().startswith(
                "%%js"
            ):
                language = "javascript"
                code = "\n".join(code.splitlines()[1:])
            elif code.strip().startswith("%%html"):
                language = "html"
                code = "\n".join(code.splitlines()[1:])
            elif code.strip().startswith("%%bash") or code.strip().startswith("%%sh"):
                language = "bash"
                code = "\n".join(code.splitlines()[1:])
            else:
                language = "python"

            # For non-Python code, we need to handle it differently
            if language != "python":
                if language == "javascript":
                    # Execute JavaScript in Node.js
                    result = self.sandbox.process.start(
                        f"node -e '{code}'",
                        on_stdout=on_stdout,
                        on_stderr=on_stderr,
                        timeout=timeout,
                        cwd=cwd,
                    )

                    stdout = result.stdout
                    stderr = result.stderr
                    exit_code = result.exit_code

                    # Create logs structure
                    logs = Logs(
                        stdout=[
                            {"line": line, "error": False, "timestamp": time.time()}
                            for line in stdout.splitlines()
                        ],
                        stderr=[
                            {"line": line, "error": True, "timestamp": time.time()}
                            for line in stderr.splitlines()
                        ],
                    )

                    # Create error object if needed
                    error = None
                    if exit_code != 0:
                        error = Error(
                            name="JavaScriptError",
                            value=stderr or "Unknown error",
                            traceback=stderr.splitlines() if stderr else None,
                        )

                    # Create results object if applicable
                    results = []
                    if not error and stdout:
                        # Try to parse as JSON for rich output
                        try:
                            data = json.loads(stdout)
                            results.append(
                                Result(mime_type="application/json", json=data)
                            )
                        except Exception:
                            # Plain text output
                            results.append(Result(mime_type="text/plain", text=stdout))

                    return Execution(
                        text=stdout if not error else None,
                        logs=logs,
                        results=results,
                        error=error,
                        created_at=time.time(),
                        finished_at=time.time(),
                    )

                elif language == "html":
                    # Handle HTML by returning it as a result
                    return Execution(
                        text=None,
                        logs=Logs(stdout=[], stderr=[]),
                        results=[Result(mime_type="text/html", html=code)],
                        error=None,
                        created_at=time.time(),
                        finished_at=time.time(),
                    )

                elif language == "bash":
                    # Execute bash script
                    result = self.sandbox.process.start(
                        f"bash -c '{code}'",
                        on_stdout=on_stdout,
                        on_stderr=on_stderr,
                        timeout=timeout,
                        cwd=cwd,
                    )

                    stdout = result.stdout
                    stderr = result.stderr
                    exit_code = result.exit_code

                    # Create logs structure
                    logs = Logs(
                        stdout=[
                            {"line": line, "error": False, "timestamp": time.time()}
                            for line in stdout.splitlines()
                        ],
                        stderr=[
                            {"line": line, "error": True, "timestamp": time.time()}
                            for line in stderr.splitlines()
                        ],
                    )

                    # Create error object if needed
                    error = None
                    if exit_code != 0:
                        error = Error(
                            name="BashError",
                            value=stderr or "Unknown error",
                            traceback=stderr.splitlines() if stderr else None,
                        )

                    return Execution(
                        text=stdout if not error else None,
                        logs=logs,
                        results=[],
                        error=error,
                        created_at=time.time(),
                        finished_at=time.time(),
                    )

            # For Python code, we'll use our run_code method
            # Modify the code to handle rich outputs like plots
            code_with_capture = f"""
import sys
import json
from io import StringIO, BytesIO
import base64

# Capture stdout and stderr
stdout_capture = StringIO()
stderr_capture = StringIO()
old_stdout, old_stderr = sys.stdout, sys.stderr
sys.stdout, sys.stderr = stdout_capture, stderr_capture

# Rich output results
rich_outputs = []

try:
    # Try to import plotting libraries if available
    try:
        import matplotlib.pyplot as plt
        has_matplotlib = True
    except ImportError:
        has_matplotlib = False
        
    try:
        import pandas as pd
        has_pandas = True
    except ImportError:
        has_pandas = False
        
    # Execute the user code
    exec_result = None
    exec_globals = {{'plt': plt}} if has_matplotlib else {{}}
    exec_globals.update({{'pd': pd}} if has_pandas else {{}})
    
    # Execute the user's code
    exec('''
{code}
    ''', exec_globals)
    
    # Capture the last expression value if any
    if '_' in exec_globals:
        exec_result = exec_globals['_']
    
    # Capture matplotlib plots if available
    if has_matplotlib and plt.get_fignums():
        for fig_num in plt.get_fignums():
            fig = plt.figure(fig_num)
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            rich_outputs.append({{
                'mime_type': 'image/png',
                'png': img_base64
            }})
        plt.close('all')
    
    # Capture pandas DataFrames if available
    if has_pandas and exec_result is not None and isinstance(exec_result, pd.DataFrame):
        rich_outputs.append({{
            'mime_type': 'text/html',
            'html': exec_result.to_html()
        }})
    
    # Add plain text result if not already captured
    if exec_result is not None and not rich_outputs:
        rich_outputs.append({{
            'mime_type': 'text/plain',
            'text': str(exec_result)
        }})
        
except Exception as e:
    import traceback
    error_details = {{
        'name': type(e).__name__,
        'value': str(e),
        'traceback': traceback.format_exception(type(e), e, e.__traceback__)
    }}
    stderr_capture.write(''.join(error_details['traceback']))
else:
    error_details = None

# Restore stdout and stderr
sys.stdout, sys.stderr = old_stdout, old_stderr

# Print the results as JSON
print(json.dumps({{
    'stdout': stdout_capture.getvalue(),
    'stderr': stderr_capture.getvalue(),
    'error': error_details,
    'rich_outputs': rich_outputs
}}))
"""

            # Execute the modified code
            execution = self.sandbox.run_code(
                code_with_capture,
                on_stdout=on_stdout,
                on_stderr=on_stderr,
                timeout=timeout,
                cwd=cwd,
            )

            # Parse the JSON result
            try:
                if execution.text:
                    result_data = json.loads(execution.text)

                    # Extract stdout and stderr
                    stdout = result_data.get("stdout", "")
                    stderr = result_data.get("stderr", "")

                    # Create logs structure
                    logs = Logs(
                        stdout=[
                            {"line": line, "error": False, "timestamp": time.time()}
                            for line in stdout.splitlines()
                        ],
                        stderr=[
                            {"line": line, "error": True, "timestamp": time.time()}
                            for line in stderr.splitlines()
                        ],
                    )

                    # Extract error if any
                    error = None
                    error_data = result_data.get("error")
                    if error_data:
                        error = Error(
                            name=error_data.get("name", "ExecutionError"),
                            value=error_data.get("value", "Unknown error"),
                            traceback=error_data.get("traceback"),
                        )

                    # Extract rich outputs
                    results = []
                    rich_outputs = result_data.get("rich_outputs", [])
                    for output in rich_outputs:
                        mime_type = output.get("mime_type", "text/plain")
                        result_obj = Result(mime_type=mime_type)

                        # Set the appropriate field based on mime type
                        if mime_type == "text/plain":
                            result_obj.text = output.get("text")
                        elif mime_type == "text/html":
                            result_obj.html = output.get("html")
                        elif mime_type == "image/png":
                            result_obj.png = output.get("png")
                        elif mime_type == "image/jpeg":
                            result_obj.jpeg = output.get("jpeg")
                        elif mime_type == "application/json":
                            result_obj.json = output.get("json")

                        results.append(result_obj)

                        # Call the results callback if provided
                        if on_results:
                            on_results(output)

                    return Execution(
                        text=stdout if not error else None,
                        logs=logs,
                        results=results,
                        error=error,
                        created_at=time.time(),
                        finished_at=time.time(),
                    )
                else:
                    # If no text output, return the original execution
                    return execution

            except Exception as e:
                # If we can't parse the JSON, return the original execution
                return execution

        except Exception as e:
            raise CodeExecutionError(f"Error executing code: {str(e)}")

    def install_package(self, package: str, version: Optional[str] = None) -> bool:
        """
        Install a Python package in the sandbox.

        Args:
            package: Package name
            version: Optional version specification

        Returns:
            True if the package was installed successfully
        """
        try:
            # Build the pip install command
            cmd = f"pip install {package}"
            if version:
                cmd = f"pip install {package}=={version}"

            # Execute the command
            exit_code, output = self.sandbox._container.exec_run(cmd)

            if exit_code != 0:
                raise CodeExecutionError(
                    f"Failed to install package: {output.decode('utf-8')}"
                )

            return True

        except Exception as e:
            if isinstance(e, CodeExecutionError):
                raise
            raise CodeExecutionError(f"Error installing package: {str(e)}")

    def get_installed_packages(self) -> List[Dict[str, str]]:
        """
        Get a list of installed Python packages.

        Returns:
            List of package info dictionaries with name and version
        """
        try:
            # Execute pip list in JSON format
            exit_code, output = self.sandbox._container.exec_run(
                "pip list --format=json"
            )

            if exit_code != 0:
                raise CodeExecutionError(
                    f"Failed to list packages: {output.decode('utf-8')}"
                )

            # Parse the JSON output
            try:
                packages = json.loads(output.decode("utf-8"))
                return packages
            except json.JSONDecodeError:
                # Fallback to text format if JSON fails
                exit_code, output = self.sandbox._container.exec_run("pip list")
                if exit_code != 0:
                    return []

                result = []
                lines = output.decode("utf-8").splitlines()[2:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        result.append({"name": parts[0], "version": parts[1]})
                return result

        except Exception as e:
            if isinstance(e, CodeExecutionError):
                raise
            raise CodeExecutionError(f"Error listing packages: {str(e)}")

    def reset(self) -> bool:
        """
        Reset the notebook environment.

        Returns:
            True if the environment was reset successfully
        """
        try:
            # Kill the Jupyter kernel if running
            if self._kernel_id:
                try:
                    self.sandbox._container.exec_run(
                        f"jupyter kernelspec remove -f {self._kernel_id}"
                    )
                except Exception:
                    pass
                self._kernel_id = None

            # Restart the container to fully reset the environment
            self.sandbox._container.restart()

            return True

        except Exception as e:
            raise CodeExecutionError(f"Error resetting notebook: {str(e)}")
