# K2 Sandbox with base Environment

This project integrates the E2B Code Interpreter template as the base image for the K2 Sandbox environment, providing a base container with multiple programming languages and enhanced capabilities for code execution.

## Overview

The K2 Sandbox uses the `e2bdev/code-interpreter` image as its base and adds additional tools and packages, providing:

- Multiple kernels (Python, JavaScript, Deno, R, Java, Bash) in a single container
- Pre-installed packages and libraries for data science, web development, and more
- Jupyter server integration
- Enhanced visualization capabilities
- Consistent environment for all languages

## Building the Sandbox Image

Build the base Docker image using:

```bash
python scripts/build_images.py
```

## Using the Sandbox

```python
from k2_sandbox import Sandbox

# Create a new sandbox instance
with Sandbox() as sandbox:
    # Execute Python code
    execution = sandbox.run_code("import numpy as np; np.random.rand(5,5)")
    print(execution.text)

    # Execute JavaScript code
    js_execution = sandbox.run_code('console.log("Hello from JavaScript!");', language="javascript")
    print(js_execution.text)

    # Execute R code
    r_execution = sandbox.run_code('x <- c(1,2,3,4,5); mean(x)', language="r")
    print(r_execution.text)

    # Upload and work with files
    sandbox.filesystem.write("/home/user/data.txt", "Hello, world!")

    # Run system commands
    result = sandbox.process.start("ls -la /home/user")
    print(result.stdout)
```

## Available Languages

The base sandbox image supports multiple programming languages in a single container:

1. **Python** - With data science libraries and machine learning tools:

   - NumPy, Pandas, Matplotlib
   - scikit-learn, TensorFlow
   - PyTorch Lightning, Transformers

2. **JavaScript/TypeScript** - With Node.js and development tools:

   - TypeScript, ts-node
   - ESLint, Prettier
   - Webpack

3. **R** - For statistical computing:

   - ggplot2, dplyr, tidyr

4. **Java** - For JVM-based applications
5. **Bash** - For shell scripting
6. **Deno** - Modern JavaScript/TypeScript runtime

## Configuration

You can customize the sandbox by modifying:

- `docker/Dockerfile.base` - The unified Docker configuration

## Docker Compose

Use Docker Compose to run the sandbox:

```bash
docker-compose up -d k2sandbox
```

This will mount the `templates` directory into the container and create a workspace volume.

## Credits

This integration uses the [E2B Code Interpreter](https://e2b.dev/docs/sandbox-template) template as the base image, which provides enhanced functionality for AI-powered code execution environments.
