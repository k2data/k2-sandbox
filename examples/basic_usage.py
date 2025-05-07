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

from dotenv import load_dotenv
from k2_sandbox import Sandbox


def main():
    load_dotenv()  # Load environment variables from .env file
    start_time = time.time()
    print("Creating a new sandbox...")
    with Sandbox.create_code_interpreter() as sandbox:
        creation_duration = time.time() - start_time
        print(f"Sandbox creation duration: {creation_duration:.2f} seconds")

        # 1. Execute simple Python code
        print("\n=== Running Python code ===")
        print(f"Sandbox ID: {sandbox.sandbox_id}")

        code_start_time = time.time()
        execution = sandbox.run_code("x = 41; x + 1; x", language="python")
        code_duration = time.time() - code_start_time

        print(f"Result: {execution.text}")  # Output: 42
        print(f"Execution: {execution}")
        print(f"Code execution duration: {code_duration:.2f} seconds")

        # # 2. File operations
        # print("\n=== File operations ===")
        # # Write a file
        # write_start_time = time.time()
        # content = "Hello, K2 Sandbox!"
        # sandbox.filesystem.write("/home/user/hello.txt", content)
        # write_duration = time.time() - write_start_time
        # print(f"File write duration: {write_duration:.2f} seconds")

        # # Read the file
        # read_start_time = time.time()
        # read_content = sandbox.filesystem.read("/home/user/hello.txt")
        # read_duration = time.time() - read_start_time
        # print(f"Read file content: {read_content}")
        # print(f"File read duration: {read_duration:.2f} seconds")

        # # List directory
        # list_start_time = time.time()
        # files = sandbox.filesystem.list("/home/user")
        # list_duration = time.time() - list_start_time
        # print("Files in home directory:")
        # for file in files:
        #     print(f"  - {file.name} {'(dir)' if file.is_dir else ''}")
        # print(f"Directory listing duration: {list_duration:.2f} seconds")

        # # 3. Process execution
        # print("\n=== Process execution ===")
        # # Run a command and capture output
        # cmd_start_time = time.time()
        # result = sandbox.process.start("ls -la /home/user")
        # cmd_duration = time.time() - cmd_start_time
        # print(f"Process stdout:\n{result.stdout}")
        # print(f"Process execution duration: {cmd_duration:.2f} seconds")

        # # Run a command in the background
        # print("Starting a background process...")
        # bg_start_time = time.time()
        # handle = sandbox.process.start(
        #     "sleep 2 && echo 'Background task finished'", background=True
        # )
        # print(f"Process is running with PID: {handle.pid}")

        # # Wait for completion
        # execution = handle.wait()
        # bg_duration = time.time() - bg_start_time
        # print(f"Background process output: {execution.stdout}")
        # print(f"Background process duration: {bg_duration:.2f} seconds")

        # # 4. Notebook-style execution with rich output
        # print("\n=== Notebook execution ===")
        # # Install matplotlib if not already installed
        # install_start_time = time.time()
        # try:
        #     sandbox.notebook.install_package("matplotlib")
        #     install_duration = time.time() - install_start_time
        #     print("Matplotlib installed")
        #     print(f"Package installation duration: {install_duration:.2f} seconds")
        # except Exception as e:
        #     install_duration = time.time() - install_start_time
        #     print(f"Matplotlib installation failed or already installed: {e}")
        #     print(f"Package installation attempt duration: {install_duration:.2f} seconds")

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

        # plot_start_time = time.time()
        # execution = sandbox.notebook.execute(plot_code)
        # plot_duration = time.time() - plot_start_time

        # if execution.results:
        #     print(f"Generated {len(execution.results)} rich output(s)")
        #     for i, result in enumerate(execution.results):
        #         print(f"  Result {i+1}: {result.mime_type}")
        #         if result.mime_type == "image/png" and result.png:
        #             # In a real application, you could save this to a file or display it
        #             print(f"  PNG data length: {len(result.png)} chars")
        # else:
        #     print("No rich outputs generated")
        # print(f"Plot generation duration: {plot_duration:.2f} seconds")

        # # 5. Working with environment variables
        # print("\n=== Environment variables ===")
        # env_code = """
        # import os
        # print(f"Current environment: {os.environ.get('ENV_TYPE', 'not set')}")
        # """

        # # Execute with a custom environment variable
        # env_start_time = time.time()
        # execution = sandbox.run_code(env_code, envs={"ENV_TYPE": "testing"})
        # env_duration = time.time() - env_start_time
        # print(f"Output: {execution.text}")
        # print(f"Environment variable test duration: {env_duration:.2f} seconds")

        print("\n=== Sandbox completed ===")
        total_duration = time.time() - start_time
        print(f"Total execution duration: {total_duration:.2f} seconds")
        # The sandbox will be automatically closed by the context manager


if __name__ == "__main__":
    main()
