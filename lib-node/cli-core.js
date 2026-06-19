import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { prepareBackendRuntime } from "./bootstrap.js";
import { loadWorkspacePermissions, PERMISSION_MENU } from "./permissions.js";
import { getWebEnabled, setWebEnabled, webDisabledMessage, webEnabledMessage, webOffMessage } from "./web.js";

const INVALID_SLASH_MESSAGE = "Only /permisions and /web on/off are available. Just tell me what you want in normal chat.";

export function getStartupBanner({ workspace, permissionsLabel, webEnabled, hasModel }) {
  return [
    "MineForgeAI Omniverse",
    "",
    `Workspace: ${workspace}`,
    `Model: ${hasModel ? "local" : "fallback tool mode"}`,
    `Permissions: ${permissionsLabel}`,
    `Web: ${webEnabled ? "on" : "off"}`,
    "Context: auto-compacting",
    "Commands: /permisions, /web on, /web off",
    "",
    "Just tell me what you want to build or fix.",
    "mineforge >"
  ].join("\n");
}

export function parseSlashCommand(input) {
  const trimmed = input.trim();
  if (!trimmed.startsWith("/")) {
    return { type: "chat", text: input };
  }
  if (trimmed === "/permisions" || trimmed === "/permissions") {
    return { type: "permissions" };
  }
  if (trimmed === "/web on") {
    return { type: "web_on" };
  }
  if (trimmed === "/web off") {
    return { type: "web_off" };
  }
  return { type: "invalid", text: INVALID_SLASH_MESSAGE };
}

export async function handleInput(input, workspace) {
  const command = parseSlashCommand(input);
  if (command.type === "permissions") {
    return PERMISSION_MENU;
  }
  if (command.type === "web_on") {
    await setWebEnabled(workspace, true);
    return webEnabledMessage();
  }
  if (command.type === "web_off") {
    await setWebEnabled(workspace, false);
    return webOffMessage();
  }
  if (command.type === "invalid") {
    return command.text;
  }
  if (/search online/i.test(input) && !(await getWebEnabled(workspace))) {
    return webDisabledMessage();
  }
  return "Natural-language task accepted. Backend routing will inspect the request and choose planning, generation, review, testing, or research steps.";
}

export async function main() {
  const repoRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
  const workspace = process.cwd();
  const permissions = await loadWorkspacePermissions(workspace);
  const webEnabled = await getWebEnabled(workspace);
  const runtime = await prepareBackendRuntime(repoRoot, workspace);
  const pythonBackendRoot = path.join(repoRoot, "python-backend");
  const pythonPath = [pythonBackendRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  const env = {
    ...process.env,
    MINEFORGE_WORKSPACE: workspace,
    MINEFORGE_PERMISSION_MODE: permissions.mode,
    MINEFORGE_WEB_ENABLED: webEnabled ? "1" : "0",
    PYTHONPATH: pythonPath
  };
  const child = spawn(runtime.python.command, [...runtime.python.args, runtime.backendScript, "--workspace", workspace, "--mode", "chatbot", "--interactive"], {
    cwd: repoRoot,
    stdio: "inherit",
    shell: false,
    env
  });
  await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", (code) => {
      if (typeof code === "number" && code !== 0) {
        reject(new Error(`MineForgeAI backend exited with code ${code}.`));
      } else {
        resolve();
      }
    });
  });
}

export { INVALID_SLASH_MESSAGE };
