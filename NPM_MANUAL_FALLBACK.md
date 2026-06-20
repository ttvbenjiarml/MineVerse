# MineForge npm Fallback

Use this only if `publish_npm_local.bat` fails.

## Install the CLI

Users install MineForge with:

```powershell
npm install -g mineforge@latest
```

After installing, run:

```powershell
mineforge
```

If npm says `No matching version found` for the latest version, wait a minute and refresh npm's cache:

```powershell
npm cache verify
npm install -g mineforge@latest
```

If npm shows an `allow-scripts` warning after install, approve MineForge's install script:

```powershell
npm approve-scripts mineforge
```

## Publish MineForge manually

Run these in this project folder:

```powershell
npm whoami
npm ci
npm run build
npm version patch --no-git-tag-version
npm pack --dry-run
npm publish --access public
npm view mineforge version
```

If `npm whoami` fails, log in first:

```powershell
npm login
```

If normal login fails:

```powershell
npm login --auth-type=legacy
```

## Version choice

For a bug fix:

```powershell
npm version patch --no-git-tag-version
```

For a new feature:

```powershell
npm version minor --no-git-tag-version
```

For a breaking change:

```powershell
npm version major --no-git-tag-version
```

npm will not let you publish the same version twice.
