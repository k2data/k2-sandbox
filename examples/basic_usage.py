"""
Basic usage examples of the K2 Sandbox SDK.

This example demonstrates:
1. Creating a sandbox
2. Running Python code
3. Working with files (commented out)
4. Running processes (commented out)
5. Using the notebook interface (commented out)
"""

import time
import sys
import os

# Add the project root directory to the Python path so we can import the k2_sandbox module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from k2_sandbox import Sandbox


def main():
    print("Creating a new sandbox...")
    with Sandbox(template="k2-sandbox/code-interpreter:latest") as sandbox:
        # 1. Execute simple Python code
        print("\n=== Running Python code ===")
        print(f"Sandbox ID: {sandbox.sandbox_id}")
        execution = sandbox.run_code("x = 41; x + 1; x", language="python")
        print(f"Result: {execution.text}")  # Output: 42
        print(f"Execution: {execution}")

        # # 2. File operations
        # print("\n=== File operations ===")
        # # Write a file
        # content = "Hello, K2 Sandbox!"
        # sandbox.filesystem.write("/home/user/hello.txt", content)

        # # Read the file
        # read_content = sandbox.filesystem.read("/home/user/hello.txt")
        # print(f"Read file content: {read_content}")

        # # List directory
        # files = sandbox.filesystem.list("/home/user")
        # print("Files in home directory:")
        # for file in files:
        #     print(f"  - {file.name} {'(dir)' if file.is_dir else ''}")

        # # 3. Process execution
        # print("\n=== Process execution ===")
        # # Run a command and capture output
        # result = sandbox.process.start("ls -la /home/user")
        # print(f"Process stdout:\n{result.stdout}")

        # # Run a command in the background
        # print("Starting a background process...")
        # handle = sandbox.process.start(
        #     "sleep 2 && echo 'Background task finished'", background=True
        # )
        # print(f"Process is running with PID: {handle.pid}")

        # # Wait for completion
        # execution = handle.wait()
        # print(f"Background process output: {execution.stdout}")

        # # 4. Notebook-style execution with rich output
        # print("\n=== Notebook execution ===")
        # # Install matplotlib if not already installed
        # try:
        #     sandbox.notebook.install_package("matplotlib")
        #     print("Matplotlib installed")
        # except Exception as e:
        #     print(f"Matplotlib installation failed or already installed: {e}")

        # # Execute code that generates a plot
        # plot_code = """
        # import matplotlib.pyplot as plt
        # import numpy as np

        # # Generate some data
        # x = np.linspace(0, 10, 100)
        # y = np.sin(x)

        # # Create a plot
        # plt.figure(figsize=(8, 4))
        # plt.plot(x, y, 'b-', label='sin(x)')
        # plt.title('Sine Function')
        # plt.xlabel('x')
        # plt.ylabel('sin(x)')
        # plt.grid(True)
        # plt.legend()
        # plt.tight_layout()
        # plt.show()
        # """

        # execution = sandbox.notebook.execute(plot_code)

        # if execution.results:
        #     print(f"Generated {len(execution.results)} rich output(s)")
        #     for i, result in enumerate(execution.results):
        #         print(f"  Result {i+1}: {result.mime_type}")
        #         if result.mime_type == "image/png" and result.png:
        #             # In a real application, you could save this to a file or display it
        #             print(f"  PNG data length: {len(result.png)} chars")
        # else:
        #     print("No rich outputs generated")

        # # 5. Working with environment variables
        # print("\n=== Environment variables ===")
        # env_code = """
        # import os
        # print(f"Current environment: {os.environ.get('ENV_TYPE', 'not set')}")
        # """

        # # Execute with a custom environment variable
        # execution = sandbox.run_code(env_code, envs={"ENV_TYPE": "testing"})
        # print(f"Output: {execution.text}")

        print("\n=== Sandbox completed ===")
        # The sandbox will be automatically closed by the context manager


if __name__ == "__main__":
    main()
