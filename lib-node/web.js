import fs from "node:fs/promises";
import path from "node:path";

export async function setWebEnabled(workspace, enabled) {
  const dir = path.join(workspace, ".mineforgeai");
  await fs.mkdir(dir, { recursive: true });
  const file = path.join(dir, "memory.json");
  let data = {};
  try {
    data = JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    data = {};
  }
  data.web_enabled = enabled;
  await fs.writeFile(file, JSON.stringify(data, null, 2));
}

export async function getWebEnabled(workspace) {
  try {
    const data = JSON.parse(await fs.readFile(path.join(workspace, ".mineforgeai", "memory.json"), "utf8"));
    return data.web_enabled === true;
  } catch {
    return false;
  }
}

export function webDisabledMessage() {
  return "Web search is off. Type /web on to allow online research.";
}

export function webEnabledMessage() {
  return "Web search enabled. I will use online sources when current docs, versions, or errors need verification.";
}

export function webOffMessage() {
  return "Web search disabled. I will only use local files, cached docs, and built-in knowledge.";
}
