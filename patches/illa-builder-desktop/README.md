# ILLA Builder desktop promotion bundle

Applies the Cam-staged Electron shell into `afidurko/illa-builder` as `electron/`, pinned to **electron-builder@26.16.1**.

## Preferred (agent)

```bash
export ILLA_BUILDER_GITHUB_TOKEN=ghp_...   # Contents + Pull requests on afidurko/illa-builder
python3 scripts/promote-illa-desktop.py --push
```

## Manual

```bash
git clone -b beta https://github.com/afidurko/illa-builder.git
cd illa-builder
git checkout -b cursor/desktop-electron-26-16-1
git am ../Personal-Assistant/patches/illa-builder-desktop/0001-*.patch
# or: tar xzf .../electron.tgz && merge root-scripts.json into package.json
git push -u origin cursor/desktop-electron-26-16-1
```

Open PR: `beta` ← `cursor/desktop-electron-26-16-1`
