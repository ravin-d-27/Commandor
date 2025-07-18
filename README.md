# Commandor

Commandor is an intelligent terminal assistant that uses AI to convert natural language into shell commands and now answers questions directly with `/ask`.  
It brings the power of generative AI to your terminal to improve productivity, reduce mental load, and streamline development workflows.

[![GitHub stars](https://img.shields.io/github/stars/ravin-d-27/Commandor?style=social)](https://github.com/ravin-d-27/Commandor/stargazers)
[![License](https://img.shields.io/badge/License-Open%20Source%20with%20Attribution-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://python.org)

**Docker Image:**  
Available at [https://hub.docker.com/r/ravind2704/commandor](https://hub.docker.com/r/ravind2704/commandor)

---

## Key Features

- `/ai` – Convert natural language instructions into shell commands
- `/ask` – Ask AI questions about programming, systems, tools, and general knowledge
- Color-coded terminal interface with clear separation of user and AI input
- Context-aware suggestions based on current working directory
- Safety checks before executing potentially destructive commands
- Command history navigation with arrow keys
- Cross-platform support: Linux, macOS, and Windows

---

## Installation

### Clone and install (recommended)

```bash
git clone https://github.com/ravin-d-27/Commandor.git
cd Commandor
pip install -e .
````

### Set up your API key

Obtain your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

---

## Docker Usage

Commandor is also available as a Docker image:

### Pull the image

```bash
docker pull ravind2704/commandor
```

### Run the Docker Image

```bash
docker run -it ravind2704/commandor
```

---

## Usage

Run Commandor from your terminal:

```bash
commandor
```

---

## Available Commands

| Command             | Description                                                  |
| ------------------- | ------------------------------------------------------------ |
| `/ai <instruction>` | Converts a natural language instruction into a shell command |
| `/ask <question>`   | Asks AI a general or technical question                      |
| `/help`             | Shows usage information and supported commands               |
| `/info`             | Displays basic system information                            |
| `/history`          | Shows the history of AI-generated commands                   |
| `/clear`            | Clears the terminal screen                                   |
| `exit` or `Ctrl+C`  | Exits Commandor                                              |

---

## Examples

```bash
/ai list all .py files
# Output: find . -name "*.py" -type f

/ask What is a virtual environment in Python?
# Output: Detailed explanation generated by AI
```

---

## Troubleshooting

**Command not found**

* Confirm installation with `pip show commandor`
* Check your `$PATH` or activate your virtual environment

**API Key errors**

* Ensure your `.env` contains a valid key: `GEMINI=your_key_here`
* Verify your key at [Google AI Studio](https://makersuite.google.com/app/apikey)
* You can also test the API by /test-api command in commandor

**Windows users**

```bash
pip install pyreadline3
```

---

## Contribute

We welcome contributions from developers, testers, and writers.

* Star the repository
* Report bugs and request features via GitHub Issues
* Submit pull requests with meaningful improvements
* Follow code conventions and include test cases for new features

---

## License

Commandor is open-source and free to use with attribution.

* You must include the line: "Powered by Commandor" in commercial tools
* You must provide a visible link back to the GitHub repository

See [LICENSE](LICENSE) for full terms.

---

## Author & Contact

Created by **Ravin D**

* GitHub: [https://github.com/ravin-d-27](https://github.com/ravin-d-27)
* Email: [ravin.d3107@outlook.com](mailto:ravin.d3107@outlook.com)

---

## Show Your Support

If you find Commandor useful:

* Star the GitHub repository
* Share it with others in your developer community

---

## Uninstall

```bash
pip uninstall commandor
```

---

**Version:** 0.0.1
**Status:** Actively maintained

