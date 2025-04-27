from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
import docker
from typing import Dict, List, Optional
import uuid

from app.models import (
    SandboxCreate,
    SandboxResponse,
    SandboxList,
    SandboxAction,
    CodeExecution,
    ExecutionResponse,
    FileSystemAction,
    FileSystemResponse,
    CommandExecution,
    CommandResponse,
)
from app.sandbox_manager import SandboxManager

app = FastAPI(
    title="K2 Sandbox API",
    description="API for managing Docker-based sandboxes",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the sandbox manager
sandbox_manager = SandboxManager()


@app.get("/")
async def root():
    return {"message": "K2 Sandbox Management API"}


@app.post("/sandboxes", response_model=SandboxResponse)
async def create_sandbox(sandbox: SandboxCreate):
    """Create a new sandbox container"""
    try:
        sandbox_id = sandbox_manager.create_sandbox(
            template=sandbox.template,
            cwd=sandbox.cwd,
            envs=sandbox.envs,
            timeout=sandbox.timeout,
            metadata=sandbox.metadata,
        )
        return {"sandbox_id": sandbox_id, "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sandboxes", response_model=SandboxList)
async def list_sandboxes():
    """List all available sandboxes"""
    try:
        sandboxes = sandbox_manager.list_sandboxes()
        return {"sandboxes": sandboxes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sandboxes/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(sandbox_id: str):
    """Get information about a specific sandbox"""
    try:
        if not sandbox_manager.is_sandbox_running(sandbox_id):
            raise HTTPException(status_code=404, detail="Sandbox not found")
        return {"sandbox_id": sandbox_id, "status": "running"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/{sandbox_id}/actions", response_model=SandboxResponse)
async def perform_sandbox_action(
    sandbox_id: str, action: SandboxAction, background_tasks: BackgroundTasks
):
    """Perform an action on a sandbox (stop, kill, restart)"""
    try:
        if not sandbox_manager.is_sandbox_running(sandbox_id):
            raise HTTPException(status_code=404, detail="Sandbox not found")

        if action.action == "stop":
            sandbox_manager.stop_sandbox(sandbox_id)
            return {"sandbox_id": sandbox_id, "status": "stopped"}
        elif action.action == "kill":
            sandbox_manager.kill_sandbox(sandbox_id)
            return {"sandbox_id": sandbox_id, "status": "killed"}
        elif action.action == "restart":
            sandbox_manager.restart_sandbox(sandbox_id)
            return {"sandbox_id": sandbox_id, "status": "running"}
        elif action.action == "set_timeout":
            if action.timeout is None:
                raise HTTPException(status_code=400, detail="Timeout value is required")
            sandbox_manager.set_timeout(sandbox_id, action.timeout)
            return {
                "sandbox_id": sandbox_id,
                "status": "running",
                "timeout": action.timeout,
            }
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported action: {action.action}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sandboxes/{sandbox_id}")
async def delete_sandbox(sandbox_id: str):
    """Delete a sandbox"""
    try:
        if not sandbox_manager.is_sandbox_running(sandbox_id):
            raise HTTPException(status_code=404, detail="Sandbox not found")

        sandbox_manager.kill_sandbox(sandbox_id)
        return {"sandbox_id": sandbox_id, "status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/{sandbox_id}/code", response_model=ExecutionResponse)
async def execute_code(sandbox_id: str, execution: CodeExecution):
    """Execute code in a sandbox"""
    try:
        if not sandbox_manager.is_sandbox_running(sandbox_id):
            raise HTTPException(status_code=404, detail="Sandbox not found")

        result = sandbox_manager.run_code(
            sandbox_id=sandbox_id,
            code=execution.code,
            language=execution.language,
            timeout=execution.timeout,
            cwd=execution.cwd,
            envs=execution.envs,
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/{sandbox_id}/command", response_model=CommandResponse)
async def execute_command(sandbox_id: str, execution: CommandExecution):
    """Execute a command in a sandbox"""
    try:
        if not sandbox_manager.is_sandbox_running(sandbox_id):
            raise HTTPException(status_code=404, detail="Sandbox not found")

        result = sandbox_manager.execute_command(
            sandbox_id=sandbox_id,
            command=execution.command,
            cwd=execution.cwd,
            envs=execution.envs,
            timeout=execution.timeout,
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sandboxes/{sandbox_id}/filesystem", response_model=FileSystemResponse)
async def file_system_action(sandbox_id: str, action: FileSystemAction):
    """Perform filesystem operations in a sandbox"""
    try:
        if not sandbox_manager.is_sandbox_running(sandbox_id):
            raise HTTPException(status_code=404, detail="Sandbox not found")

        if action.action == "list":
            result = sandbox_manager.list_files(sandbox_id=sandbox_id, path=action.path)
            return {"files": result}
        elif action.action == "read":
            if not action.path:
                raise HTTPException(status_code=400, detail="Path is required")
            content = sandbox_manager.read_file(sandbox_id=sandbox_id, path=action.path)
            return {"content": content}
        elif action.action == "write":
            if not action.path or action.content is None:
                raise HTTPException(
                    status_code=400, detail="Path and content are required"
                )
            sandbox_manager.write_file(
                sandbox_id=sandbox_id, path=action.path, content=action.content
            )
            return {"message": "File written successfully"}
        elif action.action == "delete":
            if not action.path:
                raise HTTPException(status_code=400, detail="Path is required")
            sandbox_manager.delete_file(sandbox_id=sandbox_id, path=action.path)
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported action: {action.action}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
