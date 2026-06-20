import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const REQUIRED_MODEL_FILES = ["model.pt", "tokenizer.json", "model_config.json"];

function packageRoot() {
  return path.dirname(path.dirname(fileURLToPath(import.meta.url)));
}

function packageMetadata() {
  try {
    return JSON.parse(fs.readFileSync(path.join(packageRoot(), "package.json"), "utf8"));
  } catch {
    return {};
  }
}

function run(cmd, args, opts = {}) {
  console.log(`\n> ${[cmd, ...args].join(" ")}\n`);
  const res = spawnSync(cmd, args, { stdio: "inherit", ...opts });
  if (res.error) {
    throw res.error;
  }
  if (res.status !== 0) {
    throw new Error(`${cmd} ${args.join(" ")} exited with code ${res.status}`);
  }
  return res;
}

function findPython() {
  const candidates = process.platform === "win32" ? [["py", ["-3"]], ["python", []], ["python3", []]] : [["python3", []], ["python", []]];
  for (const [cmd, args] of candidates) {
    const out = spawnSync(cmd, [...args, "--version"], { stdio: "pipe" });
    if (out.status === 0) {
      return { cmd, args };
    }
  }
  return null;
}

function modelRoot() {
  const home = os.homedir();
  if (process.platform === "win32") {
    return path.join(process.env.LOCALAPPDATA || path.join(home, "AppData", "Local"), "MineForgeAI", "models", "latest");
  }
  if (process.platform === "darwin") {
    return path.join(home, "Library", "Application Support", "MineForgeAI", "models", "latest");
  }
  return path.join(process.env.XDG_DATA_HOME || path.join(home, ".local", "share"), "mineforgeai", "models", "latest");
}

function requiredModelFilesPresent(dir) {
  return REQUIRED_MODEL_FILES.every((file) => fs.existsSync(path.join(dir, file)) && fs.statSync(path.join(dir, file)).size > 0);
}

function modelSource() {
  const pkg = packageMetadata();
  const configured = typeof pkg.config?.mineforge_model_url === "string" ? pkg.config.mineforge_model_url.trim() : "";
  const inferred = inferGithubModelUrl(pkg.repository?.url || pkg.repository || "");
  return (
    process.env.MINEFORGE_MODEL_URL ||
    process.env.npm_config_mineforge_model_url ||
    process.env.npm_package_config_mineforge_model_url ||
    configured ||
    inferred ||
    ""
  ).trim();
}

function inferGithubModelUrl(repository) {
  const value = String(repository || "").replace(/^git\+/, "").replace(/\.git$/, "");
  const match = value.match(/github\.com[:/]+([^/\s]+)\/([^/\s#?]+)/i);
  if (!match) {
    return "";
  }
  return `https://github.com/${match[1]}/${match[2]}/releases/latest/download/mineforge_model_latest.zip`;
}

function download(url, outputPath, redirects = 0) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith("https:") ? https : http;
    const req = client.get(url, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode || 0) && res.headers.location && redirects < 5) {
        res.resume();
        const next = new URL(res.headers.location, url).toString();
        download(next, outputPath, redirects + 1).then(resolve, reject);
        return;
      }
      if ((res.statusCode || 0) >= 400) {
        res.resume();
        reject(new Error(`Download failed with HTTP ${res.statusCode}`));
        return;
      }
      const file = fs.createWriteStream(outputPath);
      res.pipe(file);
      file.on("finish", () => file.close(resolve));
      file.on("error", reject);
    });
    req.on("error", reject);
  });
}

function copyRequiredFiles(sourceDir, destinationDir) {
  const queue = [sourceDir];
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) {
      continue;
    }
    if (requiredModelFilesPresent(current)) {
      fs.mkdirSync(destinationDir, { recursive: true });
      for (const file of REQUIRED_MODEL_FILES) {
        fs.copyFileSync(path.join(current, file), path.join(destinationDir, file));
      }
      const statePath = path.join(current, "state.json");
      if (fs.existsSync(statePath)) {
        fs.copyFileSync(statePath, path.join(destinationDir, "state.json"));
      }
      return true;
    }
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        queue.push(path.join(current, entry.name));
      }
    }
  }
  return false;
}

function validateModelJson(dir) {
  for (const file of ["tokenizer.json", "model_config.json"]) {
    JSON.parse(fs.readFileSync(path.join(dir, file), "utf8"));
  }
}

async function installModelIfConfigured(venvPython) {
  const destination = modelRoot();
  if (requiredModelFilesPresent(destination)) {
    console.log(`MineForgeAI: model already installed at ${destination}`);
    return;
  }

  const source = modelSource();
  if (!source) {
    console.log("MineForgeAI: no model URL configured; CLI will use deterministic tools and remote/local settings.");
    console.log("To install a model during npm install, set MINEFORGE_MODEL_URL.");
    return;
  }

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mineforge-model-"));
  try {
    let sourcePath = source;
    if (/^https?:\/\//i.test(source)) {
      sourcePath = path.join(tempDir, "model-download");
      console.log(`MineForgeAI: downloading model from ${source}`);
      await download(source, sourcePath);
    }

    const stat = fs.statSync(sourcePath);
    if (stat.isDirectory()) {
      if (!copyRequiredFiles(sourcePath, destination)) {
        throw new Error(`No complete model artifact set found in ${sourcePath}`);
      }
    } else if (sourcePath.toLowerCase().endsWith(".zip") || source.startsWith("http")) {
      const extractDir = path.join(tempDir, "extract");
      fs.mkdirSync(extractDir, { recursive: true });
      run(venvPython, ["-c", "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])", sourcePath, extractDir]);
      if (!copyRequiredFiles(extractDir, destination)) {
        throw new Error("Model archive must contain model.pt, tokenizer.json, and model_config.json");
      }
    } else {
      throw new Error("Model source must be a folder or a .zip archive");
    }

    validateModelJson(destination);
    console.log(`MineForgeAI: model installed at ${destination}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.log(`MineForgeAI: model install failed: ${message}`);
    console.log("MineForgeAI: continuing without a local model; add the release asset or set MINEFORGE_MODEL_URL and reinstall.");
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

async function main() {
  try {
    const repoRoot = packageRoot();
    const pyRoot = path.join(repoRoot, "python-backend");
    if (!fs.existsSync(pyRoot)) {
      console.log("No python-backend folder found, skipping Python venv setup.");
      return;
    }

    const found = findPython();
    if (!found) {
      console.log("Python 3 not found on PATH. Skipping venv creation.");
      console.log("Install Python 3.10+ and rerun `npm install -g mineforge`.");
      return;
    }

    const venvDir = path.join(pyRoot, ".venv");
    if (!fs.existsSync(venvDir)) {
      run(found.cmd, [...found.args, "-m", "venv", venvDir]);
    } else {
      console.log("Python venv already exists at", venvDir);
    }

    const venvPython = process.platform === "win32" ? path.join(venvDir, "Scripts", "python.exe") : path.join(venvDir, "bin", "python");
    if (!fs.existsSync(venvPython)) {
      console.log("Could not find python executable inside venv:", venvPython);
      return;
    }

    run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"]);
    const reqFile = path.join(pyRoot, "requirements-cpu.txt");
    if (fs.existsSync(reqFile)) {
      run(venvPython, ["-m", "pip", "install", "-r", reqFile]);
    }
    run(venvPython, ["-m", "pip", "install", pyRoot]);

    await installModelIfConfigured(venvPython);

    console.log("\nMineForgeAI: install complete.");
    console.log("Run the CLI with `mineforge`.");
  } catch (err) {
    console.error("MineForgeAI postinstall helper failed:", err);
    console.error("The CLI can still be installed; rerun install or see README.md for manual setup.");
  }
}

main();
