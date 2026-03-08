from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass

from ..utils import file_ops, shell


@dataclass
class Tool:
    """Represents a tool the agent can use"""
    name: str
    description: str
    function: Callable
    parameters: Dict[str, Any]
    is_dangerous: bool = False


class ToolRegistry:
    """Registry of available tools for the agent"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register all default tools"""
        
        # File operations
        self.register(Tool(
            name="Read",
            description="Read the contents of a file. Use this to examine code files.",
            function=file_ops.read_file,
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to read"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Optional: Maximum number of lines to read",
                        "default": None
                    }
                },
                "required": ["path"]
            }
        ))
        
        self.register(Tool(
            name="Write",
            description="Create a new file or overwrite an existing file with new content.",
            function=file_ops.write_file,
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string", 
                        "description": "The path where to create/write the file"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file"
                    },
                    "create_dirs": {
                        "type": "boolean",
                        "description": "Whether to create parent directories if they don't exist",
                        "default": True
                    }
                },
                "required": ["path", "content"]
            },
            is_dangerous=False
        ))
        
        self.register(Tool(
            name="Edit",
            description="Edit an existing file by replacing specific text with new text. Use this to modify code.",
            function=file_ops.edit_file,
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path to the file to edit"
                    },
                    "old": {
                        "type": "string",
                        "description": "The exact text to find and replace"
                    },
                    "new": {
                        "type": "string", 
                        "description": "The text to replace it with"
                    }
                },
                "required": ["path", "old", "new"]
            }
        ))
        
        self.register(Tool(
            name="Glob",
            description="Find files matching a glob pattern. Good for finding all files of a certain type.",
            function=file_ops.glob_files,
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The glob pattern (e.g., '*.py', 'src/**/*.ts')"
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory to search in (defaults to current directory)",
                        "default": "."
                    }
                },
                "required": ["pattern"]
            }
        ))
        
        self.register(Tool(
            name="Grep",
            description="Search for text content within files. Use this to find specific code or text.",
            function=file_ops.search_in_files,
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The text pattern or regex to search for"
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory to search in",
                        "default": "."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "File pattern to match (e.g., '*.py')",
                        "default": "*"
                    }
                },
                "required": ["pattern"]
            }
        ))
        
        self.register(Tool(
            name="Browser",
            description="List files and directories in a folder. Use this to explore the project structure.",
            function=file_ops.list_directory,
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list",
                        "default": "."
                    }
                }
            }
        ))
        
        self.register(Tool(
            name="Run",
            description="Execute a shell command and get its output. Use this to run tests, build code, or run programs.",
            function=shell.run_command,
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 60)",
                        "default": 60
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory for the command",
                        "default": None
                    }
                },
                "required": ["command"]
            },
            is_dangerous=True
        ))
        
        self.register(Tool(
            name="Directory",
            description="Get the current working directory.",
            function=shell.get_working_directory,
            parameters={
                "type": "object",
                "properties": {}
            }
        ))
        
        self.register(Tool(
            name="ProjectFiles",
            description="Get a list of all project source files.",
            function=shell.get_project_files,
            parameters={
                "type": "object",
                "properties": {
                    "extensions": {
                        "type": "array",
                        "description": "List of file extensions to include",
                        "items": {"type": "string"},
                        "default": [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp"]
                    }
                }
            }
        ))
        
        self.register(Tool(
            name="GitInfo",
            description="Get git repository information (branch, status, recent commits).",
            function=shell.get_git_info,
            parameters={
                "type": "object",
                "properties": {}
            }
        ))
        
        self.register(Tool(
            name="Environment",
            description="Get system environment information.",
            function=shell.get_environment_info,
            parameters={
                "type": "object",
                "properties": {}
            }
        ))
    
    def register(self, tool: Tool):
        """Register a new tool"""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def execute(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name"""
        tool = self.get_tool(tool_name)
        if not tool:
            return f"Error: Unknown tool '{tool_name}'"
        
        try:
            result = tool.function(**kwargs)
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    def get_schemas(self) -> List[Dict]:
        """Get tool schemas for AI function calling"""
        schemas = []
        for tool in self.tools.values():
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            })
        return schemas
    
    def get_tools_list(self) -> List[str]:
        """Get list of tool names"""
        return list(self.tools.keys())
    
    def is_dangerous(self, tool_name: str) -> bool:
        """Check if a tool is marked as dangerous"""
        tool = self.get_tool(tool_name)
        return tool.is_dangerous if tool else False


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
