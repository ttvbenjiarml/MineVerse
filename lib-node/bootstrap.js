import path from "node:path";
import { getPlatformInfo } from "./platform.js";
import { candidatePythonCommands, backendEntry, resolvePythonRuntime } from "./python.js";

export function bootstrapPlan(repoRoot, workspace) {
  const platform = getPlatformInfo();
  return {
    platform,
    workspace,
    repoRoot,
    pythonCandidates: candidatePythonCommands(platform.isWindows),
    backendScript: backendEntry(repoRoot),
    venvDir: path.join(repoRoot, "python-backend", ".venv")
  };
}

export async function prepareBackendRuntime(repoRoot, workspace) {
  const plan = bootstrapPlan(repoRoot, workspace);
  const python = await resolvePythonRuntime(repoRoot);
  return {
    ...plan,
    python
  };
}
