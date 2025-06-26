from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="terminusai",
    version="1.0.0",
    description="An intelligent terminal assistant that uses AI to convert natural language to shell commands",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ravin D",
    author_email="ravin.d3107@outlook.com",
    url="https://github.com/ravin-d-27/TerminusAI",
    project_urls={
        "Bug Reports": "https://github.com/ravin-d-27/TerminusAI/issues",
        "Source": "https://github.com/ravin-d-27/TerminusAI",
        "Documentation": "https://github.com/ravin-d-27/TerminusAI#readme",
    },
    packages=find_packages(),
    install_requires=[
        "google-generativeai>=0.3.0",
        "python-decouple>=3.6",
        "pyreadline3>=3.4.1; platform_system=='Windows'",
        "colorama>=0.4.4",  # For cross-platform colored output
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
        "Intended Audience :: System Administrators",
        "License :: Free for non-commercial use",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Shells",
        "Topic :: System :: System Shells",
        "Topic :: Terminals",
        "Topic :: Utilities",
    ],
    keywords=[
        "terminal",
        "ai",
        "shell",
        "command-line",
        "natural-language",
        "gemini",
        "assistant",
        "automation",
        "cli",
        "productivity",
    ],
    include_package_data=True,
    zip_safe=False,
)