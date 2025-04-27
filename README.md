# K2 Sandbox

K2 Sandbox is a Python SDK for running LLM-generated code in isolated Docker container environments. It provides a secure way to execute untrusted code with filesystem access, network capabilities, and stateful execution.

## Features

- Secure code execution in isolated Docker containers
- Support for Python, JavaScript, and TypeScript execution
- Stateful execution (variable persistence between runs)
- File system operations
- Process management
- Terminal interaction

## Installation

```bash
pip install k2-sandbox
```

## Quick Start

```python
from k2_sandbox import Sandbox

# Create and use a sandbox
with Sandbox() as sandbox:
    # Execute Python code
    execution = sandbox.run_code("x = 41; x + 1")
    print(f"Result: {execution.text}")  # Output: 42

    # Upload a file
    sandbox.filesystem.write("/tmp/data.txt", "Hello, world!")

    # Run a system command
    result = sandbox.process.start("ls -la /tmp")
    print(result.stdout)
```

## Documentation

For detailed documentation, see the [API Reference](docs/api_reference.md).

## License

MIT
