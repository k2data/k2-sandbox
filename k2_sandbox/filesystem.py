"""Filesystem operations for the K2 Sandbox."""

import os
import io
import tempfile
import tarfile
from typing import Any, Callable, Dict, List, Optional, Union, AsyncIterator, IO

from k2_sandbox.models import FileInfo, WatchHandle, FilesystemEvent
from k2_sandbox.exceptions import FilesystemError, NotFoundError


class Filesystem:
    """
    Interface for filesystem operations within a Docker sandbox.

    Provides methods to read, write, list, and manage files and directories in the sandbox.
    """

    def __init__(self, sandbox):
        """
        Initialize the Filesystem interface.

        Args:
            sandbox: The Sandbox instance to operate on
        """
        self.sandbox = sandbox

    def list(self, path: str, user: Optional[str] = "user") -> List[FileInfo]:
        """
        List files and directories at the specified path.

        Args:
            path: Directory path to list contents of
            user: User context (usually ignored in Docker implementation)

        Returns:
            List of FileInfo objects representing the directory contents
        """
        try:
            # Use ls command to list directory contents
            exit_code, output = self.sandbox._container.exec_run(f"ls -la {path}")
            if exit_code != 0:
                if "No such file or directory" in output.decode("utf-8"):
                    raise NotFoundError(f"Path not found: {path}")
                raise FilesystemError(
                    f"Failed to list directory: {output.decode('utf-8')}"
                )

            # Parse the output
            lines = output.decode("utf-8").splitlines()
            if len(lines) <= 1:  # Empty directory or error
                return []

            # Skip the first line (total) and parse the rest
            result = []
            for line in lines[1:]:
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) < 9:
                    continue

                # Parse permissions to determine if it's a directory
                is_dir = parts[0].startswith("d")
                name = " ".join(parts[8:])
                # Skip . and .. entries
                if name in [".", ".."]:
                    continue

                # Get size
                size = int(parts[4])

                result.append(
                    FileInfo(
                        name=name,
                        is_dir=is_dir,
                        size=size,
                        path=os.path.join(path, name),
                    )
                )

            return result

        except Exception as e:
            if isinstance(e, (NotFoundError, FilesystemError)):
                raise
            raise FilesystemError(f"Error listing directory: {str(e)}")

    def read(
        self, path: str, format: str = "text", user: Optional[str] = "user"
    ) -> Union[str, bytes]:
        """
        Read the content of a file.

        Args:
            path: File path to read
            format: Return format ('text' or 'bytes')
            user: User context (usually ignored in Docker implementation)

        Returns:
            File content as string or bytes depending on format
        """
        try:
            # Create a temporary directory to extract the file
            with tempfile.TemporaryDirectory() as temp_dir:
                # Generate stream of the file as a tar
                bits, stat = self.sandbox._container.get_archive(path)

                # Write the tar stream to a file
                tar_path = os.path.join(temp_dir, "archive.tar")
                with open(tar_path, "wb") as f:
                    for chunk in bits:
                        f.write(chunk)

                # Extract the file from the tar
                with tarfile.open(tar_path) as tar:
                    file_name = os.path.basename(path)
                    tar.extract(file_name, temp_dir)

                    # Read the extracted file
                    extracted_path = os.path.join(temp_dir, file_name)
                    if format == "bytes":
                        with open(extracted_path, "rb") as f:
                            return f.read()
                    else:  # format == "text"
                        with open(extracted_path, "r", encoding="utf-8") as f:
                            return f.read()

        except Exception as e:
            if "No such file or directory" in str(e):
                raise NotFoundError(f"File not found: {path}")
            raise FilesystemError(f"Error reading file: {str(e)}")

    def write(
        self, path: str, data: Union[str, bytes, IO], user: Optional[str] = "user"
    ) -> FileInfo:
        """
        Write data to a file.

        Args:
            path: File path to write
            data: Content to write (string, bytes, or file-like object)
            user: User context (usually ignored in Docker implementation)

        Returns:
            FileInfo about the written file
        """
        try:
            # Ensure the directory exists
            dir_path = os.path.dirname(path)
            if dir_path:
                self.sandbox._container.exec_run(f"mkdir -p {dir_path}")

            # Write data to a temporary file
            with tempfile.TemporaryDirectory() as temp_dir:
                file_name = os.path.basename(path)
                tmp_path = os.path.join(temp_dir, file_name)

                # Write the data to the temporary file
                if isinstance(data, str):
                    with open(tmp_path, "w", encoding="utf-8") as f:
                        f.write(data)
                elif isinstance(data, bytes):
                    with open(tmp_path, "wb") as f:
                        f.write(data)
                elif hasattr(data, "read"):
                    with open(tmp_path, "wb") as f:
                        while True:
                            chunk = data.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            if isinstance(chunk, str):
                                f.write(chunk.encode("utf-8"))
                            else:
                                f.write(chunk)
                else:
                    raise ValueError(
                        "Data must be a string, bytes, or file-like object"
                    )

                # Create a tar archive
                tar_path = os.path.join(temp_dir, "archive.tar")
                with tarfile.open(tar_path, "w") as tar:
                    tar.add(tmp_path, arcname=file_name)

                # Copy the tar archive to the container
                with open(tar_path, "rb") as f:
                    self.sandbox._container.put_archive(dir_path or "/", f.read())

            # Get file info
            is_dir = False
            size = None
            try:
                exit_code, output = self.sandbox._container.exec_run(
                    f"stat -c '%s' {path}"
                )
                if exit_code == 0:
                    size = int(output.decode("utf-8").strip())
            except Exception:
                pass

            return FileInfo(
                name=os.path.basename(path), is_dir=is_dir, size=size, path=path
            )

        except Exception as e:
            raise FilesystemError(f"Error writing file: {str(e)}")

    def remove(self, path: str, user: Optional[str] = "user") -> None:
        """
        Remove a file or directory.

        Args:
            path: Path to remove
            user: User context (usually ignored in Docker implementation)
        """
        try:
            # Check if the path exists
            exit_code, output = self.sandbox._container.exec_run(f"test -e {path}")
            if exit_code != 0:
                raise NotFoundError(f"Path not found: {path}")

            # Remove the path recursively
            exit_code, output = self.sandbox._container.exec_run(f"rm -rf {path}")
            if exit_code != 0:
                raise FilesystemError(
                    f"Failed to remove path: {output.decode('utf-8')}"
                )

        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise FilesystemError(f"Error removing path: {str(e)}")

    def rename(
        self, old_path: str, new_path: str, user: Optional[str] = "user"
    ) -> FileInfo:
        """
        Rename or move a file or directory.

        Args:
            old_path: Current path
            new_path: Target path
            user: User context (usually ignored in Docker implementation)

        Returns:
            FileInfo about the renamed entity
        """
        try:
            # Check if the source path exists
            exit_code, output = self.sandbox._container.exec_run(f"test -e {old_path}")
            if exit_code != 0:
                raise NotFoundError(f"Path not found: {old_path}")

            # Ensure the target directory exists
            new_dir = os.path.dirname(new_path)
            if new_dir:
                self.sandbox._container.exec_run(f"mkdir -p {new_dir}")

            # Move the file/directory
            exit_code, output = self.sandbox._container.exec_run(
                f"mv {old_path} {new_path}"
            )
            if exit_code != 0:
                raise FilesystemError(
                    f"Failed to rename path: {output.decode('utf-8')}"
                )

            # Get info about the renamed entity
            is_dir = False
            size = None
            try:
                exit_code, output = self.sandbox._container.exec_run(
                    f"test -d {new_path}"
                )
                is_dir = exit_code == 0

                if not is_dir:
                    exit_code, output = self.sandbox._container.exec_run(
                        f"stat -c '%s' {new_path}"
                    )
                    if exit_code == 0:
                        size = int(output.decode("utf-8").strip())
            except Exception:
                pass

            return FileInfo(
                name=os.path.basename(new_path), is_dir=is_dir, size=size, path=new_path
            )

        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise FilesystemError(f"Error renaming path: {str(e)}")

    def make_dir(self, path: str, user: Optional[str] = "user") -> bool:
        """
        Create a directory and parent directories if needed.

        Args:
            path: Directory path to create
            user: User context (usually ignored in Docker implementation)

        Returns:
            True if the directory was created successfully
        """
        try:
            exit_code, output = self.sandbox._container.exec_run(f"mkdir -p {path}")
            if exit_code != 0:
                raise FilesystemError(
                    f"Failed to create directory: {output.decode('utf-8')}"
                )
            return True

        except Exception as e:
            raise FilesystemError(f"Error creating directory: {str(e)}")

    def exists(self, path: str, user: Optional[str] = "user") -> bool:
        """
        Check if a file or directory exists.

        Args:
            path: Path to check
            user: User context (usually ignored in Docker implementation)

        Returns:
            True if the path exists
        """
        try:
            exit_code, _ = self.sandbox._container.exec_run(f"test -e {path}")
            return exit_code == 0

        except Exception as e:
            raise FilesystemError(f"Error checking path existence: {str(e)}")

    def watch_dir(
        self,
        path: str,
        on_event: Callable[[FilesystemEvent], Any],
        user: Optional[str] = "user",
    ) -> WatchHandle:
        """
        Watch a directory for filesystem events.

        This is a placeholder implementation. In a real implementation, you might
        use inotify or a similar mechanism.

        Args:
            path: Directory path to watch
            on_event: Callback for filesystem events
            user: User context (usually ignored in Docker implementation)

        Returns:
            A WatchHandle for managing the watch
        """
        # This is a placeholder. A real implementation would need to run a process
        # in the container to watch the directory and stream events back.
        watch_id = str(hash(f"{path}:{id(on_event)}"))

        # Check if the directory exists
        if not self.exists(path):
            raise NotFoundError(f"Directory not found: {path}")

        return WatchHandle(id=watch_id, path=path)
