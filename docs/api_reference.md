# K2 Sandbox API Reference

This document provides a reference for the K2 Sandbox Python SDK.

## Sandbox

The main class for creating and interacting with sandboxes.

### Creating Sandboxes

```python
# Create a new sandbox
sandbox = Sandbox(
    template="k2sandbox/python:latest",  # Docker image template to use
    api_key=None,  # K2 Sandbox API key (defaults to K2_API_KEY env var)
    cwd="/home/user",  # Initial working directory
    envs={},  # Environment variables
    timeout=300,  # Inactivity timeout in seconds
    metadata={},  # Custom metadata for the sandbox
    request_timeout=None,  # API request timeout in seconds
)

# Create a sandbox using the class method
sandbox = Sandbox.create(
    template="k2sandbox/python:latest",
    # ... other options same as above
)

# Connect to an existing sandbox by ID
sandbox = Sandbox.connect(
    sandbox_id="your-sandbox-id",
    api_key=None,
    # ... other options same as above
)

# Use a sandbox as a context manager
with Sandbox() as sandbox:
    # Sandbox will be automatically closed when the block exits
    pass
```

### Running Code

```python
# Execute Python code
execution = sandbox.run_code(
    code="print('Hello, world!')",
    on_stdout=lambda data: print(f"STDOUT: {data['line']}"),  # Callback for stdout lines
    on_stderr=lambda data: print(f"STDERR: {data['line']}"),  # Callback for stderr lines
    on_results=None,  # Callback for rich results (plots, etc.)
    timeout=None,  # Execution timeout in seconds
    cwd=None,  # Working directory for execution
    envs=None,  # Environment variables for execution
)

# Access execution results
print(execution.text)  # The output of the execution
print(execution.stdout)  # Concatenated stdout lines
print(execution.stderr)  # Concatenated stderr lines
print(execution.is_error)  # True if execution resulted in error
```

### Sandbox Management

```python
# Close the sandbox
sandbox.close()

# Kill the sandbox forcefully
sandbox.kill()

# Kill a sandbox by ID (class method)
Sandbox.kill(sandbox_id="your-sandbox-id")

# Check if the sandbox is running
is_running = sandbox.is_running()

# Set the inactivity timeout
sandbox.set_timeout(timeout=600)  # 10 minutes

# Set timeout for a sandbox by ID (class method)
Sandbox.set_timeout(sandbox_id="your-sandbox-id", timeout=600)

# List all sandboxes (class method)
sandboxes = Sandbox.list()
```

## Filesystem

Interface for filesystem operations within a sandbox.

```python
# Access the filesystem interface
filesystem = sandbox.filesystem

# List files in a directory
files = filesystem.list(path="/home/user")
for file in files:
    print(f"{file.name} ({file.size} bytes, {'directory' if file.is_dir else 'file'})")

# Read a file
content = filesystem.read(path="/home/user/file.txt")
binary_content = filesystem.read(path="/home/user/image.png", format="bytes")

# Write to a file
filesystem.write(path="/home/user/file.txt", data="Hello, world!")
with open("local_file.png", "rb") as f:
    filesystem.write(path="/home/user/image.png", data=f)

# Remove a file or directory
filesystem.remove(path="/home/user/file.txt")

# Rename/move a file or directory
filesystem.rename(old_path="/home/user/old_name.txt", new_path="/home/user/new_name.txt")

# Create a directory
filesystem.make_dir(path="/home/user/new_directory")

# Check if a file or directory exists
exists = filesystem.exists(path="/home/user/file.txt")

# Watch a directory for changes
def on_fs_event(event):
    print(f"Event: {event.event_type} on {event.path}")

watch_handle = filesystem.watch_dir(path="/home/user", on_event=on_fs_event)
# ... do some operations ...
watch_handle.stop()  # Stop watching
```

## Process

Interface for process management within a sandbox.

```python
# Access the process interface
process = sandbox.process

# Run a command and wait for completion
result = process.start(
    cmd="ls -la",
    on_stdout=lambda data: print(f"STDOUT: {data['line']}"),  # Callback for stdout lines
    on_stderr=lambda data: print(f"STDERR: {data['line']}"),  # Callback for stderr lines
    timeout=60,  # Execution timeout in seconds
    cwd=None,  # Working directory for the process
    envs=None,  # Environment variables for the process
    background=False  # Whether to run in background
)
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.stdout}")
print(f"Error: {result.stderr}")

# Run a command in the background
handle = process.start(
    cmd="sleep 10 && echo 'Done'",
    background=True
)
# Do something else while the process runs
print(f"Process is running with PID: {handle.pid}")
# Wait for the process to complete
result = handle.wait()
# Send data to the process stdin
handle.send_stdin("Some input data\n")
# Kill the process
handle.kill()

# List running processes
processes = process.list()
for proc in processes:
    print(f"PID: {proc.pid}, Command: {proc.cmd}")

# Kill a process by PID
process.kill(pid=12345)
```

## Terminal

Interface for terminal (PTY) interaction within a sandbox.

```python
# Access the terminal interface
terminal = sandbox.terminal

# Start a new PTY session
def on_terminal_data(data):
    print(f"Terminal output: {data.decode('utf-8', errors='ignore')}")

pty = terminal.start(
    on_data=on_terminal_data,  # Callback for terminal output
    size=(24, 80),  # Terminal dimensions (rows, cols)
    cmd=None,  # Command to run (defaults to bash or sh)
    cwd=None,  # Working directory
    envs=None,  # Environment variables
)

# Send data to the terminal
terminal.send_data(pid=pty.pid, data=b"ls -la\n")

# Resize the terminal
terminal.resize(pid=pty.pid, size=(30, 100))

# Kill the terminal session
terminal.kill(pid=pty.pid)

# PTY handle methods
pty.send_data(b"echo 'Hello'\n")
pty.resize(24, 80)
pty.kill()
```

## Notebook

Interface for Jupyter notebook-like code execution with rich output.

```python
# Access the notebook interface
notebook = sandbox.notebook

# Execute code that might produce rich output (e.g., plots, HTML, etc.)
execution = notebook.execute(
    code="import matplotlib.pyplot as plt; plt.plot([1, 2, 3]); plt.show()",
    on_stdout=lambda data: print(f"STDOUT: {data['line']}"),
    on_stderr=lambda data: print(f"STDERR: {data['line']}"),
    on_results=lambda data: print(f"Result: {data['mime_type']}"),
    timeout=None,
    cwd=None,
    metadata=None,
)

# Access rich results
for result in execution.results:
    print(f"MIME type: {result.mime_type}")
    if result.mime_type == "image/png":
        # Save the plot to a file
        with open("plot.png", "wb") as f:
            f.write(result.image_data)
    elif result.mime_type == "text/html":
        print(f"HTML content: {result.html}")

# Install a Python package
notebook.install_package("pandas")
notebook.install_package("numpy", version="1.20.0")

# Get a list of installed packages
packages = notebook.get_installed_packages()
for pkg in packages:
    print(f"{pkg['name']} {pkg['version']}")

# Reset the notebook environment
notebook.reset()
```
