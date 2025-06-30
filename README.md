# Commandor

An intelligent terminal assistant that uses AI to convert natural language to shell commands and answer questions directly.

[![GitHub stars](https://img.shields.io/github/stars/ravin-d-27/Commandor?style=social)](https://github.com/ravin-d-27/Commandor/stargazers)
[![License](https://img.shields.io/badge/License-Open%20Source%20with%20Attribution-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://python.org)

## ✨ Latest Features (v2.0)

### 🤖 **Direct AI Chat with `/ask`**
Ask the AI assistant any question directly without generating commands! Perfect for:
- Getting programming help and explanations
- Learning new concepts and best practices
- Technical troubleshooting and advice
- General knowledge queries

### 🎨 **Beautiful Colorful Interface**
- **Stunning ASCII art logo** with rainbow colors
- **Enhanced visual experience** with emojis and improved styling
- **Better color coding** for different command types
- **Professional yet fun** terminal presentation

## Core Features

- **🧠 AI-powered natural language to shell command conversion**
- **💬 Direct AI questioning and assistance**
- **🌈 Colorized output and beautiful terminal interface**
- **📚 Command history with readline support**
- **🛡️ Safety checks for dangerous commands**
- **🖥️ Cross-platform support** (Windows, macOS, Linux)
- **📍 Context-aware suggestions** based on current directory

## Installation

### Install from Source (Recommended)

1. **Clone or download the project files**
   ```bash
   git clone https://github.com/ravin-d-27/Commandor.git
   cd commandor
   ```

2. **Verify the directory structure:**
   ```
   Commandor/
   ├── setup.py
   ├── requirements.txt
   ├── README.md
   ├── LICENSE
   ├── .gitignore
   └── commandor/
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

Once installed, you can start Commandor from anywhere in your terminal:

```bash
commandor
```

### Available Commands

| Command | Description | New! |
|---------|-------------|------|
| `/ai <instruction>` | Convert natural language to shell command | |
| `/ask <question>` | Ask AI any question directly | ✨ **NEW** |
| `/help` | Show help message | |
| `/info` | Show system information | |
| `/history` | Show command history | |
| `/clear` | Clear the screen | |
| `exit` or `Ctrl+C` | Exit Commandor | |

### Command Generation Examples

```bash
commandor
🚀 COMMANDOR - Your AI-Powered Terminal Assistant 🚀

Commandor $ /ai list all python files
🤖 AI → find . -name "*.py" -type f

Commandor $ /ai create a directory called projects
🤖 AI → mkdir projects

Commandor $ /ai show disk usage
🤖 AI → df -h

Commandor $ /ai find large files over 100MB
🤖 AI → find . -type f -size +100M -exec ls -lh {} \;
```

### ✨ NEW: Direct AI Questions

Ask the AI assistant anything directly without generating commands:

```bash
Commandor $ /ask What is the difference between Python and JavaScript?
🤔 Thinking...

🤖 AI Response:
──────────────────────────────────────────────────
Python and JavaScript are both popular programming languages but serve different purposes:

**Python:**
- General-purpose language, great for data science, AI, web backends
- Interpreted, readable syntax
- Strong in scientific computing and automation
- Used for desktop applications, web servers, data analysis

**JavaScript:**
- Originally for web browsers, now also server-side (Node.js)
- Essential for web development and interactive websites
- Event-driven and asynchronous
- Used for frontend, backend, and mobile apps

Both are beginner-friendly but excel in different domains!
──────────────────────────────────────────────────

Commandor $ /ask How do I optimize my Python code for better performance?
🤔 Thinking...

🤖 AI Response:
──────────────────────────────────────────────────
Here are key strategies for Python optimization:

1. **Use built-in functions** - They're implemented in C and much faster
2. **List comprehensions** - Faster than traditional loops
3. **Avoid global variables** - Local variables are accessed faster
4. **Use appropriate data structures** - Sets for membership testing, deques for queues
5. **Profile your code** - Use cProfile to find bottlenecks
6. **NumPy for numerical operations** - Vectorized operations are much faster
7. **Cache expensive function calls** - Use @lru_cache decorator
8. **Use generators** - For memory-efficient iteration

Focus on the biggest bottlenecks first for maximum impact!
──────────────────────────────────────────────────
```

### More `/ask` Examples

```bash
# Programming Help
/ask Explain machine learning concepts for beginners
/ask What are Git best practices?
/ask How do I debug memory leaks in Python?

# System Administration
/ask What are the differences between various Linux distributions?
/ask How do I secure my server?
/ask Explain Docker vs Virtual Machines

# General Learning
/ask What is quantum computing?
/ask How does blockchain technology work?
/ask Explain REST APIs
```

## Troubleshooting

### Command not found

If you get "commandor: command not found":

1. **Check if the package is installed:**
   ```bash
   pip show commandor
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

## What's New in v2.0

### 🆕 Direct AI Assistant (`/ask`)
- **Ask any question** directly to the AI without generating commands
- **Perfect for learning** - get explanations, tutorials, and advice
- **Context-aware responses** - AI understands your system environment
- **Clean formatting** - Beautiful response display with visual separators

### 🎨 Enhanced Visual Experience
- **Colorful ASCII art logo** - Eye-catching Commandor branding on startup
- **Rainbow color palette** - More vibrant and engaging interface
- **Emoji indicators** - Visual cues for different actions (🤖, 🧠, 💡, etc.)
- **Improved help system** - Better organized with examples for both features

### 🚀 Better User Experience
- **Clearer command distinction** - Visual separation between `/ai` and `/ask`
- **Enhanced prompts** - More informative and colorful terminal prompts
- **Improved error messages** - Better feedback with emoji indicators
- **Professional presentation** - Polished interface that's both functional and beautiful

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
   git clone https://github.com/ravin-d-27/Commandor.git
   cd commandor
   ```

2. **Install in development mode:**
   ```bash
   pip install -e .
   ```

3. **Make your changes and test:**
   ```bash
   commandor
   ```

4. **Submit a pull request**

### Contribution Guidelines
- Follow existing code style
- Add tests for new features
- Update documentation as needed
- Be respectful and inclusive in discussions

## License

Commandor is **free and open source** for everyone! 🎉

- ✅ **Personal use**: No attribution required
- ✅ **Commercial use**: Free with attribution requirement
- ✅ **Contributions**: Always welcome!
- ✅ **Modifications**: Allowed with proper attribution

### Commercial Attribution Requirement

If you're using Commandor commercially, we just ask that you:
- Display **"Powered by Commandor"** in your product
- Include a link to this repository
- Consider sharing your use case with the community

See [LICENSE](LICENSE) for complete details.

## Showcase

**Using Commandor in your project?** We'd love to feature you! Submit your use case by opening an issue or contacting us.

### Featured Users
*Be the first to be featured here by using Commandor commercially and letting us know!*

## Uninstallation

To uninstall Commandor:

```bash
pip uninstall commandor
```

## Support & Contact

- 🐛 **Issues**: [GitHub Issues](https://github.com/ravin-d-27/Commandor/issues)
- 📧 **Email**: [ravin.d3107@outlook.com]
- 💬 **Discussions**: [GitHub Discussions](https://github.com/ravin-d-27/Commandor/discussions)

## Acknowledgments

- Thanks to all contributors who help make Commandor better
- Built with Google's Gemini AI
- Inspired by the need for more intuitive terminal interactions

---

**If Commandor helps you, please star this repository to help others discover it!**

**Made with ❤️ by Ravin D**