import fs from "node:fs/promises";
import path from "node:path";

export const PERMISSION_MENU = `MineForgeAI Permissions

Choose how much control the AI has in this folder:

1. See Edits
   - AI can inspect files.
   - AI can suggest changes.
   - AI shows diffs.
   - AI cannot write files.
   - AI cannot run commands.

2. Ask Before Actions
   - AI can inspect files.
   - AI can prepare edits.
   - AI asks before writing files.
   - AI asks before running commands.
   - Recommended default.

3. Full Access
   - AI can edit files in this workspace.
   - AI can create files/folders.
   - AI can run normal build/test/dev commands.
   - AI still cannot escape the workspace.
   - AI still blocks dangerous system commands.
   - AI still protects secrets and system folders.

4. Custom
   - Choose exactly what the AI can do.

Select 1, 2, 3, or 4:`;

export function defaultCustomPermissions() {
  return {
    read_files: true,
    write_files: false,
    create_files: false,
    delete_files: "ask",
    run_commands: "ask",
    install_dependencies: "ask",
    use_web: false,
    allow_outside_workspace: false,
    show_diffs_before_edit: true
  };
}

export function resolvePermissionMode(choice) {
  switch (String(choice).trim()) {
    case "1":
      return { mode: "see_edits" };
    case "2":
      return { mode: "ask_before_actions" };
    case "3":
      return { mode: "full_access" };
    case "4":
      return { mode: "custom", custom: defaultCustomPermissions() };
    default:
      return { mode: "ask_before_actions" };
  }
}

export function canWrite(permission) {
  return permission.mode === "full_access" || (permission.mode === "custom" && permission.custom?.write_files === true);
}

export function canRunCommands(permission) {
  return permission.mode === "full_access" || permission.mode === "ask_before_actions" || ["on", "ask"].includes(permission.custom?.run_commands);
}

export function requiresConfirmationForWrite(permission) {
  return permission.mode === "ask_before_actions" || (permission.mode === "custom" && permission.custom?.write_files !== true);
}

export function requiresConfirmationForCommand(permission) {
  return permission.mode === "ask_before_actions" || (permission.mode === "custom" && permission.custom?.run_commands === "ask");
}

export async function loadWorkspacePermissions(workspace) {
  const file = path.join(workspace, ".mineforgeai", "permissions.json");
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return { mode: "ask_before_actions" };
  }
}

export async function saveWorkspacePermissions(workspace, permission) {
  const dir = path.join(workspace, ".mineforgeai");
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(path.join(dir, "permissions.json"), JSON.stringify(permission, null, 2));
}
