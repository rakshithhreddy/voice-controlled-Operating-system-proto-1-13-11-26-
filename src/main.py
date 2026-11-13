"""
Main Application Entry Point.
Supports both Desktop GUI mode (default) and Interactive/Automated CLI mode.
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import APP_NAME, APP_VERSION, WORKSPACE_DIR, LOG_FILE
from src.workspace.manager import WorkspaceManager
from src.nlp.context import ContextManager
from src.nlp.parser import InstructionParser
from src.planner.planner import TaskPlanner
from src.planner.executor import TaskExecutor
from src.voice.recognizer import SpeechRecognitionEngine
from src.voice.speaker import VoiceSpeaker


def run_cli_session(command: str = None):
    """Runs the assistant in command-line interface mode."""
    print(f"\n==========================================")
    print(f" {APP_NAME} v{APP_VERSION} (CLI Mode)")
    print(f" Workspace: {WORKSPACE_DIR}")
    print(f"==========================================\n")

    workspace = WorkspaceManager(WORKSPACE_DIR)
    context = ContextManager()
    parser = InstructionParser(context)
    planner = TaskPlanner()
    executor = TaskExecutor(workspace, context)

    if command:
        print(f"Executing: '{command}'")
        parsed = parser.parse(command)
        plan = planner.create_plan(command, parsed, workspace.get_relative_cwd())
        result = executor.execute_plan(plan)
        print(f"\nResult:\n{result.summary_message}\n")
        return result.overall_success

    print("Type your instruction (or 'quit'/'exit'):\n")
    while True:
        try:
            line = input("VoiceOS> ").strip()
            if not line:
                continue
            if line.lower() in ["quit", "exit", "q"]:
                print("Exiting assistant.")
                break

            parsed = parser.parse(line)
            plan = planner.create_plan(line, parsed, workspace.get_relative_cwd())
            result = executor.execute_plan(plan)
            print(f"\nAssistant: {result.summary_message}\n")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


def run_gui():
    """Launches the Tkinter desktop dashboard."""
    import tkinter as tk
    from src.ui.app import VoiceAssistantApp

    root = tk.Tk()
    app = VoiceAssistantApp(root)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} - Local Voice Assistant")
    parser.add_argument("--cli", action="store_true", help="Run in terminal CLI mode instead of GUI")
    parser.add_argument("--command", type=str, help="Execute a single command string and exit")

    args = parser.parse_args()

    if args.command:
        success = run_cli_session(args.command)
        sys.exit(0 if success else 1)
    elif args.cli:
        run_cli_session()
    else:
        run_gui()


if __name__ == "__main__":
    main()
