"""
Demonstrates notebook-style execution and environment variables in a K2 Code Interpreter Sandbox.
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

    print("Creating a code interpreter sandbox for notebook and env vars...")
    with Sandbox.create_code_interpreter() as sandbox:
        creation_duration = time.time() - start_time
        print(f"Sandbox creation duration: {creation_duration:.2f} seconds")

        # 4. Notebook-style execution with rich output
        print("\n=== Notebook execution ===")
        # Install matplotlib if not already installed
        install_start_time = time.time()
        try:
            sandbox.notebook.install_package("matplotlib")
            install_duration = time.time() - install_start_time
            print("Matplotlib installed")
            print(f"Package installation duration: {install_duration:.2f} seconds")
        except Exception as e:
            install_duration = time.time() - install_start_time
            print(f"Matplotlib installation failed or already installed: {e}")
            print(
                f"Package installation attempt duration: {install_duration:.2f} seconds"
            )

        # Execute code that generates a plot
        plot_code = """
        import matplotlib.pyplot as plt
        import numpy as np

        # Generate some data
        x = np.linspace(0, 10, 100)
        y = np.sin(x)

        # Create a plot
        plt.figure(figsize=(8, 4))
        plt.plot(x, y, 'b-', label='sin(x)')
        plt.title('Sine Function')
        plt.xlabel('x')
        plt.ylabel('sin(x)')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()
        """

        plot_start_time = time.time()
        execution = sandbox.notebook.execute(plot_code)
        plot_duration = time.time() - plot_start_time

        if execution.results:
            print(f"Generated {len(execution.results)} rich output(s)")
            for i, result in enumerate(execution.results):
                print(f"  Result {i+1}: {result.mime_type}")
                if result.mime_type == "image/png" and result.png:
                    # In a real application, you could save this to a file or display it
                    print(f"  PNG data length: {len(result.png)} chars")
        else:
            print("No rich outputs generated")
        print(f"Plot generation duration: {plot_duration:.2f} seconds")

        # 5. Working with environment variables
        print("\n=== Environment variables ===")
        env_code = """
        import os
        print(f"Current environment: {os.environ.get('ENV_TYPE', 'not set')}")
        """

        # Execute with a custom environment variable
        env_start_time = time.time()
        execution = sandbox.run_code(env_code, envs={"ENV_TYPE": "testing"})
        env_duration = time.time() - env_start_time
        print(f"Output: {execution.text}")
        print(f"Environment variable test duration: {env_duration:.2f} seconds")

        print("\n=== Sandbox completed ===")
        total_duration = time.time() - start_time
        print(f"Total execution duration: {total_duration:.2f} seconds")


if __name__ == "__main__":
    main()
