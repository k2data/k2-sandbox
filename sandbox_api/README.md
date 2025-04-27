# K2 Sandbox API

A standalone RESTful API server for managing Docker-based sandboxes. This service handles the creation, management, and interaction with Docker containers for isolated code execution environments.

## Features

- Create, list, and manage Docker-based sandboxes
- Execute code in sandboxes with various languages
- Execute shell commands in sandboxes
- Perform filesystem operations (read, write, list, delete)
- Configure sandbox timeouts and metadata
- Manage sandbox lifecycle (start, stop, restart, kill)

## Prerequisites

- Python 3.8+
- Docker

## Installation

1. Clone the repository
2. Install dependencies:

```bash
cd sandbox_api
pip install -r requirements.txt
```

## Usage

Start the API server:

```bash
cd sandbox_api
python main.py
```

The server will start on port 8000 by default.

## API Endpoints

### Sandbox Management

- `GET /` - API root, returns a welcome message
- `POST /sandboxes` - Create a new sandbox
- `GET /sandboxes` - List all available sandboxes
- `GET /sandboxes/{sandbox_id}` - Get information about a specific sandbox
- `DELETE /sandboxes/{sandbox_id}` - Delete a sandbox
- `POST /sandboxes/{sandbox_id}/actions` - Perform actions on a sandbox (stop, kill, restart, set_timeout)

### Code and Command Execution

- `POST /sandboxes/{sandbox_id}/code` - Execute code in a sandbox
- `POST /sandboxes/{sandbox_id}/command` - Execute a shell command in a sandbox

### Filesystem Operations

- `POST /sandboxes/{sandbox_id}/filesystem` - Perform filesystem operations (list, read, write, delete)

## Examples

### Create a Sandbox

```bash
curl -X POST "http://localhost:8000/sandboxes" \
  -H "Content-Type: application/json" \
  -d '{
    "template": "k2data/sandbox-base:latest",
    "cwd": "/home/user",
    "envs": {"ENV_VAR": "value"},
    "timeout": 300,
    "metadata": {"purpose": "testing"}
  }'
```

### Execute Code

```bash
curl -X POST "http://localhost:8000/sandboxes/{sandbox_id}/code" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(\"Hello from sandbox!\")",
    "language": "python"
  }'
```

### Execute Command

```bash
curl -X POST "http://localhost:8000/sandboxes/{sandbox_id}/command" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ls -la",
    "cwd": "/home/user"
  }'
```

### List Files

```bash
curl -X POST "http://localhost:8000/sandboxes/{sandbox_id}/filesystem" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "list",
    "path": "/home/user"
  }'
```

## Documentation

The API documentation is available at `/docs` when the server is running:

```
http://localhost:8000/docs
```

## License

[MIT License](LICENSE)
