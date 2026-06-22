from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from mineforgeai.agent.memory import append_conversation_message, load_memory, save_memory, update_memory_insights
from mineforgeai.agent.natural_language_router import route_message
from mineforgeai.agent.shell import is_safe_command
from mineforgeai.agent.tools import describe_workspace, inspect_logs, search_workspace_text
from mineforgeai.chat.context_manager import ContextManager
from mineforgeai.chat.compactor import COMPACTION_MESSAGE
from mineforgeai.cli.permission_menu import PERMISSION_MENU
from mineforgeai.hardware import detect_hardware, recommended_virtual_context_window
from mineforgeai.minecraft.generators import generate_datapack, generate_fabric_mod, generate_paper_plugin, generate_resource_pack
from mineforgeai.minecraft.java_runtime import detect_java_installations, installed_java_summary, select_java_compatibility
from mineforgeai.minecraft.validators import validate_build_gradle_kts, validate_datapack, validate_fabric_mod_json, validate_plugin_yml, validate_resource_pack
from mineforgeai.model.checkpointing import (
    find_trained_model_dir,
    model_artifact_paths,
    required_model_artifact_paths,
    trained_model_locations,
)
from mineforgeai.model.runtime import load_local_model
from mineforgeai.training.trainer import write_training_plan


# Lightweight completer that suggests top-level commands and workspace paths.
class MFCompleter:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.commands = [
            ("/permisions", "permission selector"),
            ("/permissions", "permission selector"),
            ("/permisssions", "permission selector"),
            ("/web on", "enable web research"),
            ("/web off", "disable web research"),
            ("/model", "local model status"),
            ("/model status", "diagnose local model"),
            ("/theme", "show CLI theme"),
            ("/theme set codex", "Codex-like theme"),
            ("/theme set classic", "plain theme"),
            ("/rename", "rename thread"),
            ("/clear", "clear conversation context"),
            ("/help", "show help"),
            ("exit", "close MineForgeAI"),
            ("quit", "close MineForgeAI"),
            ("read", "read a workspace file"),
            ("describe", "describe workspace"),
            ("find", "search workspace text"),
            ("generate", "generate Minecraft project"),
            ("train", "create training plan"),
        ]

    def get_completions(self, document, complete_event):
        try:
            from prompt_toolkit.completion import Completion
        except Exception:
            return
        text = (document.text_before_cursor or "").lstrip()
        # Suggest slash commands as soon as the user types `/`, like Codex CLI.
        for cmd, meta in self.commands:
            if cmd.startswith(text):
                yield Completion(cmd, start_position=-len(text), display_meta=meta)

        # If user is typing an argument (after a space), suggest workspace paths
        parts = text.split()
        if parts:
            last = parts[-1]
            if len(last) >= 1:
                try:
                    # Limit suggestions to first 200 entries to avoid slowdowns
                    count = 0
                    for p in sorted(self.workspace.rglob("*")):
                        if count > 200:
                            break
                        if not p.is_file() and not p.is_dir():
                            continue
                        rel = p.relative_to(self.workspace).as_posix()
                        if rel.startswith(last):
                            count += 1
                            yield Completion(rel, start_position=-len(last))
                except Exception:
                    pass

    async def get_completions_async(self, document, complete_event):
        for completion in self.get_completions(document, complete_event):
            yield completion


def startup_text(workspace: Path, model_label: str, has_model: bool, permission_label: str = "Ask Before Actions", web_enabled: bool = False) -> str:
    profile = detect_hardware()
    virtual_window = recommended_virtual_context_window(profile)
    vm_status = "on" if profile.virtual_memory_enabled else "off"
    mode = model_label if has_model else "fallback tool mode"
    tail = "Local trained model detected and ready." if has_model else "No trained local model was found. I can still help using templates, project analysis, web research if enabled, and deterministic Minecraft tools. I can also train a local model when you ask."

    memory = load_memory(workspace)
    theme = memory.get("ui_theme", "codex")

    if theme == "codex":
        cyan = "\033[1;36m"
        green = "\033[1;32m"
        gray = "\033[90m"
        white = "\033[1;37m"
        reset = "\033[0m"
        blue = "\033[1;34m"

        title_line = f"{green}>_ MineForgeAI (interactive){reset}"
        model_line = f"{cyan}model:{reset}     {mode}   {gray}/model status{reset}"
        dir_line = f"{cyan}directory:{reset} {workspace}"

        def clean_len(s):
            import re
            return len(re.sub(r'\033\[[0-9;]*m', '', s))

        width = max(clean_len(line) for line in [title_line, "", model_line, dir_line])
        top = f"{blue}╭" + "─" * (width + 2) + f"╮{reset}"
        bottom = f"{blue}╰" + "─" * (width + 2) + f"╯{reset}"

        def fmt_line(label_clean, label_styled):
            extra_spaces = width - clean_len(label_clean)
            return f"{blue}│{reset} {label_styled}" + " " * extra_spaces + f" {blue}│{reset}"

        m1 = fmt_line(">_ MineForgeAI (interactive)", title_line)
        m2 = fmt_line("", "")
        m3 = fmt_line(f"model:     {mode}   /model status", model_line)
        m4 = fmt_line(f"directory: {workspace}", dir_line)

        middle = "\n".join([m1, m2, m3, m4])
        tip = f"{gray}Tip: Use /rename to rename threads for easier resuming.{reset}"
        body = "\n".join([top, middle, bottom, "", tip, ""])

        status_lines = [
            f"{white}Permissions:{reset} {permission_label}",
            f"{white}Web:{reset} {'on' if web_enabled else 'off'}",
            f"{white}Java:{reset} {installed_java_summary()}",
            f"{white}Memory:{reset} RAM {profile.available_ram_gb:.2f}/{profile.total_ram_gb:.2f} GB, virtual memory {vm_status}",
            f"{white}Context:{reset} auto-compacting virtual context {virtual_window} tokens",
            f"{gray}Commands: /permisions, /web on, /web off{reset}",
            f"{gray}Update CLI: npm install -g mineforge@latest{reset}",
            "",
            f"{green}Just tell me what you want to build or fix.{reset}",
            f"{white}{tail}{reset}",
        ]
        return body + "\n".join(status_lines)

    # Classic/plain header
    return "\n".join(
        [
            "MineForgeAI Omniverse",
            "",
            f"Workspace: {workspace}",
            f"Model: {mode}",
            f"Permissions: {permission_label}",
            f"Web: {'on' if web_enabled else 'off'}",
            f"Java: {installed_java_summary()}",
            f"Memory: RAM {profile.available_ram_gb:.2f}/{profile.total_ram_gb:.2f} GB, virtual memory {vm_status}",
            f"Context: auto-compacting virtual context {virtual_window} tokens",
            "Commands: /permisions, /web on, /web off",
            "Update CLI: npm install -g mineforge@latest",
            "",
            "Just tell me what you want to build or fix.",
            tail,
        ]
    )


class InteractiveApp:
    def __init__(self, workspace: Path, model_label: str, has_model: bool) -> None:
        self.workspace = workspace
        self.model_label = model_label
        self.has_model = has_model
        self.state_dir = workspace / ".mineforgeai"
        self.permissions_path = self.state_dir / "permissions.json"
        self.context = ContextManager(max_messages=20)
        self.hardware_profile = detect_hardware()
        self.context.virtual_context_window_tokens = recommended_virtual_context_window(self.hardware_profile)
        self.pending_action: dict | None = None
        self.conversation_dir = self.state_dir / "conversations" / datetime.now(UTC).strftime("%Y-%m-%d")
        self.model_dir = find_trained_model_dir(workspace)
        self.local_model = None
        if has_model:
            try:
                self.local_model = load_local_model(workspace)
            except Exception as exc:
                self.has_model = False
                self.model_label = f"fallback tool mode (local model failed to load: {exc})"
        self.context.load_summary(self._load_latest_summary())
        # prompt_toolkit PromptSession (lazy-created)
        self._prompt_session = None

    def _load_latest_summary(self) -> str:
        conversations_root = self.state_dir / "conversations"
        if not conversations_root.exists():
            return ""
        summaries = sorted(conversations_root.glob("*/summary.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not summaries:
            return ""
        return summaries[0].read_text(encoding="utf-8", errors="replace")[:4000]

    def load_permissions(self) -> dict:
        return json.loads(self.permissions_path.read_text(encoding="utf-8"))

    def save_permissions(self, payload: dict) -> None:
        self.permissions_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def permission_label(self) -> str:
        mode = self.load_permissions().get("mode", "ask_before_actions")
        return {
            "see_edits": "See Edits",
            "ask_before_actions": "Ask Before Actions",
            "full_access": "Full Access",
        }.get(mode, "Ask Before Actions")

    def is_web_enabled(self) -> bool:
        return load_memory(self.workspace).get("web_enabled", False)

    def set_web_enabled(self, enabled: bool) -> None:
        payload = load_memory(self.workspace)
        payload["web_enabled"] = enabled
        save_memory(self.workspace, payload)

    def maybe_onboard_permissions(self) -> str | None:
        permissions = self.load_permissions()
        if permissions.get("initialized"):
            return None
        # If a permission mode was provided via environment or the mode is already
        # non-default, persist it and skip interactive onboarding to behave like
        # a normal chatbot on first launch.
        env_mode = os.environ.get("MINEFORGE_PERMISSION_MODE")
        if env_mode:
            permissions["mode"] = env_mode
            permissions["initialized"] = True
            self.save_permissions(permissions)
            return None
        if permissions.get("mode") in {"full_access", "see_edits"}:
            permissions["initialized"] = True
            self.save_permissions(permissions)
            return None
        # Otherwise, run the onboarding selector and set initialized flag.
        permissions["initialized"] = True
        self.save_permissions(permissions)
        return self._select_permission_mode("Choose how much control MineForgeAI has in this folder.")

    def persist_message(self, role: str, content: str) -> None:
        self.context.add(role, content)
        append_conversation_message(self.workspace, self.conversation_dir, role, content)
        update_memory_insights(self.workspace, role, content)
        compacted = self.context.maybe_compact(self.conversation_dir, threshold=220)
        if compacted is not None:
            print(COMPACTION_MESSAGE, flush=True)

    def _confirm(self, question: str) -> bool:
        # Use prompt toolkit prompt when available for consistent UX
        try:
            answer = self._prompt(question + " ").strip().lower()
        except KeyboardInterrupt:
            return False
        return answer in {"y", "yes"}

    def _write_allowed(self) -> bool:
        permission = self.load_permissions().get("mode", "ask_before_actions")
        if permission == "full_access":
            return True
        if permission == "see_edits":
            return False
        return self._confirm("I can make those file changes now. Allow file edits in this workspace for this action? (y/n)")

    def _run_allowed(self, command: str) -> bool:
        if not is_safe_command(command):
            return False
        permission = self.load_permissions().get("mode", "ask_before_actions")
        if permission == "full_access":
            return True
        if permission == "see_edits":
            return False
        return self._confirm(f"I can run `{command}` now. Allow this command? (y/n)")

    def _prompt(self, prompt_text: str) -> str:
        """Prompt the user for input using prompt_toolkit if available, otherwise fall back to builtin input()."""
        is_main_prompt = prompt_text == " >_ "
        if is_main_prompt:
            ws_name = self.workspace.name
            branch = ""
            try:
                git_head = self.workspace / ".git" / "HEAD"
                if git_head.exists():
                    head_content = git_head.read_text(encoding="utf-8").strip()
                    if head_content.startswith("ref:"):
                        if head_content.startswith("ref: refs/heads/"):
                            branch = " (" + head_content[len("ref: refs/heads/"):] + ")"
                        else:
                            branch = " (" + head_content.split("/")[-1] + ")"
            except Exception:
                pass
            prompt_html = f'<style fg="ansiwhite" bold="true">mineforge</style> <style fg="ansigray">[{ws_name}{branch}]</style> <style fg="ansigreen" bold="true">></style> '
            prompt_plain = f"\033[1;37mmineforge\033[0m \033[90m[{ws_name}{branch}]\033[0m \033[1;32m>\033[0m "
        else:
            prompt_html = prompt_text
            prompt_plain = prompt_text

        if os.environ.get("MINEFORGE_PLAIN_INPUT") == "1":
            return input(prompt_plain)

        # Lazy create PromptSession to avoid hard dependency at import time
        if self._prompt_session is None:
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.completion import CompleteStyle
                from prompt_toolkit.key_binding import KeyBindings
                from prompt_toolkit.styles import Style

                key_bindings = KeyBindings()

                @key_bindings.add("enter")
                def _(event):
                    buffer = event.current_buffer
                    state = buffer.complete_state
                    if state and state.current_completion:
                        buffer.apply_completion(state.current_completion)
                    else:
                        buffer.validate_and_handle()

                style = Style.from_dict({
                    "completion-menu.completion": "bg:#1f2937 #d1d5db",
                    "completion-menu.completion.current": "bg:#2563eb #ffffff",
                    "completion-menu.meta.completion": "bg:#111827 #9ca3af",
                    "completion-menu.meta.completion.current": "bg:#1d4ed8 #ffffff",
                })
                self._prompt_session = PromptSession(
                    completer=MFCompleter(self.workspace),
                    complete_while_typing=True,
                    complete_style=CompleteStyle.COLUMN,
                    key_bindings=key_bindings,
                    reserve_space_for_menu=8,
                    style=style,
                )
            except Exception:
                # mark as False to avoid retrying import repeatedly
                self._prompt_session = False

        if self._prompt_session:
            try:
                if is_main_prompt:
                    from prompt_toolkit import HTML
                    return self._prompt_session.prompt(HTML(prompt_html))
                else:
                    return self._prompt_session.prompt(prompt_html)
            except (KeyboardInterrupt, EOFError):
                raise
            except Exception:
                # fallback to builtin
                pass
        # fallback
        return input(prompt_plain)

    def _select_permission_mode(self, title: str = "MineForgeAI Permissions") -> str:
        values = [
            ("see_edits", "See Edits - inspect and suggest only"),
            ("ask_before_actions", "Ask Before Actions - ask before edits or commands"),
            ("full_access", "Full Access - edit files and run normal project commands"),
        ]
        try:
            if os.environ.get("MINEFORGE_PLAIN_INPUT") == "1" or not sys.stdin.isatty():
                raise RuntimeError("plain permission selector requested")
            from prompt_toolkit.shortcuts import radiolist_dialog
            from prompt_toolkit.styles import Style

            style = Style.from_dict({
                "dialog": "bg:#111827",
                "dialog frame.label": "bg:#111827 #ffffff",
                "dialog.body": "bg:#111827 #d1d5db",
                "radio-selected": "#22c55e",
                "radio": "#9ca3af",
                "button": "bg:#1f2937 #d1d5db",
                "button.focused": "bg:#2563eb #ffffff",
            })
            selected = radiolist_dialog(
                title=title,
                text="Use arrow keys, then Enter.",
                values=values,
                default="ask_before_actions",
                style=style,
            ).run()
            if selected is None:
                selected = "ask_before_actions"
        except Exception:
            print(PERMISSION_MENU, flush=True)
            selected = self._prompt("Select 1, 2, or 3: ").strip()
            selected = {"1": "see_edits", "2": "ask_before_actions", "3": "full_access"}.get(selected, "ask_before_actions")

        self.save_permissions({"mode": selected, "initialized": True})
        return f"Permissions updated: {self.permission_label()}"

    def _handle_permission_selection(self, raw: str) -> str:
        choice = raw.strip()
        if choice == "1":
            payload = {"mode": "see_edits", "initialized": True}
        elif choice == "2":
            payload = {"mode": "ask_before_actions", "initialized": True}
        elif choice == "3":
            payload = {"mode": "full_access", "initialized": True}
        else:
            return "I did not recognize that selection. Choose 1, 2, or 3."
        self.save_permissions(payload)
        return f"Permissions updated: {self.permission_label()}"

    def _generate_project(self, route: dict) -> str:
        project_name = route.get("project_name") or route.get("suggested_name") or "MineForgeProject"
        package_name = route.get("package_name") or "com.mineforgeai.generated"
        files = []
        issues = []
        if route["platform"] == "paper":
            compatibility = select_java_compatibility("paper", route.get("version", "1.21.1"))
            files = generate_paper_plugin(self.workspace, project_name, package_name, route)
            plugin_yml = self.workspace / project_name / "src" / "main" / "resources" / "plugin.yml"
            build_kts = self.workspace / project_name / "build.gradle.kts"
            issues = validate_plugin_yml(plugin_yml) + validate_build_gradle_kts(build_kts)
        elif route["platform"] == "fabric":
            compatibility = select_java_compatibility("fabric", route.get("version", "1.20.1"))
            files = generate_fabric_mod(self.workspace, project_name, package_name, route)
            mod_json = self.workspace / project_name / "src" / "main" / "resources" / "fabric.mod.json"
            build_kts = self.workspace / project_name / "build.gradle.kts"
            issues = validate_fabric_mod_json(mod_json) + validate_build_gradle_kts(build_kts)
        elif route["platform"] == "datapack":
            compatibility = select_java_compatibility("paper", route.get("version", "1.21.1"))
            files = generate_datapack(self.workspace, project_name, route)
            issues = validate_datapack(self.workspace / project_name, route.get("namespace", project_name.lower()), route.get("version"))
        elif route["platform"] == "resourcepack":
            compatibility = select_java_compatibility("paper", route.get("version", "1.21.1"))
            files = generate_resource_pack(self.workspace, project_name, route)
            issues = validate_resource_pack(self.workspace / project_name, route.get("namespace", project_name.lower()))
        else:
            return "I understand the request, but this platform generator is not implemented yet in the interactive runtime."

        summary = [f"Created `{project_name}`."]
        summary.append(f"Platform: {route['platform']} requested {route.get('version', 'best-effort')}.")
        summary.append(f"Resolved target version: {compatibility.effective_version}.")
        summary.append(f"Java detected: {installed_java_summary(detect_java_installations())}.")
        summary.append(f"Virtual context budget: {self.context.virtual_context_window_tokens} tokens.")
        summary.append(compatibility.message)
        summary.append(f"Files created: {len(files)}")
        if issues:
            summary.append("Validator notes:")
            summary.extend(f"- {issue}" for issue in issues)
        else:
            summary.append("Validators passed for the generated project metadata.")
        if route["platform"] in {"paper", "fabric"}:
            build_command = "gradlew.bat build" if os.name == "nt" else "./gradlew build"
            if self._run_allowed(build_command):
                summary.append(f"Build command allowed: `{build_command}`")
            else:
                summary.append(f"Build not run automatically. Suggested command: `{build_command}`")
        return "\n".join(summary)

    def respond(self, text: str) -> str:
        trimmed = text.strip()
        # Load user preferences (model, theme) early so commands can inspect/change them
        memory_payload = load_memory(self.workspace)
        # CLI model/theme commands
        if trimmed.startswith("/model"):
            parts = trimmed.split()
            if len(parts) == 1 or (len(parts) >= 2 and parts[1].lower() in {"status", "diagnose", "info"}):
                return self._diagnose_local_model()
            return "Only the local MineForgeAI model is available. Use `/model status` to inspect it."

        if trimmed in {"/model status", "/model diagnose", "/model info"}:
            return self._diagnose_local_model()

        if trimmed.startswith("/theme"):
            parts = trimmed.split()
            current = memory_payload.get("ui_theme", "codex")
            if len(parts) == 1:
                return f"UI theme: {current}. Options: codex, classic. Set with '/theme set <name>'."
            if parts[1] in ("set", "use") and len(parts) >= 3:
                choice = parts[2].lower()
            else:
                choice = parts[1].lower()
            if choice not in {"codex", "classic"}:
                return "Unknown theme. Options: codex, classic."
            memory_payload["ui_theme"] = choice
            save_memory(self.workspace, memory_payload)
            return f"UI theme set to: {choice}"
        if trimmed in {"/permisions", "/permissions", "/permisssions"}:
            return self._select_permission_mode()
        if trimmed == "/web on":
            self.set_web_enabled(True)
            return "Web search enabled. I will use online sources when current docs, versions, or errors need verification."
        if trimmed == "/web off":
            self.set_web_enabled(False)
            return "Web search disabled. I will only use local files, cached docs, and built-in knowledge."
        if trimmed == "/help":
            return self._help_text()
        if trimmed.startswith("/rename"):
            parts = trimmed.split(maxsplit=1)
            new_name = parts[1].strip() if len(parts) > 1 else ""
            return self._rename_thread(new_name)
        if trimmed == "/clear":
            self.context.messages.clear()
            self.context.prior_summary = ""
            return "Context cleared. Starting fresh — previous messages have been removed from working memory."
        if trimmed.startswith("/"):
            return "Unknown command. Type `/help` to see available commands."
        if "search online" in trimmed.lower() and not self.is_web_enabled():
            return "Web search is off. Type /web on to allow online research."

        route = route_message(trimmed)
        if route["type"] == "clarification":
            return route["message"]
        if route["type"] == "generate_project":
            if not self._write_allowed():
                return "I prepared the project plan, but current permissions do not allow writing right now. Use `/permisions` or approve the edit when asked."
            return self._generate_project(route)
        if route["type"] == "analyze_crash":
            logs = inspect_logs(self.workspace)
            if not logs:
                return "I could not find a likely log in this workspace. Add `latest.log`, `debug.log`, or a crash report here and ask again."
            return logs
        if route["type"] == "train_model":
            hours = route.get("hours", 2)
            plan_path = write_training_plan(hours, self.workspace)
            return (
                f"Training plan created for about {hours} hour(s). "
                f"The plan targets Minecraft plugins, mods, datapacks, resource packs, Gradle projects, mappings, crash logs, and user projects. "
                f"Saved: `{plan_path}`"
            )
        if route["type"] == "workspace_review":
            return describe_workspace(self.workspace)
        if route["type"] == "search_workspace":
            return search_workspace_text(self.workspace, route["query"])
        # Local model generation only; deterministic tools handle requests when it is unavailable.
        prompt = self._build_model_prompt(text)

        def try_local():
            # Attempt to lazily load the local model if it wasn't available at startup
            if self.local_model is None:
                try:
                    self.local_model = load_local_model(self.workspace)
                except Exception:
                    self.local_model = None
            if self.local_model is None:
                return ""
            try:
                return self.local_model.generate_text(prompt, profile=self.local_model.preferred_profile)
            except Exception:
                return ""

        def try_local_streaming():
            """Attempt streaming generation from the local model."""
            if self.local_model is None:
                try:
                    self.local_model = load_local_model(self.workspace)
                except Exception:
                    self.local_model = None
            if self.local_model is None:
                return None
            try:
                return self.local_model.generate_text_streaming(prompt, profile=self.local_model.preferred_profile)
            except Exception:
                return None

        # Prefer streaming; fall back to batch; fall back to deterministic
        stream = try_local_streaming()
        if stream is not None:
            # Signal to run() that this is a streaming response
            return ("__STREAM__", stream)
        generated = try_local()
        if generated.strip():
            return generated.strip()
        # Fallback: no local model available — provide helpful deterministic responses
        return self.fallback_chat_response(text)

    def fallback_chat_response(self, text: str) -> str:
        """Simple deterministic fallback responder when no local model is loaded.

        Tries to inspect workspace files (plugin.yml, README.md, build files) and
        returns a concise summary. This keeps the CLI conversational when a model
        isn't present.
        """
        lowered = text.lower().strip()
        # If user asks to read the workspace or ask about a plugin, try to summarize
        if any(word in lowered for word in ("read", "tell me", "what does", "describe")) and "plugin" in lowered:
            # Look for plugin.yml
            candidates = list(self.workspace.rglob("plugin.yml"))
            if candidates:
                plugin = candidates[0]
                try:
                    content = plugin.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    return f"Found {plugin.relative_to(self.workspace)} but could not read it."
                # crude parsing
                name = None
                main = None
                version = None
                description = None
                commands = []
                in_commands = False
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        in_commands = False
                        continue
                    if stripped.startswith("name:") and not name:
                        name = stripped.split(":", 1)[1].strip()
                    if stripped.startswith("main:") and not main:
                        main = stripped.split(":", 1)[1].strip()
                    if stripped.startswith("version:") and not version:
                        version = stripped.split(":", 1)[1].strip()
                    if stripped.startswith("description:") and not description:
                        description = stripped.split(":", 1)[1].strip()
                    if stripped.startswith("commands:"):
                        in_commands = True
                        continue
                    if in_commands and stripped and stripped.endswith(":"):
                        commands.append(stripped[:-1])
                lines = [f"I inspected `{plugin.relative_to(self.workspace)}`."]
                if name:
                    lines.append(f"- Name: {name}")
                if main:
                    lines.append(f"- Main class: {main}")
                if version:
                    lines.append(f"- Version: {version}")
                if description:
                    lines.append(f"- Description: {description}")
                if commands:
                    lines.append(f"- Commands: {', '.join(commands)}")
                if len(lines) == 1:
                    lines.append("I could not parse key fields; here's the raw file preview:")
                    lines.extend(content.splitlines()[:10])
                return "\n".join(lines)

        # If user asks to read current folder generically, show a workspace preview
        if any(phrase in lowered for phrase in ("read the current folder", "read current folder", "what is in the folder", "read the folder", "describe workspace", "what does this folder")):
            return describe_workspace(self.workspace)

        # If they asked to 'read README' or similar, show README head
        if "readme" in lowered or "readme.md" in lowered:
            candidates = list(self.workspace.glob("README.md"))
            if candidates:
                try:
                    text = candidates[0].read_text(encoding="utf-8", errors="replace")
                    preview = "\n".join(text.splitlines()[:12])
                    return f"I found README.md — first lines:\n\n{preview}"
                except OSError:
                    return "Found README.md but could not read it."

        # Generic fallback help when no model present
        return (
            f"(Fallback mode) I don't have a local model available. You asked: \"{text.strip()}\"\n"
            "I can still:\n"
            "- Inspect the workspace files (try: 'Read the current folder' or 'Read plugin.yml')\n"
            "- Search for text (try: 'find <term>')\n"
            "- Generate project scaffolds when you ask (limited helpers)\n"
            "If you'd like a conversational model, place a trained model in `.mineforgeai/models/latest` or set `MINEFORGE_MODEL_URL` and run `start_bot.py` to download it."
        )

    def _build_model_prompt(self, user_text: str) -> str:
        recent = self.context.recent_messages(8)
        history = "\n".join(f"{message['role']}: {message['content']}" for message in recent)
        summary = self.context.prior_summary or "No long-term summary yet."
        memory_payload = load_memory(self.workspace)
        insights = memory_payload.get("insights", {})
        goals = insights.get("goals", [])[-8:]
        preferences = insights.get("preferences", [])[-8:]
        facts = insights.get("important_facts", [])[-12:]
        memory_block = "\n".join([
            "Goals:",
            *[f"- {item}" for item in goals],
            "Preferences:",
            *[f"- {item}" for item in preferences],
            "Important facts:",
            *[f"- {item}" for item in facts],
        ])
        return (
            "You are MineForgeAI, a local Minecraft development chatbot and coding agent. "
            "Answer naturally, stay helpful, and prefer Minecraft development context.\n\n"
            f"Long-term summary:\n{summary}\n\n"
            f"Persistent memory:\n{memory_block}\n\n"
            f"Recent conversation:\n{history}\n\n"
            f"user: {user_text}\nassistant:"
        )

    def _diagnose_local_model(self) -> str:
        """Return diagnostic information about candidate trained model locations and PyTorch availability."""
        lines: list[str] = []
        workspace = self.workspace
        candidates = trained_model_locations(workspace)
        found = find_trained_model_dir(workspace)
        if found is not None:
            lines.append(f"Found trained model at: {found}")
            artifacts = model_artifact_paths(found)
            for name, path in artifacts.items():
                optional = " (optional)" if name == "state" else ""
                missing = "missing" if name == "state" else "MISSING"
                lines.append(f"- {name}{optional}: {'exists' if path.exists() else missing} ({path})")
        else:
            lines.append("No trained model found in known locations.")
            lines.append("Checked candidate locations:")
            for candidate in candidates:
                lines.append(f"- {candidate}:")
                artifacts = required_model_artifact_paths(candidate)
                for name, path in artifacts.items():
                    lines.append(f"    - {name}: {'exists' if path.exists() else 'missing'} ({path})")

        try:
            import torch

            lines.append(f"PyTorch available: True (version {getattr(torch, '__version__', 'unknown')})")
        except Exception:
            lines.append("PyTorch available: False — install torch in the runtime venv to load local models")

        # If a model dir was found, attempt a light-weight check of tokenizer/config readability
        if found is not None:
            artifacts = model_artifact_paths(found)
            tokenizer_path = artifacts.get('tokenizer')
            config_path = artifacts.get('config')
            try:
                if tokenizer_path and tokenizer_path.exists():
                    tokenizer_text = tokenizer_path.read_text(encoding='utf-8', errors='replace')[:400]
                    lines.append(f"Tokenizer preview: {tokenizer_path} (first 400 chars):")
                    lines.append(tokenizer_text)
                if config_path and config_path.exists():
                    config_text = config_path.read_text(encoding='utf-8', errors='replace')[:400]
                    lines.append(f"Model config preview: {config_path} (first 400 chars):")
                    lines.append(config_text)
            except Exception as exc:
                lines.append(f"Could not read tokenizer/config: {exc}")

        lines.append("\nIf files are missing, place weights as 'model.pt', tokenizer as 'tokenizer.json', and config as 'model_config.json' in one of the candidate locations listed above. Then restart the CLI.")
        return "\n".join(lines)

    def _help_text(self) -> str:
        """Return a comprehensive help message listing all available commands."""
        memory = load_memory(self.workspace)
        theme = memory.get("ui_theme", "codex")
        if theme == "codex":
            cyan = "\033[1;36m"
            green = "\033[1;32m"
            gray = "\033[90m"
            white = "\033[1;37m"
            reset = "\033[0m"
        else:
            cyan = green = gray = white = reset = ""

        return "\n".join([
            f"{green}MineForgeAI — Available Commands{reset}",
            "",
            f"  {cyan}/permissions{reset}  {gray}Change workspace permissions (see edits / ask / full access){reset}",
            f"  {cyan}/web on{reset}       {gray}Enable web research for answers{reset}",
            f"  {cyan}/web off{reset}      {gray}Disable web research{reset}",
            f"  {cyan}/model status{reset} {gray}Diagnose local model, show PyTorch and checkpoint info{reset}",
            f"  {cyan}/theme set X{reset}  {gray}Set UI theme (codex, classic){reset}",
            f"  {cyan}/rename X{reset}     {gray}Rename the current conversation thread{reset}",
            f"  {cyan}/clear{reset}        {gray}Clear conversation context and start fresh{reset}",
            f"  {cyan}/help{reset}         {gray}Show this help message{reset}",
            "",
            f"{green}Natural Language{reset}",
            f"  {white}Just type what you want.{reset} MineForgeAI routes your request to the",
            f"  appropriate tool: project generation, crash analysis, workspace search,",
            f"  training, or freeform AI chat.",
            "",
            f"{green}Examples{reset}",
            f"  {gray}make a paper plugin that adds custom enchantments{reset}",
            f"  {gray}find CommandExecutor in this project{reset}",
            f"  {gray}read the current folder{reset}",
            f"  {gray}train the local model for 4 hours{reset}",
            "",
            f"  Type {cyan}exit{reset} or {cyan}quit{reset} to close.",
        ])

    def _rename_thread(self, new_name: str) -> str:
        """Rename the current conversation thread directory."""
        if not new_name:
            return "Usage: `/rename My Thread Name`"
        # Sanitize the name for filesystem safety
        import re
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', new_name).strip()[:80]
        if not safe_name:
            return "Invalid name. Use alphanumeric characters and spaces."
        old_dir = self.conversation_dir
        new_dir = old_dir.parent / safe_name
        if new_dir.exists():
            return f"A thread named `{safe_name}` already exists. Pick a different name."
        try:
            old_dir.mkdir(parents=True, exist_ok=True)
            old_dir.rename(new_dir)
            self.conversation_dir = new_dir
            return f"Thread renamed to: `{safe_name}`"
        except Exception as exc:
            return f"Failed to rename thread: {exc}"

    def run(self) -> int:
        onboarding = self.maybe_onboard_permissions()
        print(startup_text(self.workspace, self.model_label, self.has_model, self.permission_label(), self.is_web_enabled()), flush=True)
        if onboarding:
            print(onboarding, flush=True)
        while True:
            try:
                raw = self._prompt(" >_ ")
            except EOFError:
                print("Goodbye.", flush=True)
                return 0
            if raw.strip().lower() in {"exit", "quit"}:
                print("Goodbye.", flush=True)
                return 0
            self.persist_message("user", raw)

            # Show a thinking spinner while generating the response
            spinner_active = threading.Event()
            spinner_active.set()

            def spinner():
                frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                idx = 0
                while spinner_active.is_set():
                    sys.stdout.write(f"\r\033[90m{frames[idx % len(frames)]} Thinking...\033[0m")
                    sys.stdout.flush()
                    idx += 1
                    time.sleep(0.08)
                sys.stdout.write("\r" + " " * 30 + "\r")
                sys.stdout.flush()

            spin_thread = threading.Thread(target=spinner, daemon=True)
            spin_thread.start()

            try:
                response = self.respond(raw)
            finally:
                spinner_active.clear()
                spin_thread.join(timeout=1.0)

            # Handle streaming response (tuple marker from respond)
            if isinstance(response, tuple) and len(response) == 2 and response[0] == "__STREAM__":
                stream = response[1]
                collected_chunks = []
                try:
                    use_rich = False
                    try:
                        from rich.console import Console
                        console = Console()
                        use_rich = True
                    except Exception:
                        pass

                    # Stream token by token to stdout
                    sys.stdout.write("\n")
                    for chunk in stream:
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                        collected_chunks.append(chunk)
                    sys.stdout.write("\n\n")
                    sys.stdout.flush()
                except Exception:
                    pass
                full_response = "".join(collected_chunks).strip()
                if full_response:
                    self.persist_message("assistant", full_response)
                else:
                    fallback = self.fallback_chat_response(raw)
                    self.persist_message("assistant", fallback)
                    try:
                        from rich.console import Console
                        from rich.markdown import Markdown
                        console = Console()
                        console.print()
                        console.print(Markdown(fallback))
                        console.print()
                    except Exception:
                        print(fallback, flush=True)
            else:
                self.persist_message("assistant", response)
                try:
                    from rich.console import Console
                    from rich.markdown import Markdown
                    console = Console()
                    console.print()
                    console.print(Markdown(response))
                    console.print()
                except Exception:
                    print(response, flush=True)
