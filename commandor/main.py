#!/usr/bin/env python3
"""
Commandor - An intelligent terminal assistant
"""

import sys
from .terminal import AITerminal

def main():
    """Main entry point for the Commandor command."""
    try:
        terminal = AITerminal()
        terminal.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting Commandor: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()