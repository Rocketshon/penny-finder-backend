@echo off
REM Full weekly pipeline — run from the Dell so the briefing published to
REM GitHub Pages includes the data sources that only exist locally:
REM   - circulars/walmart.html  (Walmart __NEXT_DATA__ via Playwright)
REM   - circulars/*.pdf         (weekly-ad PDFs dropped by hand or cron)
REM
REM Task Scheduler setup (one-time):
REM   1. taskschd.msc
REM   2. Create Basic Task: Penny Finder - Weekly Publish
REM   3. Trigger: Weekly, Sunday 6:00 AM
REM   4. Action: Start a program
REM        Program: %~dp0run_local_pipeline.bat
REM        Start in: %USERPROFILE%\Projects\PennyHunter\penny-finder-backend

setlocal
cd /d "%~dp0.."

echo [%DATE% %TIME%] Fetching Walmart Flash Deals...
python scripts\fetch_walmart.py
if errorlevel 1 echo   (Walmart fetch skipped/failed — continuing)

echo [%DATE% %TIME%] Running backend pipeline...
python -m main
if errorlevel 1 (
  echo   ERROR: pipeline failed, aborting
  exit /b 1
)

echo [%DATE% %TIME%] Publishing to pages branch...
git checkout --orphan pages-tmp
git --work-tree=out add --all
git --work-tree=out commit -m "local briefing %DATE% %TIME%" || (
  echo   no changes to publish
  git checkout main
  exit /b 0
)
git push --force origin pages-tmp:pages
git checkout main

echo [%DATE% %TIME%] Done.
endlocal
