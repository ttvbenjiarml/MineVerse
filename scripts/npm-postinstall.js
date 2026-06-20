import path from 'node:path';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';

function run(cmd, args, opts = {}) {
  console.log(`\n> ${[cmd, ...args].join(' ')}\n`);
  const res = spawnSync(cmd, args, { stdio: 'inherit', ...opts });
  if (res.error) {
    throw res.error;
  }
  if (res.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} exited with code ${res.status}`);
  }
  return res;
}

function findPython() {
  const candidates = process.platform === 'win32' ? [['py', ['-3']], ['python', []], ['python3', []]] : [['python3', []], ['python', []]];
  for (const [cmd, args] of candidates) {
    try {
      const out = spawnSync(cmd, [...args, '--version'], { stdio: 'pipe' });
      if (out.status === 0) return { cmd, args };
    } catch (e) {}
  }
  return null;
}

async function main() {
  try {
    const repoRoot = process.cwd();
    const pyRoot = path.join(repoRoot, 'python-backend');
    if (!fs.existsSync(pyRoot)) {
      console.log('No python-backend folder found, skipping Python venv setup.');
      return;
    }

    const found = findPython();
    if (!found) {
      console.log('Python 3 not found on PATH. Skipping venv creation.');
      console.log('You can set up the Python runtime manually: see README.md');
      return;
    }
    const pythonCmd = found.cmd; const pythonArgs = found.args || [];

    const venvDir = path.join(pyRoot, '.venv');
    if (!fs.existsSync(venvDir)) {
      // create venv
      run(pythonCmd, [...pythonArgs, '-m', 'venv', venvDir]);
    } else {
      console.log('Python venv already exists at', venvDir);
    }

    const isWindows = process.platform === 'win32';
    const venvPython = isWindows ? path.join(venvDir, 'Scripts', 'python.exe') : path.join(venvDir, 'bin', 'python');
    if (!fs.existsSync(venvPython)) {
      console.log('Could not find python executable inside venv:', venvPython);
      console.log('You may need to run the installer manually.');
      return;
    }

    // upgrade pip
    run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip']);

    // install requirements
    const reqFile = path.join(pyRoot, 'requirements-cpu.txt');
    if (fs.existsSync(reqFile)) {
      run(venvPython, ['-m', 'pip', 'install', '-r', reqFile]);
    } else {
      console.log('No requirements-cpu.txt found; skipping dependency install.');
    }

    // install backend package editable
    run(venvPython, ['-m', 'pip', 'install', '-e', pyRoot]);

    console.log('\nMineForgeAI: Python runtime prepared in', venvDir);
    console.log('You can now run the CLI with `mineforge` (after global npm install) or:');
    console.log('  node bin/mineforge.js');
  } catch (err) {
    console.error('Postinstall helper failed:', err);
    console.error('Please run the install steps manually as described in README.md');
  }
}

main();
