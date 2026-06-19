import os from "node:os";
import path from "node:path";

export function getPlatformInfo() {
  return {
    os: process.platform,
    arch: process.arch,
    isWindows: process.platform === "win32",
    isMac: process.platform === "darwin",
    isLinux: process.platform === "linux"
  };
}

export function getUserDataDir() {
  const home = os.homedir();
  if (process.platform === "win32") {
    return path.join(process.env.LOCALAPPDATA || path.join(home, "AppData", "Local"), "MineForgeAI");
  }
  if (process.platform === "darwin") {
    return path.join(home, "Library", "Application Support", "MineForgeAI");
  }
  return path.join(process.env.XDG_DATA_HOME || path.join(home, ".local", "share"), "mineforgeai");
}

export function getCacheDir() {
  const home = os.homedir();
  if (process.platform === "win32") {
    return path.join(process.env.LOCALAPPDATA || path.join(home, "AppData", "Local"), "MineForgeAI", "cache");
  }
  if (process.platform === "darwin") {
    return path.join(home, "Library", "Caches", "MineForgeAI");
  }
  return path.join(process.env.XDG_CACHE_HOME || path.join(home, ".cache"), "mineforgeai");
}

export function getWorkspaceRoot(cwd = process.cwd()) {
  return cwd;
}
