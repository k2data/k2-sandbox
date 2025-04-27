from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="k2-sandbox",
    version="0.1.0",
    author="K2 Team",
    author_email="info@k2sandbox.com",
    description="Python SDK for running code in isolated Docker containers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/k2-sandbox",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "docker>=5.0.0",
    ],
)
