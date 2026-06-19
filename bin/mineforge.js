#!/usr/bin/env node

import { main } from "../lib-node/cli-core.js";

main(process.argv.slice(2)).catch((error) => {
  console.error("MineForgeAI failed to start.");
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
