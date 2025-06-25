import os
import subprocess
import google.generativeai as genai
from decouple import config

# Set your API Key (or use os.environ)
GEMINI_API_KEY = config("GEMINI")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

current_dir = os.getcwd()

def get_shell_command_from_ai(instruction, cwd):
    prompt = f"""You are an AI assistant that helps convert natural language to shell commands.
Current directory is: {cwd}
Instruction: "{instruction}"
Reply with ONLY the shell command to execute, no explanations."""
    
    response = model.generate_content(prompt)
    return response.text.strip()

def run_shell_command(command, cwd):
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("\033[91m" + result.stderr + "\033[0m")
    except Exception as e:
        print(f"Error running command: {e}")

def main():
    global current_dir
    print(f"📟 AI Terminal Ready. Type `/ai your instruction` to use AI. Ctrl+C to exit.")
    while True:
        try:
            inp = input(f"{os.path.basename(current_dir)} $ ")
            if inp.startswith("/ai "):
                nl_instruction = inp[4:].strip()
                shell_cmd = get_shell_command_from_ai(nl_instruction, current_dir)
                print(f"🧠 AI → {shell_cmd}")
                if shell_cmd.startswith("cd "):
                    path = shell_cmd[3:].strip()
                    try:
                        new_dir = os.path.abspath(os.path.join(current_dir, path))
                        os.chdir(new_dir)
                        current_dir = new_dir
                    except FileNotFoundError:
                        print(f"❌ Directory not found: {path}")
                else:
                    run_shell_command(shell_cmd, current_dir)
            else:
                # Run normal shell commands
                if inp.startswith("cd "):
                    path = inp[3:].strip()
                    try:
                        new_dir = os.path.abspath(os.path.join(current_dir, path))
                        os.chdir(new_dir)
                        current_dir = new_dir
                    except FileNotFoundError:
                        print(f"❌ Directory not found: {path}")
                else:
                    run_shell_command(inp, current_dir)
        except KeyboardInterrupt:
            print("\n👋 Exiting AI Terminal.")
            break

if __name__ == "__main__":
    main()
