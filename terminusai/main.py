#!/usr/bin/env python3
"""
TerminusAI - An intelligent terminal assistant
"""

import sys
from .terminal import AITerminal

def main():
    """Main entry point for the terminusai command."""
    try:
        terminal = AITerminal()
        terminal.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting TerminusAI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()