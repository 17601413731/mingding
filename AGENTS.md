# Repository Guidelines

## Project Structure & Module Organization

`mingding.py` is the application entry point. `window.py` and `widgets.py` implement the PySide6 interface; `theme.py` holds shared visual constants. `engine.py` owns screen capture, card detection, and key input, while `config.py` loads and validates settings. Regression tests live in `tests/`, with image fixtures in `assets/`. `tools/` contains calibration, icon, and release helpers. `legacy/` preserves the pre-refactor implementations; make active changes in the root modules.

## Build, Test, and Development Commands

Run these from the repository root on Windows. Install the runtime packages with `python -m pip install PySide6 opencv-python numpy dxcam keyboard pydirectinput`; the repository has no dependency manifest. Use `python mingding.py --ui-only` to inspect the UI without starting capture or hotkeys, or `python mingding.py --screenshot out.png` to render it to a file. `python mingding.py` runs the full app and may need administrator rights for game input. `python -m unittest discover -s tests` runs all tests. `build_mingding.bat` packages the app with PyInstaller using `mingding.spec`; install PyInstaller first. The distributable is the entire `dist\mingding\` directory.

## Coding Style & Naming Conventions

Follow the existing Python style: four-space indentation, `snake_case` functions and modules, `PascalCase` classes, and uppercase constants. Keep detection and input behavior in `engine.py`; communicate with the UI through the existing callback and Qt signal boundary. Put shared UI colors, fonts, and spacing in `theme.py`. No formatter or linter is configured, so keep edits consistent with nearby code.

## Testing Guidelines

Tests use the standard-library `unittest` framework. Name new files `test_*.py` and methods `test_*`. Add detection regressions against `assets/` images in `tests/test_detect.py`; add configuration cases in `tests/test_config.py` using temporary paths, never a contributor's `config.json`. There is no stated coverage threshold. After changing `mingding.spec`, also launch `dist\mingding\mingding.exe` to catch runtime packaging errors.

## Commits, Pull Requests & Configuration

Recent commits use `feat:` and `chore:` prefixes followed by concise descriptions; follow that pattern and choose a prefix matching the change. In pull requests, describe behavior changes, list the test command and result, and include a screenshot for UI changes. Keep `config.json`, `build/`, and `dist/` out of commits; they are ignored local settings and generated output. Update `.github/release-notes.md` when preparing a release.
