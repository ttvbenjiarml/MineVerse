from __future__ import annotations

import json
import os
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
from mineforgeai.minecraft.generators import generate_fabric_mod, generate_paper_plugin
from mineforgeai.minecraft.java_runtime import detect_java_installations, installed_java_summary, select_java_compatibility
from mineforgeai.minecraft.validators import validate_build_gradle_kts, validate_fabric_mod_json, validate_plugin_yml
from mineforgeai.model.checkpointing import find_trained_model_dir, model_artifact_paths, trained_model_locations
from mineforgeai.model.runtime import load_local_model
from mineforgeai.model.remote_runtime import RemoteModelRuntime
from mineforgeai.training.trainer import write_training_plan


# Lightweight completer that suggests top-level commands and workspace paths.
class MFCompleter:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.commands = [
            "/permisions",
            "/permissions",
            "/web on",
            "/web off",
            "/model",
            "/model set",
            "/model status",
            "/theme",
            "/theme set",
            "/rename",
            "/help",
            "exit",
            "quit",
            "read",
            "describe",
            "find",
            "generate",
            "train",
        ]

    def get_completions(self, document, complete_event):
        try:
            from prompt_toolkit.completion import Completion
        except Exception:
            return
        text = (document.text_before_cursor or "").lstrip()
        # Suggest commands that start with the current buffer
        for cmd in self.commands:
            if cmd.startswith(text):
                yield Completion(cmd, start_position=-len(text))

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


def startup_text(workspace: Path, model_label: str, has_model: bool, permission_label: str = "Ask Before Actions", web_enabled: bool = False) -> str:
    profile = detect_hardware()
    virtual_window = recommended_virtual_context_window(profile)
    vm_status = "on" if profile.virtual_memory_enabled else "off"
    mode = model_label if has_model else "fallback tool mode"
    tail = "Local trained model detected and ready." if has_model else "No trained local model was found. I can still help using templates, project analysis, web research if enabled, and deterministic Minecraft tools. I can also train a local model when you ask."

    memory = load_memory(workspace)
    theme = memory.get("ui_theme", "codex")

    if theme == "codex":
        lines = [
            f">_ MineForgeAI (interactive)",
            "",
            f"model:     {mode}   /model to change",
            f"directory: {workspace}",
        ]

        # compute width and build box using unicode box drawing
        width = max(len(line) for line in lines)
        top = "╭" + "─" * (width + 2) + "╮"
        bottom = "╰" + "─" * (width + 2) + "╯"
        middle = "\n".join("│ " + line.ljust(width) + " │" for line in lines)
        tip = "Tip: Use /rename to rename threads for easier resuming."

        body = "\n".join([top, middle, bottom, "", tip, ""])
        # additional status lines below the box
        status_lines = [
            f"Permissions: {permission_label}",
            f"Web: {'on' if web_enabled else 'off'}",
            f"Java: {installed_java_summary()}",
            f"Memory: RAM {profile.available_ram_gb:.2f}/{profile.total_ram_gb:.2f} GB, virtual memory {vm_status}",
            f"Context: auto-compacting virtual context {virtual_window} tokens",
            "Commands: /permisions, /web on, /web off",
            "",
            "Just tell me what you want to build or fix.",
            tail,
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
            "custom": "Custom",
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
        # Otherwise, run the onboarding menu and set initialized flag.
        permissions["initialized"] = True
        self.save_permissions(permissions)
        return "\n".join([PERMISSION_MENU, "", "Default selected for first launch: 2. Ask Before Actions"]) 

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
        # Lazy create PromptSession to avoid hard dependency at import time
        if self._prompt_session is None:
            try:
                from prompt_toolkit import PromptSession
                self._prompt_session = PromptSession(completer=MFCompleter(self.workspace), complete_while_typing=True)
            except Exception:
                # mark as False to avoid retrying import repeatedly
                self._prompt_session = False

        if self._prompt_session:
            try:
                return self._prompt_session.prompt(prompt_text)
            except (KeyboardInterrupt, EOFError):
                raise
            except Exception:
                # fallback to builtin
                pass
        # fallback
        return input(prompt_text)

    def _handle_permission_selection(self, raw: str) -> str:
        choice = raw.strip()
        if choice == "1":
            payload = {"mode": "see_edits", "initialized": True}
        elif choice == "2":
            payload = {"mode": "ask_before_actions", "initialized": True}
        elif choice == "3":
            payload = {"mode": "full_access", "initialized": True}
        elif choice == "4":
            payload = {
                "mode": "custom",
                "initialized": True,
                "custom": {
                    "read_files": True,
                    "write_files": False,
                    "create_files": False,
                    "delete_files": "ask",
                    "run_commands": "ask",
                    "install_dependencies": "ask",
                    "use_web": False,
                    "allow_outside_workspace": False,
                    "show_diffs_before_edit": True,
                },
            }
        else:
            return "I did not recognize that selection. Choose 1, 2, 3, or 4."
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
            summary.append("Validators passed for the generated metadata and build file.")
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
        model_pref = memory_payload.get("model", os.environ.get("MINEFORGE_DEFAULT_MODEL", "auto"))

        # CLI model/theme commands
        if trimmed.startswith("/model"):
            parts = trimmed.split()
            if len(parts) == 1:
                return f"Model preference: {model_pref}. Options: auto, local, openai, mock. Set with '/model set <name>'."
            # accept '/model set <name>' or '/model <name>'
            if parts[1] in ("set", "use") and len(parts) >= 3:
                choice = parts[2].lower()
            else:
                choice = parts[1].lower()
            # support diagnostic subcommand
            if choice in {"status", "diagnose", "info"}:
                return self._diagnose_local_model()
            if choice not in {"auto", "local", "openai", "mock"}:
                return "Unknown model. Options: auto, local, openai, mock."
            memory_payload["model"] = choice
            save_memory(self.workspace, memory_payload)
            hint = "" if choice != "openai" else " (requires OPENAI_API_KEY env var)"
            return f"Model preference set to: {choice}{hint}"

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
        if self.pending_action and self.pending_action.get("type") == "permission_menu":
            self.pending_action = None
            return self._handle_permission_selection(trimmed)

        if trimmed in {"/permisions", "/permissions"}:
            self.pending_action = {"type": "permission_menu"}
            return PERMISSION_MENU
        if trimmed == "/web on":
            self.set_web_enabled(True)
            return "Web search enabled. I will use online sources when current docs, versions, or errors need verification."
        if trimmed == "/web off":
            self.set_web_enabled(False)
            return "Web search disabled. I will only use local files, cached docs, and built-in knowledge."
        if trimmed.startswith("/"):
            return "Only /permisions, /web, /model, and /theme are available. Just tell me what you want in normal chat."
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
        # Model selection & generation logic (local preferred unless user set otherwise)
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

        def try_remote():
            try:
                remote = RemoteModelRuntime()
                return remote.generate_text(prompt)
            except Exception:
                return ""

        generated = ""
        if model_pref == "local":
            generated = try_local()
            if not generated.strip():
                return "Local model selected but not available or generation failed.\n" + self._diagnose_local_model()
        elif model_pref == "openai":
            generated = try_remote()
            if not generated.strip():
                return "Remote model failed — check OPENAI_API_KEY or network connectivity."
        elif model_pref == "mock":
            generated = RemoteModelRuntime(api_key=None).generate_text(prompt)
        else:  # auto
            generated = try_local()
            if not generated.strip():
                generated = try_remote()
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
                lines.append(f"- {name}: {'exists' if path.exists() else 'MISSING'} ({path})")
        else:
            lines.append("No trained model found in known locations.")
            lines.append("Checked candidate locations:")
            for candidate in candidates:
                lines.append(f"- {candidate}:")
                artifacts = model_artifact_paths(candidate)
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
            response = self.respond(raw)
            self.persist_message("assistant", response)
            print(response, flush=True)
