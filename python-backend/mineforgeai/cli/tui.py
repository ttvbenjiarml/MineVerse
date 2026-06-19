from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.align import Align
from rich.text import Text
from rich.layout import Layout

ROOT = Path(__file__).resolve().parents[3]


def _node_cli_available() -> bool:
    return (ROOT / "bin" / "mineforge.js").exists() and bool(shutil.which("node") or shutil.which("node.exe"))


def _list_conversations() -> list[Path]:
    conv_root = ROOT / ".mineforgeai" / "conversations"
    if not conv_root.exists():
        return []
    return sorted([p for p in conv_root.rglob("summary.md")], key=lambda p: p.stat().st_mtime, reverse=True)


def _status_rows() -> Iterable[tuple[str, str]]:
    yield ("Python", sys.executable)
    yield ("Venv", str(ROOT / ".venv" if (ROOT / ".venv").exists() else "(none)"))
    yield ("Backend", str(ROOT / "python-backend" if (ROOT / "python-backend").exists() else "(missing)"))
    yield ("Node CLI", "available" if _node_cli_available() else "unavailable")
    yield ("Package.json", "present" if (ROOT / "package.json").exists() else "absent")
    try:
        from mineforgeai.hardware import detect_hardware

        profile = detect_hardware()
        yield ("HW", f"{profile.device} {profile.performance_tier} ram={profile.available_ram_gb:.1f}GB")
    except Exception:
        yield ("HW", "unknown")


def launch_python_backend(console: Console) -> None:
    venv_python = sys.executable
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "python-backend")
    console.print("[bold green]Launching Python backend interactive...[/]\n")
    subprocess.run([venv_python, "-m", "mineforgeai.main"], env=env)


def launch_node_cli(console: Console) -> None:
    node = shutil.which("node") or shutil.which("node.exe")
    bin_js = ROOT / "bin" / "mineforge.js"
    if not node or not bin_js.exists():
        console.print("[bold red]Node CLI not available (node or bin/mineforge.js missing)[/]")
        return
    console.print("[bold green]Launching Node CLI...[/]\n")
    subprocess.run([node, str(bin_js)])


def _render_header(console: Console) -> None:
    console.clear()
    header = Panel(Align.center("MineVerse — MiMoCode-inspired CLI\nlocal Minecraft AI", vertical="middle"), style="bold magenta")
    console.print(header)


def _render_status(console: Console) -> None:
    table = Table.grid(expand=True)
    table.add_column(justify="right", ratio=20)
    table.add_column(ratio=80)
    for k, v in _status_rows():
        table.add_row(f"[cyan]{k}[/]:", f"{v}")
    console.print(Panel(table, title="Status", subtitle="Press ':' for commands, 'h' for help"))


def show_menu(console: Console) -> None:
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Key", width=6)
    table.add_column("Action")
    table.add_row("1", "Start Python backend (interactive)")
    table.add_row("2", "Launch Node CLI frontend (bin/mineforge.js)")
    table.add_row("3", "Show recent conversation summaries")
    table.add_row("4", "Write training plan (train.py)")
    table.add_row(":", "Command palette (type ':help' for commands)")
    table.add_row("q", "Quit")
    console.print(table)


def view_summaries(console: Console) -> None:
    summaries = _list_conversations()
    if not summaries:
        console.print("No conversation summaries found.")
        return
    for i, path in enumerate(summaries[:12], start=1):
        console.print(Panel(path.read_text(encoding="utf-8"), title=f"Summary {i}", width=80))
        if i != len(summaries[:12]):
            if not Confirm.ask("Next?", default=True):
                break


def command_palette(console: Console, command: str) -> None:
    cmd = command.strip()
    if cmd in (":q", ":quit", "quit"):
        raise KeyboardInterrupt
    if cmd in (":start python", "start python"):
        launch_python_backend(console)
        return
    if cmd in (":start node", "start node"):
        launch_node_cli(console)
        return
    if cmd in (":train", "train"):
        console.print("Writing training plan (invoking train.py)")
        subprocess.run([sys.executable, str(ROOT / "train.py")], env={**os.environ, "PYTHONPATH": str(ROOT / "python-backend")})
        return
    if cmd.startswith(":open "):
        target = cmd[len(":open "):].strip()
        try:
            idx = int(target) - 1
            summaries = _list_conversations()
            if 0 <= idx < len(summaries):
                console.print(Panel(summaries[idx].read_text(encoding="utf-8"), title=f"Summary {idx+1}"))
                return
        except Exception:
            pass
    if cmd in (":help", ":h", "help"):
        console.print(Panel(Text(":start python | :start node | :train | :open N | :quit"), title="Commands"))
        return
    console.print("Unknown command. Type ':help' for command list.")


def run_loop():
    console = Console()
    _render_header(console)
    while True:
        _render_status(console)
        show_menu(console)
        choice = Prompt.ask("Select", choices=["1", "2", "3", "4", ":", "q"], default="1")
        if choice == "1":
            launch_python_backend(console)
        elif choice == "2":
            if _node_cli_available():
                launch_node_cli(console)
            else:
                console.print("Node CLI not available.")
        elif choice == "3":
            view_summaries(console)
        elif choice == "4":
            console.print("Writing training plan (invoking train.py)")
            subprocess.run([sys.executable, str(ROOT / "train.py")], env={**os.environ, "PYTHONPATH": str(ROOT / "python-backend")})
        elif choice == ":":
            cmd = Prompt.ask("Command (':help' for list)")
            try:
                command_palette(console, cmd)
            except KeyboardInterrupt:
                console.print("Quitting...")
                break
        elif choice == "q":
            console.print("Goodbye.")
            break


def main() -> None:
    try:
        run_loop()
    except KeyboardInterrupt:
        print("Exiting...")


if __name__ == "__main__":
    main()
