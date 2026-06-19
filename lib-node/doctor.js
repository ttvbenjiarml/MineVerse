export function repairInstructions() {
  return [
    "Check that Node.js 20+ is installed.",
    "Check that python, python3, or py -3 is available.",
    "If PyTorch install fails, rerun with CPU requirements first.",
    "Confirm the workspace path is writable and inside your project folder."
  ].join("\n");
}
