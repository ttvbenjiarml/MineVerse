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
from mineforgeai.model.checkpointing import find_trained_model_dir
from mineforgeai.model.runtime import load_local_model
from mineforgeai.training.trainer import write_training_plan


def startup_text(workspace: Path, model_label: str, has_model: bool, permission_label: str = "Ask Before Actions", web_enabled: bool = False) -> str:
    profile = detect_hardware()
    virtual_window = recommended_virtual_context_window(profile)
    vm_status = "on" if profile.virtual_memory_enabled else "off"
    mode = model_label if has_model else "fallback tool mode"
    tail = "Local trained model detected and ready." if has_model else "No trained local model was found. I can still help using templates, project analysis, web research if enabled, and deterministic Minecraft tools. I can also train a local model when you ask."
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
        self.local_model = load_local_model(workspace) if has_model else None
        self.context.load_summary(self._load_latest_summary())

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
        print(question, flush=True)
        answer = input().strip().lower()
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
        summary.append(f"Resolved target version: {compatibility.resolved_version}.")
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
            return "Only /permisions and /web on/off are available. Just tell me what you want in normal chat."
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
        if self.local_model is not None:
            prompt = self._build_model_prompt(text)
            try:
                generated = self.local_model.generate_text(prompt, profile=self.local_model.preferred_profile)
            except Exception:
                generated = ""
            if generated.strip():
                return generated.strip()
        return (
            "I can help with Minecraft plugins, mods, datapacks, resource packs, Gradle fixes, logs, and version compatibility. "
            "Tell me what you want to build or fix, for example: `make a minecraft plugin for paper 1.21.1 that adds a custom sword with VFX`."
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

    def run(self) -> int:
        onboarding = self.maybe_onboard_permissions()
        print(startup_text(self.workspace, self.model_label, self.has_model, self.permission_label(), self.is_web_enabled()), flush=True)
        if onboarding:
            print(onboarding, flush=True)
        while True:
            try:
                raw = input("mineforge > ")
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
