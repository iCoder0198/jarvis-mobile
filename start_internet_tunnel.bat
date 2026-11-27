@echo off
cd /d "%~dp0"
echo Starting J.A.R.V.I.S Mobile Bridge + HTTPS Internet Tunnel...
"C:\Users\HP\.gemini\antigravity\scratch\JARVIS\.venv\Scripts\python.exe" start_internet_tunnel.py
pause
