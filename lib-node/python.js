import path from "node:path";
import fs from "node:fs/promises";
import { spawn } from "node:child_process";

export function candidatePythonCommands(isWindows = process.platform === "win32") {
  return isWindows ? [["py", ["-3"]], ["python", []], ["python3", []]] : [["python3", []], ["python", []]];
}

export function backendEntry(repoRoot) {
  return path.join(repoRoot, "python-backend", "mineforgeai", "main.py");
}

export function venvPythonPath(repoRoot, isWindows = process.platform === "win32") {
  return isWindows
    ? path.join(repoRoot, "python-backend", ".venv", "Scripts", "python.exe")
    : path.join(repoRoot, "python-backend", ".venv", "bin", "python");
}

function runVersionCheck(command, args, workdir) {
  return new Promise((resolve) => {
    const child = spawn(command, [...args, "--version"], {
      cwd: workdir,
      stdio: ["ignore", "pipe", "pipe"],
      shell: false
    });
    let output = "";
    child.stdout.on("data", (chunk) => {
      output += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      output += chunk.toString();
    });
    child.on("error", () => resolve(null));
    child.on("close", (code) => {
      resolve(code === 0 ? { command, args, version: output.trim() } : null);
    });
  });
}

export async function resolvePythonRuntime(repoRoot) {
  const isWindows = process.platform === "win32";
  const venvPython = venvPythonPath(repoRoot, isWindows);
  try {
    await fs.access(venvPython);
    const checked = await runVersionCheck(venvPython, [], repoRoot);
    if (checked) {
      return checked;
    }
  } catch {
  }

  for (const [command, args] of candidatePythonCommands(isWindows)) {
    const checked = await runVersionCheck(command, args, repoRoot);
    if (checked) {
      return checked;
    }
  }
  throw new Error("Python 3 was not found. Install python, python3, or py -3 and try again.");
}
