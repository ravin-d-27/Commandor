# 🚀 Commandor

An intelligent terminal assistant that uses AI to **convert natural language into shell commands** and now **answers questions directly** with `/ask`.  
Bring the power of AI to your terminal and work smarter!

[![GitHub stars](https://img.shields.io/github/stars/ravin-d-27/Commandor?style=social)](https://github.com/ravin-d-27/Commandor/stargazers)
[![License](https://img.shields.io/badge/License-Open%20Source%20with%20Attribution-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://python.org)

---

## ✨ What’s New in v1.0.2

- ✅ **Improved Help Command:** Better organized, clearer instructions
- 🐛 **Bug Fixes:** Minor fixes in `/ask` command parsing & response formatting
- 🔧 **Code Cleanup:** Refactored terminal loop for clarity
- 📚 **Documentation:** Updated README & help text to reflect new usage

---

## 🌟 Key Features

- 🧠 **/ai** – Convert natural language instructions to shell commands
- 💡 **/ask** – Ask AI anything: get explanations, coding help, system tips & more
- 🌈 **Beautiful interface** – Colorful ASCII art, emoji cues, color-coded prompts
- 📍 **Context-aware** – Commands tailored to your current directory
- 🛡️ **Safety checks** – Warn before running dangerous commands
- 📚 **Command history** – Navigate with arrow keys (readline support)
- 🖥️ **Cross-platform** – Works on Linux, macOS & Windows

---

## 📦 Installation

### 🔧 Clone & install (recommended)

```bash
git clone https://github.com/ravin-d-27/Commandor.git
cd Commandor
pip install -e .
````

### 🔑 Set up your API key

Get your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey):

```bash
echo "GEMINI=your_api_key_here" > ~/.env
```

Or set it directly:

```bash
export GEMINI=your_api_key_here
```

> ✅ **Windows tip:** Use `set GEMINI=your_api_key_here` instead

---

## 🚀 Usage

Run from any terminal:

```bash
commandor
```

---

## 🛠️ Available Commands

|             Command |                                              What it does |
| ------------------: | --------------------------------------------------------: |
| `/ai <instruction>` |                 Convert natural language to shell command |
|   `/ask <question>` | Ask AI anything (coding, concepts, tips, general queries) |
|             `/help` |                                         Show help message |
|             `/info` |                                    Show basic system info |
|          `/history` |                              View past generated commands |
|            `/clear` |                                     Clear terminal screen |
|   `exit` / `Ctrl+C` |                                            Exit Commandor |

---

## 🧪 Examples

```bash
Commandor $ /ai list all .py files
🤖 AI → find . -name "*.py" -type f

Commandor $ /ask What is a virtual environment in Python?
🤔 Thinking...

🤖 AI Response:
────────────────────────────────────────────
A virtual environment isolates your Python packages ...
────────────────────────────────────────────
```

---

## 🎨 Beautiful UI

* 🌈 Rainbow-colored ASCII logo on start
* 🤖 & 💡 emojis for quick visual cues
* Clear, color-coded prompts to separate AI and user input

---

## 🛠 Troubleshooting

✅ Command not found?

* Ensure it’s installed: `pip show commandor`
* Check your PATH: `echo $PATH`

✅ API key issues?

* Verify `.env` contains: `GEMINI=your_actual_key`
* Key must be valid on [Google AI Studio](https://makersuite.google.com/app/apikey)

✅ Windows users:

```bash
pip install pyreadline3
```

---

## 🤝 Contribute

We love contributions!

* ⭐ Star the repo
* 🐛 Report bugs / request features via [issues](https://github.com/ravin-d-27/Commandor/issues)
* 📚 Improve docs
* 🔧 Submit pull requests

> Follow code style & add tests if you add features!

---

## 📜 License

Open Source, free to use personally & commercially (with attribution):

* Display **"Powered by Commandor"** if used commercially
* Link back to this repo
  See [LICENSE](LICENSE) for full details.

---

## ✏️ Author & Contact

Made with ❤️ by **Ravin D**

* 📧 Email: [ravin.d3107@outlook.com](mailto:ravin.d3107@outlook.com)
* 💬 [GitHub Discussions](https://github.com/ravin-d-27/Commandor/discussions)

---

## 🌟 Show your support

If you find Commandor helpful:

* ⭐ Star this repository!
* Share with fellow developers!

---

## 🏁 Uninstall

```bash
pip uninstall commandor
```

---

**Happy coding! 🚀**


