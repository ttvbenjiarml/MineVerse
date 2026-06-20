import { execSync } from 'node:child_process';
import fs from 'node:fs';

function run(cmd, opts = {}) {
  console.log(`> ${cmd}`);
  return execSync(cmd, { stdio: 'pipe', encoding: 'utf-8', ...opts });
}

try {
  const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
  let version = pkg.version;
  if (!version) throw new Error('package.json has no version');

  const prefix = 'v';
  const tagsRaw = run('git tag --list');
  const tags = tagsRaw.split(/\r?\n/).filter(Boolean);

  let [major, minor, patch] = version.split('.').map((v) => parseInt(v, 10));
  if ([major, minor, patch].some(isNaN)) {
    throw new Error('package.json version is not semver');
  }

  let candidate = `${prefix}${major}.${minor}.${patch}`;
  while (tags.includes(candidate)) {
    patch += 1;
    candidate = `${prefix}${major}.${minor}.${patch}`;
  }

  console.log('Creating tag', candidate);
  run(`git tag -a ${candidate} -m "Release ${candidate}"`, { stdio: 'inherit' });
  console.log('Pushing tag to origin');
  run(`git push origin ${candidate}`, { stdio: 'inherit' });

  console.log('Tag pushed:', candidate);
} catch (err) {
  console.error('Failed to create/push tag:', err.message || err);
  process.exit(1);
}
