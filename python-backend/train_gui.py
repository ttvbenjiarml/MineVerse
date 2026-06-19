"""Simple Tkinter GUI to start training and monitor progress.

This module lives inside the `python-backend` folder so the workspace root
stays minimal (only three .py files). Launch it by running `python train.py`
with no flags — it will import and call `train_gui.main()`.
"""
from __future__ import annotations

import sys
import os
import subprocess
import threading
import time
import shutil
import queue
from pathlib import Path
import json
from datetime import datetime, UTC
import re

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
except Exception:
    raise RuntimeError("Tkinter is required to run the training GUI")

ROOT = Path(__file__).parent.parent
TRAIN_PY = ROOT / "train.py"
from mineforgeai.paths import latest_model_dir


class TrainerGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("MineForgeAI Training Monitor")

        self.cmd_frame = ttk.Frame(master)
        self.cmd_frame.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(self.cmd_frame, text="Hours:").pack(side=tk.LEFT)
        import config as _cfg

        self.hours_var = tk.StringVar(value=str(getattr(_cfg, "training_hours", 1.0)))
        self.hours_entry = ttk.Entry(self.cmd_frame, width=8, textvariable=self.hours_var)
        self.hours_entry.pack(side=tk.LEFT, padx=(4, 12))

        # Dark mode toggle
        self.dark_var = tk.BooleanVar(value=True)
        self.dark_toggle = ttk.Checkbutton(self.cmd_frame, text="Dark mode", variable=self.dark_var, command=self._apply_theme)
        self.dark_toggle.pack(side=tk.RIGHT, padx=(6, 0))

        self.start_button = ttk.Button(self.cmd_frame, text="Start Training", command=self.start_training)
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = ttk.Button(self.cmd_frame, text="Stop Training", command=self.stop_training, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(6, 0))

        self.npm_button = ttk.Button(self.cmd_frame, text="Check npm", command=self.check_npm)
        self.npm_button.pack(side=tk.RIGHT)
        self.install_button = ttk.Button(self.cmd_frame, text="Run npm install", command=self.run_npm_install)
        self.install_button.pack(side=tk.RIGHT, padx=(6, 0))

        self.progress = ttk.Progressbar(master, length=600)
        self.progress.pack(fill=tk.X, padx=8, pady=(0, 6))

        self.status_label = ttk.Label(master, text="Idle")
        self.status_label.pack(fill=tk.X, padx=8)

        self.log = ScrolledText(master, height=18)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # Apply initial theme (default dark)
        self._apply_theme()

        self.proc: subprocess.Popen | None = None
        self.proc_thread: threading.Thread | None = None
        self.queue: "queue.Queue[str]" = queue.Queue()
        self.start_time: float | None = None
        self.expected_seconds: float | None = None
        self.update_loop()

    def append_log(self, text: str) -> None:
        self.log.insert(tk.END, text)
        self.log.see(tk.END)

    def _apply_theme(self) -> None:
        dark = bool(self.dark_var.get())
        style = ttk.Style()
        # try to use clam for predictable styling
        try:
            style.theme_use('clam')
        except Exception:
            pass
        if dark:
            bg = '#1e1e1e'
            panel = '#2b2b2b'
            fg = '#e6e6e6'
            entry_bg = '#2e2e2e'
            text_bg = '#0f0f0f'
            self.master.configure(bg=bg)
            style.configure('TFrame', background=bg)
            style.configure('TLabel', background=bg, foreground=fg)
            style.configure('TButton', background=panel, foreground=fg)
            style.configure('TEntry', fieldbackground=entry_bg, foreground=fg)
            style.configure('TCheckbutton', background=bg, foreground=fg)
            style.configure('Horizontal.TProgressbar', troughcolor=panel, background='#4caf50')
            # ScrolledText is a tk widget
            self.log.configure(background=text_bg, foreground=fg, insertbackground=fg)
            self.status_label.configure(background=bg, foreground=fg)
            # Entry widget (ttk) needs to set through configure when possible
            try:
                self.hours_entry.configure(background=entry_bg, foreground=fg)
            except Exception:
                pass
        else:
            # reset to defaults
            try:
                style.theme_use(style.theme_use())
            except Exception:
                pass
            self.master.configure(bg=None)
            style.configure('TFrame', background=None)
            style.configure('TLabel', background=None, foreground=None)
            style.configure('TButton', background=None, foreground=None)
            style.configure('TEntry', fieldbackground=None, foreground=None)
            self.log.configure(background='white', foreground='black', insertbackground='black')
            self.status_label.configure(background=None, foreground=None)

    def start_training(self) -> None:
        if self.proc is not None:
            return
        try:
            hours = float(self.hours_var.get())
        except Exception:
            hours = 1.0
            self.hours_var.set(str(hours))

        # If a checkpoint exists, resume mode: start trainer without --hours
        latest = latest_model_dir()
        checkpoint = latest / "checkpoint.pt"
        paused_flag = latest / "PAUSED"
        resume_mode = checkpoint.exists()

        if resume_mode and paused_flag.exists():
            # remove the PAUSED flag so trainer can resume
            try:
                paused_flag.unlink()
            except Exception:
                pass

        if resume_mode:
            cmd = [sys.executable, "-u", str(TRAIN_PY)]
            # try to set expected seconds from saved state
            try:
                state_path = latest / "state.json"
                if state_path.exists():
                    st = json.loads(state_path.read_text(encoding="utf-8"))
                    hrs = float(st.get("hours_requested", hours))
                    secs_done = float(st.get("seconds_trained", 0.0))
                    self.expected_seconds = max(0.0, hrs * 3600.0 - secs_done)
                else:
                    self.expected_seconds = hours * 3600.0
            except Exception:
                self.expected_seconds = hours * 3600.0
        else:
            cmd = [sys.executable, "-u", str(TRAIN_PY), "--hours", str(hours)]

        env = os.environ.copy()
        # launch from workspace root
        cwd = str(ROOT)

        self.append_log(f"> {' '.join(cmd)}\n")
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=cwd, env=env)
        except Exception as exc:
            self.append_log(f"Failed to start training: {exc}\n")
            self.proc = None
            return

        self.start_time = time.time()
        self.expected_seconds = hours * 3600.0
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.status_label.configure(text="Training running...")

        # thread to read stdout
        def reader():
            assert self.proc is not None
            for line in self.proc.stdout:  # type: ignore[attr-defined]
                self.queue.put(line)
            self.proc.wait()
            self.queue.put("__PROCESS_FINISHED__")

        self.proc_thread = threading.Thread(target=reader, daemon=True)
        self.proc_thread.start()

    def stop_training(self) -> None:
        if not self.proc:
            return
        # Create a PAUSED flag so the trainer can save a checkpoint and exit gracefully
        try:
            latest = latest_model_dir()
            latest.mkdir(parents=True, exist_ok=True)
            paused_flag = latest / "PAUSED"
            paused_flag.write_text(f"paused by GUI at {datetime.now(UTC).isoformat()}", encoding="utf-8")
        except Exception:
            pass
        self.append_log("Pause requested; trainer will save a checkpoint and exit shortly.\n")
        self.stop_button.configure(state=tk.DISABLED)

    def check_npm(self) -> None:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm:
            self.append_log("npm not found on PATH. Please install Node.js and npm.\n")
            return
        try:
            out = subprocess.check_output([npm, "--version"], cwd=str(ROOT), text=True, stderr=subprocess.STDOUT)
            self.append_log(f"npm version: {out.strip()}\n")
        except Exception as exc:
            self.append_log(f"npm check failed: {exc}\n")

    def run_npm_install(self) -> None:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm:
            self.append_log("npm not found on PATH. Please install Node.js and npm.\n")
            return
        pkg = ROOT / "package.json"
        if not pkg.exists():
            self.append_log("package.json not found in workspace root; skipping npm install.\n")
            return

        self.append_log("Running `npm install` - this may take a while...\n")
        try:
            # Run synchronously so user sees output
            proc = subprocess.Popen([npm, "install"], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:  # type: ignore[attr-defined]
                self.append_log(line)
            proc.wait()
            if proc.returncode == 0:
                self.append_log("npm install completed successfully.\n")
            else:
                self.append_log(f"npm install failed with exit code {proc.returncode}\n")
        except Exception as exc:
            self.append_log(f"npm install failed to run: {exc}\n")

    def update_loop(self) -> None:
        # poll queue for new lines
        try:
            while True:
                line = self.queue.get_nowait()
                if line == "__PROCESS_FINISHED__":
                    self.append_log("Process finished.\n")
                    self.proc = None
                    self.proc_thread = None
                    self.start_button.configure(state=tk.NORMAL)
                    self.stop_button.configure(state=tk.DISABLED)
                    self.status_label.configure(text="Idle")
                    self.progress.configure(value=0)
                    self.start_time = None
                    self.expected_seconds = None
                    continue
                self.append_log(line)
                # parse iter and loss for display
                m = re.search(r"iter=(\d+)\s+loss=([0-9.eE+-]+)", line)
                if m:
                    iter_count = m.group(1)
                    loss_val = m.group(2)
                    self.status_label.configure(text=f"iter={iter_count} loss={loss_val}")

        except queue.Empty:
            pass

        # update progress based on elapsed time if available
        if self.start_time and self.expected_seconds:
            elapsed = time.time() - self.start_time
            percent = min(100.0, (elapsed / self.expected_seconds) * 100.0)
            self.progress.configure(value=percent)
            if percent >= 100.0:
                self.status_label.configure(text="Finishing...")

        self.master.after(200, self.update_loop)


def main():
    root = tk.Tk()
    app = TrainerGUI(root)
    root.geometry("800x600")
    root.mainloop()


if __name__ == "__main__":
    main()
