@echo off
cd /d "%~dp0"
echo Starting J.A.R.V.I.S Mobile Bridge on port 8765...
"C:\Users\HP\.gemini\antigravity\scratch\JARVIS\.venv\Scripts\python.exe" bridge_server.py
pause
