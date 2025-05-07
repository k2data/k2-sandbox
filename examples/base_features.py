"""
Demonstrates file operations and process execution in a K2 Base Sandbox.
"""

import time
import sys
import os

# Add the project root directory to the Python path so we can import the k2_sandbox module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from k2_sandbox import Sandbox


def main():
    load_dotenv()  # Load environment variables from .env file
    start_time = time.time()

    print("Creating a base sandbox for file and process operations...")
    with Sandbox() as sandbox:
        creation_duration = time.time() - start_time
        print(f"Sandbox creation duration: {creation_duration:.2f} seconds")

        # 1. File operations
        print("\n=== File operations ===")
        # Write a file
        write_start_time = time.time()
        content = "Hello, K2 Sandbox!"
        sandbox.filesystem.write("/home/user/hello.txt", content)
        write_duration = time.time() - write_start_time
        print(f"File write duration: {write_duration:.2f} seconds")

        # Read the file
        read_start_time = time.time()
        read_content = sandbox.filesystem.read("/home/user/hello.txt")
        read_duration = time.time() - read_start_time
        print(f"Read file content: {read_content}")
        print(f"File read duration: {read_duration:.2f} seconds")

        # List directory
        list_start_time = time.time()
        files = sandbox.filesystem.list("/home/user")
        list_duration = time.time() - list_start_time
        print("Files in home directory:")
        for file in files:
            print(f"  - {file.name} {'(dir)' if file.is_dir else ''}")
        print(f"Directory listing duration: {list_duration:.2f} seconds")

        # 2. Process execution
        print("\n=== Process execution ===")
        # Run a command and capture output
        cmd_start_time = time.time()
        result = sandbox.process.start("ls -la /home/user")
        cmd_duration = time.time() - cmd_start_time
        print(f"Process stdout:\n{result.stdout}")
        print(f"Process execution duration: {cmd_duration:.2f} seconds")

        # Run a command in the background
        print("Starting a background process...")
        bg_start_time = time.time()
        handle = sandbox.process.start(
            "sleep 2 && echo 'Background task finished'", background=True
        )
        print(f"Process is running with PID: {handle.pid}")

        # Wait for completion
        execution = handle.wait()
        bg_duration = time.time() - bg_start_time
        print(f"Background process output: {execution.stdout}")
        print(f"Background process duration: {bg_duration:.2f} seconds")

        print("\n=== Sandbox completed ===")
        total_duration = time.time() - start_time
        print(f"Total execution duration: {total_duration:.2f} seconds")


if __name__ == "__main__":
    main()
