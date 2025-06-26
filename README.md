# TerminusAI

An intelligent terminal assistant that uses AI to convert natural language to shell commands.

## Features

- AI-powered natural language to shell command conversion
- Colorized output and beautiful terminal interface
- Command history with readline support
- Safety checks for dangerous commands
- Cross-platform support (Windows, macOS, Linux)
- Context-aware suggestions based on current directory

## Installation

### Method 1: Install from Source (Recommended)

1. **Clone or download the project files**
2. **Set up the directory structure:**
   ```
   terminusai/
   ├── setup.py
   ├── requirements.txt
   ├── README.md
   └── terminusai/
       ├── __init__.py
       ├── main.py
       └── terminal.py
   ```

3. **Install the package:**
   ```bash
   cd terminusai
   pip install -e .
   ```

4. **Set up your environment:**
   Create a `.env` file in your home directory or project directory:
   ```
   GEMINI=your_gemini_api_key_here
   ```

### Method 2: Direct Installation

If you prefer to install directly:

```bash
# Install dependencies
pip install google-generativeai python-decouple pyreadline3

# Install the package
pip install -e .
```

## Setup

1. **Get a Gemini API Key:**
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Copy the key

2. **Configure the environment:**
   Create a `.env` file in your home directory:
   ```bash
   echo "GEMINI=your_api_key_here" > ~/.env
   ```

   Or set it as an environment variable:
   ```bash
   export GEMINI=your_api_key_here
   ```

## Usage

Once installed, you can start TerminusAI from anywhere in your terminal:

```bash
terminusai
```

### Commands

- `/ai <instruction>` - Convert natural language to shell command
- `/help` - Show help message
- `/info` - Show system information
- `/history` - Show command history
- `/clear` - Clear the screen
- `exit` or `Ctrl+C` - Exit TerminusAI

### Examples

```bash
terminusai
TerminusAI $ /ai list all python files
AI → find . -name "*.py" -type f

TerminusAI $ /ai create a directory called projects
AI → mkdir projects

TerminusAI $ /ai show disk usage
AI → df -h
```

## Troubleshooting

### Command not found

If you get "terminusai: command not found":

1. **Check if the package is installed:**
   ```bash
   pip show terminusai
   ```

2. **Check your PATH:**
   ```bash
   echo $PATH
   ```

3. **Find where pip installs scripts:**
   ```bash
   python -m site --user-base
   ```

4. **Add to PATH if needed (add to your `.bashrc` or `.zshrc`):**
   ```bash
   export PATH="$PATH:$(python -m site --user-base)/bin"
   ```

### API Key Issues

- Make sure your `.env` file contains: `GEMINI=your_actual_api_key`
- Verify the API key is valid at [Google AI Studio](https://makersuite.google.com/app/apikey)
- Check that the `.env` file is in your home directory or current working directory

### Windows Users

For better experience on Windows, install pyreadline3:
```bash
pip install pyreadline3
```

## Uninstallation

To uninstall TerminusAI:

```bash
pip uninstall terminusai
```

## Development

To contribute or modify:

1. Clone the repository
2. Install in development mode: `pip install -e .`
3. Make your changes
4. Test with `terminusai`

## License

MIT License