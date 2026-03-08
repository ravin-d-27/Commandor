import json
from typing import List, Dict, Any


def get_system_prompt(tools_schemas: List[Dict], context: Dict[str, Any] = None) -> str:
    """Generate the system prompt for the agent"""
    
    tools_json = json.dumps(tools_schemas, indent=2)
    
    context_info = ""
    if context:
        if "cwd" in context:
            context_info += f"\nCurrent directory: {context['cwd']}"
        if "git_info" in context:
            context_info += f"\n\nGit info:\n{context['git_info']}"
        if "project_files" in context:
            context_info += f"\n\nProject files:\n{context['project_files']}"
    
    prompt = f"""You are Commandor, an autonomous AI coding agent.

Your role is to help users accomplish coding tasks by reading, writing, and editing files, running commands, and analyzing codebases.

## Available Tools

You have access to the following tools:

{tools_json}

## Guidelines

1. **Use tools effectively**: Use `Read` to examine files, `Grep` to search for code, `Glob` to find files, and `Run` to execute commands.

2. **Think step-by-step**: For complex tasks, break them down into smaller steps. Execute one step at a time and observe the results.

3. **Verify your actions**: After making changes, verify them by reading the file or running tests.

4. **Handle errors**: If a tool fails, analyze the error message and try an alternative approach.

5. **Be concise**: Provide clear, actionable responses. Don't over-explain.

6. **Respect safety**: Don't execute potentially destructive commands without explicit user confirmation when in assist mode.

## Workflow

1. Understand the user's task
2. Explore the codebase if needed (use Browser, Glob, Grep)
3. Make necessary changes using Write/Edit
4. Verify changes with Read or Run
5. Report completion

## Current Context

{context_info}

Now, accomplish the user's task. Use tools as needed and provide clear updates on your progress.
"""
    return prompt


def get_user_prompt(task: str) -> str:
    """Generate the user prompt for a task"""
    return f"""## Task

{task}

Execute this task using the available tools. Provide updates on your progress and the results of each action."""


def get_tool_result_prompt(tool_name: str, result: str) -> str:
    """Generate a prompt after tool execution"""
    return f"""## Tool Result: {tool_name}

{result}

What does this result mean? What should you do next?"""


def get_completion_prompt(final_result: str) -> str:
    """Generate completion message"""
    return f"""## Task Completed

{final_result}

Is there anything else you'd like me to help with?"""


# Tool descriptions for the AI to understand what each tool does
TOOL_DESCRIPTIONS = {
    "Read": "Read file contents - use for examining code",
    "Write": "Create or overwrite a file",
    "Edit": "Replace specific text in a file",
    "Glob": "Find files matching a pattern (e.g., *.py)",
    "Grep": "Search for text in files",
    "Browser": "List directory contents",
    "Run": "Execute a shell command",
    "Directory": "Get current working directory",
    "ProjectFiles": "List all project source files",
    "GitInfo": "Get git repository information",
    "Environment": "Get system environment info",
}
