"""
Desktop User Interface Application.
Provides a modern dark dashboard for voice control, live transcription,
execution planning, verification tracking, history, and system logs.
"""

import sys
import os
import time
import queue
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from src.config import APP_NAME, APP_VERSION, WORKSPACE_DIR, LOG_FILE
from src.workspace.manager import WorkspaceManager
from src.nlp.context import ContextManager
from src.nlp.parser import InstructionParser
from src.planner.planner import TaskPlanner, ExecutionPlan
from src.planner.executor import TaskExecutor, ExecutionResult
from src.planner.task import TaskItem, TaskStatus
from src.voice.recognizer import SpeechRecognitionEngine
from src.voice.speaker import VoiceSpeaker
from src.voice.hold_to_talk import HoldToTalkManager
from src.ui import theme

logger = logging.getLogger("VoiceOS.UI")


class VoiceAssistantApp:
    """
    Main Desktop UI Application for Voice-Controlled OS Assistant.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION} - Local OS Voice Assistant")
        self.root.geometry("1100x780")
        self.root.minsize(950, 650)
        self.root.configure(bg=theme.BG_DARK)

        # Thread-safe event queue
        self.msg_queue: queue.Queue = queue.Queue()

        # Initialize Backend Subsystems
        self.workspace = WorkspaceManager(WORKSPACE_DIR)
        self.context = ContextManager()
        self.parser = InstructionParser(self.context)
        self.planner = TaskPlanner()
        self.speaker = VoiceSpeaker(enabled=True)

        self.executor = TaskExecutor(
            workspace_manager=self.workspace,
            context_manager=self.context,
            status_callback=self._on_executor_status
        )

        self.recognizer = SpeechRecognitionEngine(
            on_transcription=self._on_voice_transcribed,
            on_status_change=self._on_voice_status_change
        )

        # Push-to-Talk (Hold Enter) Manager
        self.hold_to_talk = HoldToTalkManager(
            on_recording_start=lambda: self.msg_queue.put(("STATUS", "RECORDING...")),
            on_recording_tick=lambda elapsed: self.msg_queue.put(("STATUS", f"RECORDING ({elapsed:.1f}s)...")),
            on_recording_complete=self._on_hold_to_talk_complete,
            on_error=lambda err: self.msg_queue.put(("STATUS", "MIC_ERROR"))
        )

        # UI state variables
        self.status_var = tk.StringVar(value="IDLE")
        self.mic_state_var = tk.StringVar(value="Continuous Mic: OFF")
        self.tts_var = tk.BooleanVar(value=True)
        self.selected_mic_var = tk.StringVar()

        # Build UI layout
        self._setup_styles()
        self._build_header()
        self._build_control_bar()
        self._build_main_dashboard()
        self._build_footer()

        # Root keyboard shortcuts for Push-To-Talk
        self.root.bind("<KeyPress-Return>", self._on_enter_key_press)
        self.root.bind("<KeyRelease-Return>", self._on_enter_key_release)

        # Periodic queue checker
        self.root.after(100, self._process_queue)

        # Initial workspace tree population
        self.root.after(300, self._refresh_workspace_tree)

        # Set initial status
        self._update_status_badge("IDLE")
        self._log_system(f"Assistant initialized. Workspace: '{self.workspace.root}'")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Global backgrounds
        style.configure(".", background=theme.BG_DARK, foreground=theme.TEXT_PRIMARY)
        style.configure("TFrame", background=theme.BG_DARK)
        style.configure("Surface.TFrame", background=theme.BG_SURFACE)

        # Labels
        style.configure("Header.TLabel", font=theme.FONT_TITLE, foreground=theme.TEXT_BRIGHT, background=theme.BG_DARK)
        style.configure("Subtitle.TLabel", font=theme.FONT_SUBTITLE, foreground=theme.TEXT_PRIMARY, background=theme.BG_SURFACE)
        style.configure("TLabel", font=theme.FONT_BODY, background=theme.BG_DARK, foreground=theme.TEXT_PRIMARY)
        style.configure("Surface.TLabel", font=theme.FONT_BODY, background=theme.BG_SURFACE, foreground=theme.TEXT_PRIMARY)

        # Buttons
        style.configure(
            "Accent.TButton",
            font=theme.FONT_BOLD,
            background=theme.STATUS_LISTENING,
            foreground="#11111b",
            borderwidth=0,
            padding=6
        )
        style.map("Accent.TButton", background=[("active", theme.STATUS_VERIFYING)])

        style.configure(
            "Control.TButton",
            font=theme.FONT_BODY,
            background=theme.BG_SURFACE_LIGHT,
            foreground=theme.TEXT_BRIGHT,
            borderwidth=0,
            padding=6
        )
        style.map("Control.TButton", background=[("active", theme.BORDER_COLOR)])

        # Panedwindow
        style.configure("TPanedwindow", background=theme.BG_DARK)

        # Treeview (Task Plan)
        style.configure(
            "Treeview",
            background=theme.BG_SURFACE,
            foreground=theme.TEXT_PRIMARY,
            fieldbackground=theme.BG_SURFACE,
            rowheight=26,
            font=theme.FONT_BODY
        )
        style.configure("Treeview.Heading", font=theme.FONT_BOLD, background=theme.BG_SURFACE_LIGHT, foreground=theme.TEXT_BRIGHT)
        style.map("Treeview", background=[("selected", theme.BG_SURFACE_LIGHT)], foreground=[("selected", theme.TEXT_BRIGHT)])

    def _build_header(self):
        header_frame = ttk.Frame(self.root, padding="12 10 12 5")
        header_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(header_frame, text=f"🎙 {APP_NAME}", style="Header.TLabel")
        title_lbl.pack(side=tk.LEFT)

        version_lbl = ttk.Label(header_frame, text=f"v{APP_VERSION} (Offline Ready)", font=("Segoe UI", 9), foreground=theme.TEXT_SECONDARY)
        version_lbl.pack(side=tk.LEFT, padx=10, pady=4)

        # Status Pill
        self.status_pill = tk.Label(
            header_frame,
            textvariable=self.status_var,
            font=theme.FONT_STATUS,
            bg=theme.STATUS_IDLE,
            fg="#11111b",
            padx=16,
            pady=4,
            relief=tk.FLAT
        )
        self.status_pill.pack(side=tk.RIGHT)

        ttk.Label(header_frame, text="Current State:", font=theme.FONT_BODY, foreground=theme.TEXT_SECONDARY).pack(side=tk.RIGHT, padx=6)

    def _build_control_bar(self):
        ctrl_frame = ttk.Frame(self.root, style="Surface.TFrame", padding="10 8 10 8")
        ctrl_frame.pack(fill=tk.X, padx=12, pady=5)

        # Push to talk button (supports clicking or holding Enter)
        self.btn_listen = ttk.Button(ctrl_frame, text="🎤 Speak [Hold Enter]", style="Accent.TButton", command=self._on_push_to_talk)
        self.btn_listen.pack(side=tk.LEFT, padx=4)

        # Toggle continuous listening button
        self.btn_continuous = ttk.Button(ctrl_frame, textvariable=self.mic_state_var, style="Control.TButton", command=self._toggle_continuous_mic)
        self.btn_continuous.pack(side=tk.LEFT, padx=4)

        # TTS Checkbox
        tts_chk = tk.Checkbutton(
            ctrl_frame,
            text="Voice Output (TTS)",
            variable=self.tts_var,
            command=self._on_toggle_tts,
            bg=theme.BG_SURFACE,
            fg=theme.TEXT_PRIMARY,
            selectcolor=theme.BG_DARK,
            activebackground=theme.BG_SURFACE,
            activeforeground=theme.TEXT_BRIGHT,
            font=theme.FONT_BODY
        )
        tts_chk.pack(side=tk.LEFT, padx=12)

        # Text input fallback / manual command
        ttk.Label(ctrl_frame, text="Or Type:", style="Surface.TLabel").pack(side=tk.LEFT, padx=(10, 4))
        self.txt_input = ttk.Entry(ctrl_frame, font=theme.FONT_BODY, width=32)
        self.txt_input.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        self.txt_input.bind("<Return>", lambda e: self._on_execute_typed_command())

        btn_send = ttk.Button(ctrl_frame, text="Send", style="Control.TButton", command=self._on_execute_typed_command)
        btn_send.pack(side=tk.LEFT, padx=4)

    def _build_main_dashboard(self):
        # Themed PanedWindow for responsive, proportional layout
        paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=5)

        # Top section: Horizontal PanedWindow (Left: Conversation | Right: Plan)
        top_paned = ttk.PanedWindow(paned, orient=tk.HORIZONTAL)
        paned.add(top_paned, weight=3)

        # Left Column: Conversation Stream
        conv_frame = ttk.Frame(top_paned, style="Surface.TFrame", padding=10)
        top_paned.add(conv_frame, weight=3)

        ttk.Label(conv_frame, text="🗣 Live Spoken Input & Assistant Response", style="Subtitle.TLabel").pack(anchor=tk.W, pady=(0, 6))

        self.txt_conversation = scrolledtext.ScrolledText(
            conv_frame,
            wrap=tk.WORD,
            bg=theme.BG_DARK,
            fg=theme.TEXT_PRIMARY,
            insertbackground=theme.TEXT_BRIGHT,
            font=theme.FONT_BODY,
            bd=0,
            highlightthickness=1,
            highlightbackground=theme.BORDER_COLOR
        )
        self.txt_conversation.pack(fill=tk.BOTH, expand=True)
        self.txt_conversation.tag_config("user", foreground=theme.STATUS_LISTENING, font=theme.FONT_BOLD)
        self.txt_conversation.tag_config("assistant", foreground=theme.STATUS_COMPLETED, font=theme.FONT_BODY)
        self.txt_conversation.tag_config("system", foreground=theme.STATUS_PROCESSING, font=theme.FONT_CODE)

        # Right Column: Execution Plan & Verification Tracker
        plan_frame = ttk.Frame(top_paned, style="Surface.TFrame", padding=10)
        top_paned.add(plan_frame, weight=4)

        ttk.Label(plan_frame, text="📋 Multi-Step Execution Plan & Verification", style="Subtitle.TLabel").pack(anchor=tk.W, pady=(0, 6))

        columns = ("step", "intent", "description", "status", "verified")
        self.tree_plan = ttk.Treeview(plan_frame, columns=columns, show="headings", selectmode="browse")
        self.tree_plan.heading("step", text="#")
        self.tree_plan.heading("intent", text="Intent")
        self.tree_plan.heading("description", text="Operation Description")
        self.tree_plan.heading("status", text="Status")
        self.tree_plan.heading("verified", text="Verified")

        self.tree_plan.column("step", width=35, anchor=tk.CENTER)
        self.tree_plan.column("intent", width=110, anchor=tk.W)
        self.tree_plan.column("description", width=230, anchor=tk.W)
        self.tree_plan.column("status", width=80, anchor=tk.CENTER)
        self.tree_plan.column("verified", width=65, anchor=tk.CENTER)

        tree_scroll = ttk.Scrollbar(plan_frame, orient=tk.VERTICAL, command=self.tree_plan.yview)
        self.tree_plan.configure(yscrollcommand=tree_scroll.set)

        self.tree_plan.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom section: Tabs for History and Application Logs
        bottom_frame = ttk.Frame(paned, style="Surface.TFrame", padding=8)
        paned.add(bottom_frame, weight=2)

        notebook = ttk.Notebook(bottom_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Execution History
        tab_history = ttk.Frame(notebook, padding=6)
        notebook.add(tab_history, text="Execution History")

        self.txt_history = scrolledtext.ScrolledText(
            tab_history,
            wrap=tk.WORD,
            bg=theme.BG_DARK,
            fg=theme.TEXT_PRIMARY,
            font=theme.FONT_CODE,
            bd=0
        )
        self.txt_history.pack(fill=tk.BOTH, expand=True)

        # Tab 2: System Logs
        tab_logs = ttk.Frame(notebook, padding=6)
        notebook.add(tab_logs, text="System & Security Logs")

        self.txt_logs = scrolledtext.ScrolledText(
            tab_logs,
            wrap=tk.WORD,
            bg=theme.BG_DARK,
            fg=theme.TEXT_SECONDARY,
            font=theme.FONT_CODE,
            bd=0
        )
        self.txt_logs.pack(fill=tk.BOTH, expand=True)

        # Tab 3: Live Workspace Data Explorer
        tab_ws = ttk.Frame(notebook, padding=6)
        notebook.add(tab_ws, text="Workspace Data Explorer")

        self.tree_workspace = ttk.Treeview(tab_ws, columns=("type", "size"), show="tree headings")
        self.tree_workspace.heading("#0", text="Folder / File Path")
        self.tree_workspace.heading("type", text="Type")
        self.tree_workspace.heading("size", text="Size")
        self.tree_workspace.column("#0", width=420)
        self.tree_workspace.column("type", width=90, anchor=tk.CENTER)
        self.tree_workspace.column("size", width=90, anchor=tk.CENTER)

        ws_scroll = ttk.Scrollbar(tab_ws, orient=tk.VERTICAL, command=self.tree_workspace.yview)
        self.tree_workspace.configure(yscrollcommand=ws_scroll.set)
        self.tree_workspace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ws_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_footer(self):
        footer_frame = ttk.Frame(self.root, padding="10 4 10 8")
        footer_frame.pack(fill=tk.X)

        self.lbl_workspace = ttk.Label(
            footer_frame,
            text=f"📂 Active Workspace: {self.workspace.root}",
            font=("Segoe UI", 9),
            foreground=theme.TEXT_SECONDARY
        )
        self.lbl_workspace.pack(side=tk.LEFT)

        btn_open_ws = ttk.Button(footer_frame, text="Open Folder", style="Control.TButton", command=self._open_workspace_folder)
        btn_open_ws.pack(side=tk.RIGHT)

        btn_clear = ttk.Button(footer_frame, text="Clear Views", style="Control.TButton", command=self._clear_displays)
        btn_clear.pack(side=tk.RIGHT, padx=6)

    # -----------------------------------------------------------------
    # CONTROL HANDLERS
    # -----------------------------------------------------------------

    def _on_enter_key_press(self, event):
        # If user is in text input, let Return submit the typed command
        if self.root.focus_get() == self.txt_input:
            return
        started = self.hold_to_talk.handle_key_press()
        if started:
            self._update_status_badge("RECORDING...")

    def _on_enter_key_release(self, event):
        if self.root.focus_get() == self.txt_input:
            return
        if self.hold_to_talk.is_recording():
            self._update_status_badge("PROCESSING...")
            self.hold_to_talk.handle_key_release()

    def _on_hold_to_talk_complete(self, wav_bytes: bytes):
        def worker():
            self.msg_queue.put(("STATUS", "TRANSCRIBING..."))
            text = self.recognizer.transcribe_wav_bytes(wav_bytes)
            if text:
                self.msg_queue.put(("TRANSCRIBED", text))
            else:
                self.msg_queue.put(("STATUS", "NO_SPEECH"))
                time.sleep(1.0)
                self.msg_queue.put(("STATUS", "IDLE"))
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_workspace_tree(self):
        """Refreshes the live workspace explorer treeview."""
        if not hasattr(self, "tree_workspace"):
            return
        for item in self.tree_workspace.get_children():
            self.tree_workspace.delete(item)

        tree_data = self.workspace.get_workspace_tree()

        def insert_node(parent_id, node_data):
            node_type = node_data.get("type", "folder")
            size_str = f"{node_data.get('size', 0)} B" if node_type == "file" else ""
            icon = "📁 " if node_type == "folder" else "📄 "
            item_id = self.tree_workspace.insert(
                parent_id,
                tk.END,
                text=f"{icon}{node_data.get('name')}",
                values=(node_type, size_str),
                open=True
            )
            for child in node_data.get("children", []):
                insert_node(item_id, child)

        insert_node("", tree_data)

    def _on_push_to_talk(self):
        """Runs single phrase recognition in background thread."""
        def worker():
            self._update_status_badge("LISTENING")
            self._log_system("Push-to-talk started listening...")
            text = self.recognizer.listen_once()
            if text:
                self._dispatch_command(text)
            else:
                self._update_status_badge("IDLE")

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_continuous_mic(self):
        """Toggles background continuous listening thread."""
        if self.recognizer.is_listening():
            self.recognizer.stop_continuous_listening()
            self.mic_state_var.set("Continuous Mic: OFF")
            self._update_status_badge("IDLE")
            self._log_system("Continuous listening deactivated.")
        else:
            success = self.recognizer.start_continuous_listening()
            if success:
                self.mic_state_var.set("Continuous Mic: ON")
                self._update_status_badge("LISTENING")
                self._log_system("Continuous listening activated.")
            else:
                messagebox.showerror("Microphone Error", "Could not start microphone listening. Check microphone settings.")

    def _on_toggle_tts(self):
        self.speaker.set_enabled(self.tts_var.get())

    def _on_execute_typed_command(self):
        cmd = self.txt_input.get().strip()
        if not cmd:
            return
        self.txt_input.delete(0, tk.END)
        self._dispatch_command(cmd)

    def _open_workspace_folder(self):
        try:
            os.startfile(str(self.workspace.root))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open workspace folder: {e}")

    def _clear_displays(self):
        for item in self.tree_plan.get_children():
            self.tree_plan.delete(item)
        self.txt_conversation.delete("1.0", tk.END)

    # -----------------------------------------------------------------
    # PIPELINE DISPATCH & THREAD MANAGEMENT
    # -----------------------------------------------------------------

    def _dispatch_command(self, user_command: str):
        """Asynchronously executes the full NLP -> Plan -> Execution pipeline."""
        def pipeline_worker():
            try:
                # 1. Processing State
                self._update_status_badge("PROCESSING")
                self._append_conversation("USER", user_command)
                self._log_system(f"Processing user utterance: '{user_command}'")

                # Parse NLP
                parsed_instructions = self.parser.parse(user_command)
                self._log_system(f"Parsed {len(parsed_instructions)} instruction clauses.")

                # 2. Planning State
                self._update_status_badge("PLANNING")
                plan = self.planner.create_plan(
                    raw_instruction=user_command,
                    parsed_instructions=parsed_instructions,
                    current_workspace_cwd=self.workspace.get_relative_cwd()
                )
                self._populate_plan_tree(plan)
                self._log_system(f"Created execution plan with {plan.total_tasks()} tasks.")

                # 3. Executing State
                self._update_status_badge("EXECUTING")
                result = self.executor.execute_plan(plan)

                # 4. Final State
                if result.overall_success:
                    self._update_status_badge("COMPLETED")
                else:
                    self._update_status_badge("FAILED")

                # Update Plan Tree with verified outcomes
                self._update_plan_tree_outcomes(result)

                # Deliver Natural English Response
                self._append_conversation("ASSISTANT", result.summary_message)
                self.speaker.speak(result.summary_message)

                # Record in History
                self._record_history(user_command, result)
                self._log_system(f"Completed command turn. Success: {result.overall_success}")

                # Refresh live workspace explorer
                self.root.after(0, self._refresh_workspace_tree)

            except Exception as e:
                logger.error(f"Error in pipeline worker: {e}", exc_info=True)
                self._update_status_badge("FAILED")
                err_msg = f"An internal error occurred: {str(e)}"
                self._append_conversation("ASSISTANT", err_msg)
                self.speaker.speak("An error occurred during task execution.")

        threading.Thread(target=pipeline_worker, daemon=True).start()

    # -----------------------------------------------------------------
    # BACKEND CALLBACKS (Thread-Safe via Queue)
    # -----------------------------------------------------------------

    def _on_voice_transcribed(self, text: str):
        self.msg_queue.put(("TRANSCRIBED", text))

    def _on_voice_status_change(self, status: str):
        self.msg_queue.put(("STATUS", status))

    def _on_executor_status(self, status: str, task: Optional[TaskItem]):
        self.msg_queue.put(("EXECUTOR_STEP", (status, task)))

    def _process_queue(self):
        """Processes events queued by background threads on the Tkinter main thread."""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "TRANSCRIBED":
                    self._dispatch_command(data)
                elif msg_type == "STATUS":
                    self._update_status_badge(data)
                elif msg_type == "EXECUTOR_STEP":
                    status, task = data
                    self._update_status_badge(status)
                    if task:
                        self._update_single_task_row(task)
                self.msg_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._process_queue)

    # -----------------------------------------------------------------
    # UI VIEW UPDATERS
    # -----------------------------------------------------------------

    def _update_status_badge(self, status: str):
        """Updates the status pill text and color."""
        status_upper = status.upper()
        self.status_var.set(status_upper)

        color_map = {
            "IDLE": theme.STATUS_IDLE,
            "LISTENING": theme.STATUS_LISTENING,
            "PROCESSING": theme.STATUS_PROCESSING,
            "PLANNING": theme.STATUS_PLANNING,
            "EXECUTING": theme.STATUS_EXECUTING,
            "VERIFYING": theme.STATUS_VERIFYING,
            "COMPLETED": theme.STATUS_COMPLETED,
            "FAILED": theme.STATUS_FAILED,
            "CALIBRATING": theme.STATUS_PROCESSING,
            "MIC_ERROR": theme.STATUS_FAILED
        }
        bg = color_map.get(status_upper, theme.STATUS_IDLE)
        self.status_pill.configure(bg=bg)

    def _append_conversation(self, speaker: str, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_conversation.configure(state=tk.NORMAL)
        if speaker == "USER":
            self.txt_conversation.insert(tk.END, f"\n[{ts}] You: ", "user")
            self.txt_conversation.insert(tk.END, f"{text}\n")
        elif speaker == "ASSISTANT":
            self.txt_conversation.insert(tk.END, f"[{ts}] Assistant: ", "assistant")
            self.txt_conversation.insert(tk.END, f"{text}\n")
        else:
            self.txt_conversation.insert(tk.END, f"[{ts}] {text}\n", "system")
        self.txt_conversation.see(tk.END)

    def _populate_plan_tree(self, plan: ExecutionPlan):
        """Clears and repopulates the task execution tree."""
        for item in self.tree_plan.get_children():
            self.tree_plan.delete(item)

        for task in plan.tasks:
            self.tree_plan.insert(
                "",
                tk.END,
                iid=str(task.task_id),
                values=(
                    task.task_id,
                    task.intent.value,
                    task.description,
                    task.status.value,
                    "No"
                )
            )

    def _update_single_task_row(self, task: TaskItem):
        """Updates status of a single row in the treeview."""
        if self.tree_plan.exists(str(task.task_id)):
            verified_str = "Yes" if task.verified else ("Failed" if task.status == TaskStatus.FAILED else "No")
            self.tree_plan.item(
                str(task.task_id),
                values=(
                    task.task_id,
                    task.intent.value,
                    task.description,
                    task.status.value,
                    verified_str
                )
            )

    def _update_plan_tree_outcomes(self, result: ExecutionResult):
        for task in result.plan.tasks:
            self._update_single_task_row(task)

    def _record_history(self, user_command: str, result: ExecutionResult):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_label = "SUCCESS" if result.overall_success else "PARTIAL/FAILED"
        entry = (
            f"--- [{ts}] [{status_label}] ---\n"
            f"Instruction: {user_command}\n"
            f"Total Tasks: {result.total} | Succeeded: {len(result.succeeded)} | Failed: {len(result.failed)}\n"
            f"Summary: {result.summary_message}\n\n"
        )
        self.txt_history.insert(tk.END, entry)
        self.txt_history.see(tk.END)

    def _log_system(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}\n"
        self.txt_logs.insert(tk.END, entry)
        self.txt_logs.see(tk.END)
