#!/usr/bin/env python3
"""
Script to build Docker image from templates/Dockerfile.
"""

import argparse
import subprocess
import sys
import os


def build_image(image_name, tag, build_args=None, no_cache=False):
    """Build a Docker image using templates/Dockerfile."""
    full_tag = f"{image_name}:{tag}"

    # Build command
    cmd = ["docker", "build"]

    # Add no-cache option if specified
    if no_cache:
        cmd.append("--no-cache")

    # Add build args if any
    if build_args:
        for arg in build_args:
            cmd.extend(["--build-arg", arg])

    # Add image tag and build context
    cmd.extend(["-t", full_tag, "-f", "templates/Dockerfile", "templates"])

    print(f"Building {full_tag}...")
    print(f"Command: {' '.join(cmd)}\n")

    # Execute the command
    result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        print(f"\nSuccessfully built {full_tag}")
        print(f"\nYou can run the image with:")
        print(f"docker run -it {full_tag}")
        return True
    else:
        print(f"\nFailed to build {full_tag}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Build Docker image from templates/Dockerfile"
    )
    parser.add_argument(
        "--name",
        default="k2data/sandbox-code-interpreter",
        help="Name for the image (default: k2data/sandbox-code-interpreter)",
    )
    parser.add_argument(
        "--tag", default="latest", help="Tag for the image (default: latest)"
    )
    parser.add_argument(
        "--build-arg",
        action="append",
        help="Build argument for Docker (can be used multiple times)",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Build without using cache"
    )

    args = parser.parse_args()

    # Check if Docker is available
    try:
        subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Docker is not available. Please install Docker and try again.")
        sys.exit(1)

    # Check if templates/Dockerfile exists
    if not os.path.exists("templates/Dockerfile"):
        print("Error: templates/Dockerfile not found.")
        sys.exit(1)

    # Build the image
    success = build_image(args.name, args.tag, args.build_arg, args.no_cache)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
