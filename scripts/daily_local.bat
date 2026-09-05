@echo off
rem imfde daily local job: ingest -> pregen AI reports -> build -> push
rem ASCII-only + CRLF required for cmd.exe. Do not add non-ASCII comments.
setlocal
chcp 437 >nul

set "ROOT=D:\program\imfde"
set "PY=C:\Users\14798\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"

set "LOG=%ROOT%\daily_update.log"
echo [%date% %time%] === daily update start === >> "%LOG%"

rem ---- 1. ingest latest data into fde.db ----
cd /d "%ROOT%\portal"
"%PY%" ingest_world.py --daily >> "%LOG%" 2>&1

rem ---- 2. pregen AI reports (needs AI_API_KEY) ----
if "%AI_API_KEY%"=="" set "AI_API_KEY=sk-1HMYi1KWNnjWV9TzDQ83aBzp63DOpuWwlq2ALuRMIV1uWAzu"
set "AI_BASE_URL=https://api.airy.work/v1"
set "AI_MODEL=gpt-5.6-luna"
cd /d "%ROOT%"
"%PY%" scripts\pregen_ai.py >> "%LOG%" 2>&1

rem ---- 3. rebuild static pages + commit + push (Vercel auto-deploys) ----
cd /d "%ROOT%\portal"
"%PY%" build_static.py >> "%LOG%" 2>&1
cd /d "%ROOT%"
git add -A >> "%LOG%" 2>&1
git commit -m "daily data refresh %date% %time%" >> "%LOG%" 2>&1
git push origin main >> "%LOG%" 2>&1

echo [%date% %time%] === daily update done === >> "%LOG%"
endlocal

