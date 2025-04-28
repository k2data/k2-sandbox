#!/bin/bash

# Script to build Docker image from templates/Dockerfile

# Default values
IMAGE_NAME="k2-sandbox/code-interpreter"
TAG="latest"
BUILD_ARGS=""
NO_CACHE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
  --name)
    IMAGE_NAME="$2"
    shift 2
    ;;
  --tag)
    TAG="$2"
    shift 2
    ;;
  --build-arg)
    BUILD_ARGS="$BUILD_ARGS --build-arg $2"
    shift 2
    ;;
  --no-cache)
    NO_CACHE=true
    shift
    ;;
  --help)
    echo "Usage: $0 [OPTIONS]"
    echo "Build Docker image from templates/Dockerfile"
    echo ""
    echo "Options:"
    echo "  --name NAME       Set the image name (default: k2-sandbox/code-interpreter)"
    echo "  --tag TAG         Set the image tag (default: latest)"
    echo "  --build-arg ARG   Add a build argument (can be used multiple times)"
    echo "  --no-cache        Build without using Docker cache"
    echo "  --help            Display this help message"
    exit 0
    ;;
  *)
    echo "Unknown option: $1"
    echo "Use --help for usage information"
    exit 1
    ;;
  esac
done

# Full image name with tag
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

# Build command
BUILD_CMD="docker build"

# Add no-cache option if specified
if [ "$NO_CACHE" = true ]; then
  BUILD_CMD="$BUILD_CMD --no-cache"
fi

# Add build args if any
if [ -n "$BUILD_ARGS" ]; then
  BUILD_CMD="$BUILD_CMD $BUILD_ARGS"
fi

# Add image name and build context
BUILD_CMD="$BUILD_CMD -t $FULL_IMAGE_NAME -f templates/Dockerfile templates"

# Display the command
echo "Building image with command:"
echo "$BUILD_CMD"
echo ""

# Execute the build command
eval $BUILD_CMD

# Check if build was successful
if [ $? -eq 0 ]; then
  echo ""
  echo "Successfully built image: $FULL_IMAGE_NAME"
  echo ""
  echo "You can run the image with:"
  echo "docker run -it $FULL_IMAGE_NAME"
else
  echo ""
  echo "Failed to build image: $FULL_IMAGE_NAME"
  exit 1
fi
