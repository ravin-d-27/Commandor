from setuptools import setup, find_packages

setup(
    name="terminusai",
    version="1.0.0",
    description="An intelligent terminal that uses AI to convert natural language to shell commands",
    author="Ravin D",
    author_email="ravin.d3107@outlook.com",
    packages=find_packages(),
    install_requires=[
        "google-generativeai>=0.3.0",
        "python-decouple>=3.6",
        "pyreadline3>=3.4.1; platform_system=='Windows'",
    ],
    entry_points={
        "console_scripts": [
            "terminusai=terminusai.main:main",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)