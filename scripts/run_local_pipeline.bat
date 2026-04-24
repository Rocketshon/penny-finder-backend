@echo off
REM Full weekly pipeline - run from the Dell so the briefing published to
REM GitHub Pages includes the data sources that only exist locally:
REM   circulars/walmart.html  (Walmart NEXT_DATA via Playwright)
REM   circulars/*.pdf         (weekly-ad PDFs dropped by hand or cron)
REM
REM Task Scheduler setup (one-time):
REM   taskschd.msc
REM   Create Basic Task: Penny Finder - Weekly Publish
REM   Trigger: Weekly, Sunday 6:00 AM
REM   Action: Start a program
REM     Program: run_local_pipeline.bat (in this scripts folder)
REM     Start in: penny-finder-backend root

setlocal
cd /d "%~dp0.."

echo [%DATE% %TIME%] Fetching Walmart Flash Deals...
python scripts\fetch_walmart.py
if errorlevel 1 echo   Walmart fetch skipped or failed - continuing

echo [%DATE% %TIME%] Running backend pipeline...
python -m main
if errorlevel 1 (
  echo   ERROR: pipeline failed, aborting
  exit /b 1
)

echo [%DATE% %TIME%] Publishing to pages branch...

REM Stash any untracked working-tree state so checkout doesnt fail.
git stash push --include-untracked -m "run_local_pipeline-autostash" >nul 2>&1

git checkout --orphan pages-tmp
git --work-tree=out reset --mixed >nul 2>&1
git --work-tree=out add --all
git --work-tree=out commit -m "local briefing %DATE% %TIME%"
if errorlevel 1 (
  echo   no changes to publish
  git checkout -f main
  git stash pop >nul 2>&1
  exit /b 0
)

git push --force origin pages-tmp:pages

git checkout -f main
git branch -D pages-tmp >nul 2>&1
git stash pop >nul 2>&1

echo [%DATE% %TIME%] Done.
endlocal
