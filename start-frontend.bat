@echo off
setlocal
cd /d "%~dp0"

if not exist "node_modules\.bin\vite.cmd" (
  echo Frontend dependencies are not installed.
  echo Run npm install once before starting the frontend.
  exit /b 1
)

call npm run dev -- --host localhost --port 5173 --strictPort

