"""
Demonstrates basic Python code execution in a K2 Code Interpreter Sandbox.
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

    print("Creating a code interpreter sandbox for simple execution...")
    with Sandbox.create_code_interpreter() as sandbox:
        creation_duration = time.time() - start_time
        print(f"Sandbox creation duration: {creation_duration:.2f} seconds")

        print("\n=== Running Python code ===")
        print(f"Sandbox ID: {sandbox.sandbox_id}")

        code_start_time = time.time()
        execution = sandbox.run_code("x = 41; x + 1; x", language="python")
        code_duration = time.time() - code_start_time

        print(f"Result: {execution.text}")  # Output: 42
        print(f"Execution: {execution}")
        print(f"Code execution duration: {code_duration:.2f} seconds")

        print("\n=== Sandbox completed ===")
        total_duration = time.time() - start_time
        print(f"Total execution duration: {total_duration:.2f} seconds")


if __name__ == "__main__":
    main()
