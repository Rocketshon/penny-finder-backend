@echo off
REM Windows Task Scheduler wrapper for fetch_walmart.py.
REM Schedule this .bat to run weekly (e.g. Sundays 5:30 AM) so the Flash
REM Deals HTML in circulars/walmart.html stays fresh for the backend
REM pipeline to parse.
REM
REM Task Scheduler setup (one-time):
REM   1. Run taskschd.msc
REM   2. Create Basic Task:
REM        Name: Penny Finder - Fetch Walmart
REM        Trigger: Weekly, Sunday 5:30 AM
REM        Action: Start a program
REM        Program: %USERPROFILE%\Projects\PennyHunter\penny-finder-backend\scripts\fetch_walmart.bat
REM        Start in: %USERPROFILE%\Projects\PennyHunter\penny-finder-backend

setlocal
cd /d "%~dp0.."
python scripts\fetch_walmart.py
endlocal
