@echo off
setlocal

cd /d "%~dp0"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  mingding.spec

if errorlevel 1 (
  echo.
  echo 打包失败。
  exit /b 1
)

echo.
echo 打包完成：dist\mingding\mingding.exe
echo 注意：config.json 会生成在 mingding.exe 旁边，整个 dist\mingding 目录一起拷贝。
endlocal
