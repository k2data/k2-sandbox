#!/usr/bin/env python3
"""
Script to build Docker images for K2 Sandbox.
"""

import os
import subprocess
import argparse
import sys
import shutil
import tempfile

# Define the available images
IMAGES = {
    "base": "docker/Dockerfile.base",
}


def build_image(image_name, dockerfile, tag="latest", no_cache=False):
    """Build a Docker image."""
    repo = f"k2data/sandbox-{image_name}"
    full_tag = f"{repo}:{tag}"

    # Create a temporary build context that includes templates
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy the templates directory to the temp dir
        if os.path.exists("templates"):
            shutil.copytree("templates", os.path.join(temp_dir, "templates"))

        # Copy the Dockerfile to the temp dir
        shutil.copy2(dockerfile, os.path.join(temp_dir, "Dockerfile"))

        # Build from the temp directory
        cmd = ["docker", "build", "-t", full_tag]
        if no_cache:
            cmd.append("--no-cache")
        cmd.append(temp_dir)

        print(f"Building {full_tag}...")
        result = subprocess.run(cmd, check=False)

    if result.returncode == 0:
        print(f"Successfully built {full_tag}")
        return True
    else:
        print(f"Failed to build {full_tag}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Build K2 Sandbox Docker images")
    parser.add_argument(
        "--images",
        nargs="+",
        choices=list(IMAGES.keys()) + ["all"],
        default=["all"],
        help="Images to build",
    )
    parser.add_argument("--tag", default="latest", help="Tag for the images")
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

    # Determine which images to build
    images_to_build = list(IMAGES.keys()) if "all" in args.images else args.images

    success = True
    for image in images_to_build:
        if not build_image(image, IMAGES[image], args.tag, args.no_cache):
            success = False

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
