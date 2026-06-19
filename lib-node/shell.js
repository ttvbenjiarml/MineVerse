const DANGEROUS_PATTERNS = [
  /rm\s+-rf\s+\/?$/i,
  /rm\s+-rf\s+\*/i,
  /del\s+\/s/i,
  /format(\s|$)/i,
  /diskpart/i,
  /shutdown/i,
  /reboot/i,
  /mkfs/i,
  /dd\s+if=/i,
  /curl.+\|\s*sh/i,
  /wget.+\|\s*sh/i
];

export function isDangerousCommand(command) {
  return DANGEROUS_PATTERNS.some((pattern) => pattern.test(command));
}

export function getShellCommand(command, platform = process.platform) {
  if (platform === "win32") {
    return { executable: "cmd.exe", args: ["/d", "/s", "/c", command] };
  }
  return { executable: "/bin/sh", args: ["-lc", command] };
}
