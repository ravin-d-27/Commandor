# TerminusAI

An intelligent terminal assistant that uses AI to convert natural language to shell commands.

[![GitHub stars](https://img.shields.io/github/stars/[your-username]/terminusai?style=social)](https://github.com/ravin-d-27/TerminusAI/stargazers)
[![License](https://img.shields.io/badge/License-Open%20Source%20with%20Attribution-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://python.org)

## Features

- **AI-powered natural language to shell command conversion**
- **Colorized output and beautiful terminal interface**
- **Command history with readline support**
- **Safety checks for dangerous commands**
- **Cross-platform support** (Windows, macOS, Linux)
- **Context-aware suggestions** based on current directory

## Installation

### Install from Source (Recommended)

1. **Clone or download the project files**
   ```bash
   git clone https://github.com/ravin-d-27/TerminusAI.git
   cd terminusai
   ```

2. **Verify the directory structure:**
   ```
   terminusai/
   ├── setup.py
   ├── requirements.txt
   ├── README.md
   ├── LICENSE
   ├── .gitignore
   └── terminusai/
       ├── __init__.py
       ├── main.py
       └── terminal.py
   ```

3. **Install the package:**
   ```bash
   pip install -e .
   ```

4. **Set up your environment:**
   Create a `.env` file in your home directory or project directory:
   ```bash
   echo "GEMINI=your_gemini_api_key_here" > ~/.env
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

### Available Commands

| Command | Description |
|---------|-------------|
| `/ai <instruction>` | Convert natural language to shell command |
| `/help` | Show help message |
| `/info` | Show system information |
| `/history` | Show command history |
| `/clear` | Clear the screen |
| `exit` or `Ctrl+C` | Exit TerminusAI |

### Examples

```bash
terminusai
TerminusAI $ /ai list all python files
AI → find . -name "*.py" -type f

TerminusAI $ /ai create a directory called projects
AI → mkdir projects

TerminusAI $ /ai show disk usage
AI → df -h

TerminusAI $ /ai find large files over 100MB
AI → find . -type f -size +100M -exec ls -lh {} \;
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

## Contributing

We welcome contributions from everyone! Here's how you can help:

### Ways to Contribute
- **Report bugs** by opening an issue
- **Suggest features** or improvements
- **Improve documentation**
- **Submit pull requests** with bug fixes or new features
- **Star the repository** to help others discover it

### Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/ravin-d-27/TerminusAI.git
   cd terminusai
   ```

2. **Install in development mode:**
   ```bash
   pip install -e .
   ```

3. **Make your changes and test:**
   ```bash
   terminusai
   ```

4. **Submit a pull request**

### Contribution Guidelines
- Follow existing code style
- Add tests for new features
- Update documentation as needed
- Be respectful and inclusive in discussions

## License

TerminusAI is **free and open source** for everyone! 🎉

- ✅ **Personal use**: No attribution required
- ✅ **Commercial use**: Free with attribution requirement
- ✅ **Contributions**: Always welcome!
- ✅ **Modifications**: Allowed with proper attribution

### Commercial Attribution Requirement

If you're using TerminusAI commercially, we just ask that you:
- Display **"Powered by TerminusAI"** in your product
- Include a link to this repository
- Consider sharing your use case with the community

See [LICENSE](LICENSE) for complete details.

## Showcase

**Using TerminusAI in your project?** We'd love to feature you! Submit your use case by opening an issue or contacting us.

### Featured Users
*Be the first to be featured here by using TerminusAI commercially and letting us know!*

## Uninstallation

To uninstall TerminusAI:

```bash
pip uninstall terminusai
```

## Support & Contact

- 🐛 **Issues**: [GitHub Issues](https://github.com/ravin-d-27/TerminusAI/issues)
- 📧 **Email**: [ravin.d3107@outlook.com]
- 💬 **Discussions**: [GitHub Discussions](https://github.com/ravin-d-27/TerminusAI/discussions)

## Acknowledgments

- Thanks to all contributors who help make TerminusAI better
- Built with Google's Gemini AI
- Inspired by the need for more intuitive terminal interactions

---

**If TerminusAI helps you, please star this repository to help others discover it!**

**Made with ❤️ by Ravin D**