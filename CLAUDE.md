# Translation Launcher

A Windows desktop launcher for Hebrew game-translation mods. Built with
**Eel** (Python ↔ Chromium bridge), a React + Vite frontend, and packaged
as a standalone installer via PyInstaller + Inno Setup.

The launcher fetches a games catalog from the public translation hub
API, displays available titles, downloads the matching translation
archive, and copies it into the game's mod folder.

---

## Repository layout

| Path | Purpose |
|---|---|
| `main_eel.py` | Eel entry point. Spawns the Chromium window and exposes the Python bridge functions consumed by the frontend. |
| `translation_manager/` | Python application package — UI views, asset/download logic, game detection, theme, paths, SWR cache. |
| `frontend/` | React + Vite UI rendered inside the Eel window. Build output is bundled into the executable. |
| `build_assets/` | Installer artwork (icon, wizard BMPs, store screenshots) used by Inno Setup + PyInstaller. |
| `build_exe.bat` | One-shot build script: builds the frontend, runs PyInstaller, then Inno Setup. |
| `TranslationManager.spec` | PyInstaller spec — declares hidden imports, data files, icon, and console behaviour. |

---

## Dev setup

Prerequisites: **Python 3.11+**, **Node 20+**, **Windows 10/11**.

```bash
# Python deps (run from the repo root)
python -m venv .venv
.venv\Scripts\activate
pip install -r translation_manager/requirements.txt

# Frontend deps
cd frontend
npm install
```

---

## Running locally

```bash
# Terminal 1 — frontend dev server (HMR)
cd frontend
npm run dev

# Terminal 2 — Eel host (Python)
python main_eel.py
```

For a one-shot production-mode launch (frontend already built into
`frontend/dist/`):

```bash
cd frontend && npm run build && cd ..
python main_eel.py
```

---

## Building the installer

`build_exe.bat` is the canonical end-to-end build:

1. `npm run build` inside `frontend/` — produces `frontend/dist/`.
2. `pyinstaller TranslationManager.spec` — bundles Python + frontend
   into `dist/TranslationManager/`.
3. Inno Setup compiles the installer into `Output/TranslationManager-Setup-<version>.exe`.

Latest signed builds: see
[Releases](https://github.com/nehorayc04/translation-launcher/releases).

---

## Frontend build flags

| Command | Description |
|---|---|
| `npm run dev` | Vite dev server with HMR on `localhost:5173`. |
| `npm run build` | Type-checks + emits production bundle to `frontend/dist/`. |
| `npm run preview` | Serves the built bundle to validate before bundling. |

---

## License

See repository for license terms.
