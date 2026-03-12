#!/usr/bin/env python3
"""
Commandor - Agentic CLI
Entry point for commandor command
"""

import sys
import argparse
from . import config
from .agent import run_agent


def main():
    """Main entry point for Commandor"""
    parser = argparse.ArgumentParser(
        description="Commandor - Agentic CLI for autonomous coding",
        prog="commandor"
    )

    parser.add_argument(
        "task",
        nargs="*",
        help="Task to accomplish (for non-interactive mode)"
    )
    parser.add_argument(
        "-a", "--agent",
        action="store_true",
        help="Run in autonomous agent mode"
    )
    parser.add_argument(
        "--assist",
        action="store_true",
        help="Run in assist mode (with confirmations)"
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Run in chat mode (Q&A only)"
    )
    parser.add_argument(
        "-n", "--plan",
        action="store_true",
        help="Run in plan mode (review plan before execution)"
    )
    parser.add_argument(
        "-p", "--provider",
        help="AI provider to use (gemini, anthropic, openai, openrouter)"
    )
    parser.add_argument(
        "-m", "--model",
        help="Model to use"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive setup"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version"
    )

    args = parser.parse_args()

    if args.version:
        print("Commandor v0.2.0")
        print("Agentic CLI - Autonomous coding assistant")
        return 0

    if args.setup:
        config.setup_interactive()
        return 0

    # If we have a task and a mode flag, run non-interactively
    if args.task and (args.agent or args.assist or args.chat or args.plan):
        task = " ".join(args.task)

        if args.agent:
            mode = "agent"
        elif args.assist:
            mode = "assist"
        elif args.plan:
            mode = "plan"
        else:
            mode = "chat"

        try:
            result = run_agent(
                task,
                mode=mode,
                provider=args.provider,
                model=args.model
            )

            if result.success:
                print("\n" + "=" * 40)
                print("Result:")
                print("=" * 40)
                print(result.final_answer)
            else:
                print(f"Error: {result.final_answer}", file=sys.stderr)
                return 1

            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Interactive Textual split-pane UI
    try:
        from .textual_app import CommandorApp  # noqa: PLC0415

        # Determine initial mode for chat panel
        if args.agent:
            initial_mode = "agent"
        elif args.chat:
            initial_mode = "chat"
        elif args.plan:
            initial_mode = "plan"
        elif args.assist:
            initial_mode = "assist"
        else:
            initial_mode = "agent"

        app = CommandorApp(
            initial_mode=initial_mode,
            provider=args.provider,
            model=args.model,
        )
        app.run()
        return 0
    except KeyboardInterrupt:
        print("\nGoodbye!")
        return 0
    except Exception as e:
        print(f"Error starting Commandor: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
