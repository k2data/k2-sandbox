# PowerShell script to build Docker image from templates/Dockerfile

# Default values
$ImageName = "k2data/sandbox-code-interpreter"
$Tag = "latest"
$BuildArgs = @()
$NoCache = $false

# Parse command line arguments
for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        "--name" {
            $ImageName = $args[++$i]
        }
        "--tag" {
            $Tag = $args[++$i]
        }
        "--build-arg" {
            $BuildArgs += "--build-arg"
            $BuildArgs += $args[++$i]
        }
        "--no-cache" {
            $NoCache = $true
        }
        "--help" {
            Write-Host "Usage: .\build_template_image.ps1 [OPTIONS]"
            Write-Host "Build Docker image from templates/Dockerfile"
            Write-Host ""
            Write-Host "Options:"
            Write-Host "  --name NAME       Set the image name (default: k2data/sandbox-code-interpreter)"
            Write-Host "  --tag TAG         Set the image tag (default: latest)"
            Write-Host "  --build-arg ARG   Add a build argument (can be used multiple times)"
            Write-Host "  --no-cache        Build without using Docker cache"
            Write-Host "  --help            Display this help message"
            exit 0
        }
        default {
            Write-Host "Unknown option: $($args[$i])"
            Write-Host "Use --help for usage information"
            exit 1
        }
    }
}

# Full image name with tag
$FullImageName = "${ImageName}:${Tag}"

# Build command
$BuildCmd = @("docker", "build")

# Add no-cache option if specified
if ($NoCache) {
    $BuildCmd += "--no-cache"
}

# Add build args if any
if ($BuildArgs.Count -gt 0) {
    $BuildCmd += $BuildArgs
}

# Add image name and build context
$BuildCmd += "-t", $FullImageName, "-f", "templates/Dockerfile", "templates"

# Display the command
Write-Host "Building image with command:"
Write-Host ($BuildCmd -join " ")
Write-Host ""

# Execute the build command
$process = Start-Process -FilePath $BuildCmd[0] -ArgumentList $BuildCmd[1..($BuildCmd.Length - 1)] -NoNewWindow -PassThru -Wait

# Check if build was successful
if ($process.ExitCode -eq 0) {
    Write-Host ""
    Write-Host "Successfully built image: $FullImageName"
    Write-Host ""
    Write-Host "You can run the image with:"
    Write-Host "docker run -it $FullImageName"
}
else {
    Write-Host ""
    Write-Host "Failed to build image: $FullImageName"
    exit 1
} 