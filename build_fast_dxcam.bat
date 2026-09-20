@echo off
setlocal

cd /d "%~dp0"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name kapai_fast_dxcam ^
  --hidden-import dxcam ^
  --hidden-import keyboard ^
  --hidden-import pydirectinput ^
  main_fast_dxcam.py

if errorlevel 1 (
  echo.
  echo Build failed.
  exit /b 1
)

echo.
echo Build complete: dist\kapai_fast_dxcam.exe
endlocal
