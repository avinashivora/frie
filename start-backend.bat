@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo FRIE backend environment not found at backend\.venv.
  echo Complete the first-time setup steps before starting the backend.
  exit /b 1
)

cd /d "%~dp0backend"

"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

