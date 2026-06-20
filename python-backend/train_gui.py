"""Tkinter training control panel for MineForgeAI.

Launch by running `python train.py` with no flags.
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
except Exception as exc:
    raise RuntimeError("Tkinter is required to run the training GUI") from exc

from mineforgeai.paths import latest_model_dir

ROOT = Path(__file__).parent.parent
TRAIN_PY = ROOT / "train.py"


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class TrainerGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("MineForgeAI Training")
        self.master.minsize(900, 620)

        import config as _cfg

        self.hours_var = tk.StringVar(value=str(getattr(_cfg, "training_hours", 1.0)))
        self.mode_var = tk.StringVar(value="continue")
        self.status_var = tk.StringVar(value="Idle")
        self.source_var = tk.StringVar(value="Checking saved model...")
        self.iter_var = tk.StringVar(value="-")
        self.loss_var = tk.StringVar(value="-")
        self.total_var = tk.StringVar(value="-")
        self.session_var = tk.StringVar(value="-")

        self.proc: subprocess.Popen | None = None
        self.proc_thread: threading.Thread | None = None
        self.queue: "queue.Queue[str]" = queue.Queue()
        self.start_time: float | None = None
        self.expected_seconds: float = 0.0

        self._build_styles()
        self._build_layout()
        self.refresh_state()
        self.update_loop()

    def _build_styles(self) -> None:
        self.colors = {
            "bg": "#111827",
            "panel": "#182235",
            "panel2": "#202b3f",
            "fg": "#e5e7eb",
            "muted": "#9ca3af",
            "accent": "#22c55e",
            "warn": "#f59e0b",
            "danger": "#ef4444",
            "input": "#0b1220",
            "line": "#334155",
        }
        self.master.configure(bg=self.colors["bg"])
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Root.TFrame", background=self.colors["bg"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["fg"])
        style.configure("Panel.TLabel", background=self.colors["panel"], foreground=self.colors["fg"])
        style.configure("Muted.TLabel", background=self.colors["panel"], foreground=self.colors["muted"])
        style.configure("Value.TLabel", background=self.colors["panel"], foreground=self.colors["fg"], font=("Segoe UI", 13, "bold"))
        style.configure("Title.TLabel", background=self.colors["bg"], foreground=self.colors["fg"], font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=self.colors["bg"], foreground=self.colors["muted"])
        style.configure("TEntry", fieldbackground=self.colors["input"], foreground=self.colors["fg"], insertcolor=self.colors["fg"])
        style.configure("TRadiobutton", background=self.colors["panel"], foreground=self.colors["fg"])
        style.map("TRadiobutton", background=[("active", self.colors["panel2"])])
        style.configure("TButton", background=self.colors["panel2"], foreground=self.colors["fg"], padding=(12, 7))
        style.map("TButton", background=[("active", self.colors["line"]), ("disabled", self.colors["panel"])])
        style.configure("Accent.TButton", background=self.colors["accent"], foreground="#052e16")
        style.map("Accent.TButton", background=[("active", "#16a34a")])
        style.configure("Danger.TButton", background=self.colors["danger"], foreground="#fff7ed")
        style.map("Danger.TButton", background=[("active", "#dc2626")])
        style.configure("Horizontal.TProgressbar", troughcolor=self.colors["panel2"], background=self.colors["accent"], bordercolor=self.colors["panel"])

    def _panel(self, parent: tk.Widget, **grid) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=16)
        frame.grid(**grid)
        return frame

    def _build_layout(self) -> None:
        root = ttk.Frame(self.master, style="Root.TFrame", padding=18)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        ttk.Label(root, text="MineForgeAI Training", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(root, text="Continue from saved work by default. Start fresh only when you want to replace the latest model.", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 14))

        controls = self._panel(root, row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)

        ttk.Label(controls, text="Training mode", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        mode_frame = ttk.Frame(controls, style="Panel.TFrame")
        mode_frame.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Radiobutton(mode_frame, text="Continue latest", variable=self.mode_var, value="continue").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="Start fresh", variable=self.mode_var, value="fresh").pack(side=tk.LEFT, padx=(18, 0))

        ttk.Label(controls, text="Hours this run", style="Muted.TLabel").grid(row=0, column=1, sticky="w", padx=(24, 0))
        hours_entry = ttk.Entry(controls, textvariable=self.hours_var, width=12)
        hours_entry.grid(row=1, column=1, sticky="w", padx=(24, 0), pady=(6, 0))

        ttk.Label(controls, text="Saved model", style="Muted.TLabel").grid(row=0, column=2, sticky="w", padx=(24, 0))
        ttk.Label(controls, textvariable=self.source_var, style="Panel.TLabel").grid(row=1, column=2, sticky="w", padx=(24, 0), pady=(6, 0))

        action_frame = ttk.Frame(controls, style="Panel.TFrame")
        action_frame.grid(row=0, column=3, rowspan=2, sticky="e")
        self.start_button = ttk.Button(action_frame, text="Start", style="Accent.TButton", command=self.start_training)
        self.start_button.pack(side=tk.LEFT)
        self.pause_button = ttk.Button(action_frame, text="Pause", style="Danger.TButton", command=self.pause_training, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(action_frame, text="Open Folder", command=self.open_model_folder).pack(side=tk.LEFT, padx=(8, 0))

        stats = self._panel(root, row=3, column=0, sticky="ew", pady=(12, 12))
        for col in range(5):
            stats.columnconfigure(col, weight=1)
        self._metric(stats, 0, "Status", self.status_var)
        self._metric(stats, 1, "Iteration", self.iter_var)
        self._metric(stats, 2, "Loss", self.loss_var)
        self._metric(stats, 3, "Total trained", self.total_var)
        self._metric(stats, 4, "This run", self.session_var)

        log_panel = self._panel(root, row=4, column=0, sticky="nsew")
        log_panel.rowconfigure(1, weight=1)
        log_panel.columnconfigure(0, weight=1)
        ttk.Label(log_panel, text="Logs", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.log = ScrolledText(log_panel, height=16, wrap=tk.WORD, relief=tk.FLAT)
        self.log.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.log.configure(background=self.colors["input"], foreground=self.colors["fg"], insertbackground=self.colors["fg"], selectbackground=self.colors["line"])

        progress_row = ttk.Frame(root, style="Root.TFrame")
        progress_row.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        progress_row.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_row, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Button(progress_row, text="Refresh", command=self.refresh_state).grid(row=0, column=1, padx=(10, 0))

    def _metric(self, parent: ttk.Frame, col: int, label: str, var: tk.StringVar) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 14, 0))
        ttk.Label(frame, text=label, style="Muted.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=var, style="Value.TLabel").pack(anchor="w", pady=(4, 0))

    def append_log(self, text: str) -> None:
        self.log.insert(tk.END, text)
        self.log.see(tk.END)

    def refresh_state(self) -> None:
        latest = latest_model_dir()
        checkpoint = latest / "checkpoint.pt"
        model = latest / "model.pt"
        state = latest / "state.json"
        if checkpoint.exists():
            self.source_var.set("checkpoint ready")
        elif model.exists():
            self.source_var.set("saved model ready")
        else:
            self.source_var.set("no saved model")

        if state.exists():
            try:
                payload = json.loads(state.read_text(encoding="utf-8"))
                self.iter_var.set(str(payload.get("iterations", "-")))
                self.total_var.set(_format_duration(float(payload.get("seconds_trained", 0.0))))
                if payload.get("paused"):
                    self.status_var.set("Paused")
                elif payload.get("completed"):
                    self.status_var.set("Complete")
            except Exception:
                pass

    def _hours(self) -> float | None:
        try:
            hours = float(self.hours_var.get())
        except Exception:
            messagebox.showerror("Invalid hours", "Enter a number of hours, for example 1 or 0.5.")
            return None
        if hours <= 0:
            messagebox.showerror("Invalid hours", "Training hours must be greater than zero.")
            return None
        return hours

    def start_training(self) -> None:
        if self.proc is not None:
            return
        hours = self._hours()
        if hours is None:
            return
        fresh = self.mode_var.get() == "fresh"
        if fresh:
            ok = messagebox.askyesno("Start fresh?", "This clears the latest checkpoint and saved model before training. Continue?")
            if not ok:
                return

        latest = latest_model_dir()
        paused_flag = latest / "PAUSED"
        try:
            if paused_flag.exists():
                paused_flag.unlink()
        except Exception:
            pass

        cmd = [sys.executable, "-u", str(TRAIN_PY), "--hours", str(hours)]
        if fresh:
            cmd.append("--fresh")

        self.append_log(f"> {' '.join(cmd)}\n")
        self.status_var.set("Running")
        self.loss_var.set("-")
        self.session_var.set("0s")
        self.progress.configure(value=0)
        self.expected_seconds = hours * 3600.0
        self.start_time = time.time()

        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=str(ROOT), env=os.environ.copy())
        except Exception as exc:
            self.append_log(f"Failed to start training: {exc}\n")
            self.proc = None
            self.status_var.set("Idle")
            return

        self.start_button.configure(state=tk.DISABLED)
        self.pause_button.configure(state=tk.NORMAL)

        def reader() -> None:
            assert self.proc is not None
            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                self.queue.put(line)
            return_code = self.proc.wait()
            self.queue.put(f"__PROCESS_FINISHED__:{return_code}")

        self.proc_thread = threading.Thread(target=reader, daemon=True)
        self.proc_thread.start()

    def pause_training(self) -> None:
        if not self.proc:
            return
        try:
            latest = latest_model_dir()
            latest.mkdir(parents=True, exist_ok=True)
            (latest / "PAUSED").write_text(f"paused by GUI at {datetime.now(UTC).isoformat()}", encoding="utf-8")
            self.append_log("Pause requested. The trainer will save a checkpoint before it exits.\n")
            self.status_var.set("Pausing")
        except Exception as exc:
            self.append_log(f"Could not request pause: {exc}\n")
        self.pause_button.configure(state=tk.DISABLED)

    def open_model_folder(self) -> None:
        latest = latest_model_dir()
        latest.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(latest))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(latest)])
            else:
                subprocess.Popen(["xdg-open", str(latest)])
        except Exception as exc:
            self.append_log(f"Could not open model folder: {exc}\n")

    def update_loop(self) -> None:
        try:
            while True:
                line = self.queue.get_nowait()
                if line.startswith("__PROCESS_FINISHED__:"):
                    code = int(line.split(":", 1)[1])
                    self.append_log(f"Process finished with exit code {code}.\n")
                    self.proc = None
                    self.proc_thread = None
                    self.start_button.configure(state=tk.NORMAL)
                    self.pause_button.configure(state=tk.DISABLED)
                    self.progress.configure(value=0 if code else 100)
                    self.status_var.set("Complete" if code == 0 else "Failed")
                    self.start_time = None
                    self.refresh_state()
                    continue

                self.append_log(line)
                match = re.search(r"iter=(\d+)\s+loss=([0-9.eE+-]+)", line)
                if match:
                    self.iter_var.set(match.group(1))
                    self.loss_var.set(match.group(2))
                if line.startswith("Training source:"):
                    self.source_var.set(line.split(":", 1)[1].strip())
                if "Checkpoint saved" in line:
                    self.refresh_state()
        except queue.Empty:
            pass

        if self.start_time and self.expected_seconds > 0:
            elapsed = time.time() - self.start_time
            self.session_var.set(_format_duration(elapsed))
            percent = min(100.0, (elapsed / self.expected_seconds) * 100.0)
            self.progress.configure(value=percent)
            if percent >= 100.0 and self.proc is not None:
                self.status_var.set("Finishing")

        self.master.after(200, self.update_loop)


def main() -> None:
    root = tk.Tk()
    TrainerGUI(root)
    root.geometry("980x680")
    root.mainloop()


if __name__ == "__main__":
    main()
