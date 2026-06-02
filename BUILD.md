# Building the CardWatcher executable

The standalone `.exe` is built with PyInstaller. To keep the binary small and
predictable we use a **whitelist** approach: build inside a clean virtualenv that
contains **only** the packages CardWatcher actually needs (listed in
[requirements.txt](requirements.txt)).

PyInstaller bundles whatever it can reach through imports. If you build from a
Python that also has unrelated packages installed (e.g. `torch`, `scipy`,
`pandas`, `transformers`), PyInstaller follows transitive/optional imports into
them and the exe balloons — a real build hit ~346 MB this way, exceeding
GitHub's 100 MB file limit. A clean build env physically cannot bundle what is
not installed, so it stays around ~30 MB without any `excludes` blacklist.

## One-time: create the build venv

```powershell
py -3.12 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install --upgrade pip
.\.venv-build\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
```

`.venv-build/` is gitignored.

## Build

```powershell
.\.venv-build\Scripts\pyinstaller.exe cardwatcher.spec
```

The exe is written to `dist/CardWatcher.exe` (~30 MB). It expects the
`cardwatcher-data/` directory as a sibling, containing `pages/`, `archive/`,
`images/`, and `changes/`.

## When you add a new dependency

Add it to `requirements.txt`, then reinstall it into the build venv before
rebuilding:

```powershell
.\.venv-build\Scripts\python.exe -m pip install -r requirements.txt
```

Do **not** add real dependencies only as PyInstaller `hiddenimports` — the
whitelist in `requirements.txt` is the single source of truth for what gets
bundled.
