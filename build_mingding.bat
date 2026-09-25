@echo off
setlocal

cd /d "%~dp0"

python -m PyInstaller --noconfirm --clean mingding.spec

if errorlevel 1 exit /b 1

echo Build complete: dist\mingding\mingding.exe
echo Copy the entire dist\mingding directory; config.json is created next to the exe.
endlocal
