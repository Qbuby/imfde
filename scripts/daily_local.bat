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

rem ---- 1.5 rebuild fde-public.db from fde.db (production data; fde.db is gitignored) ----
cd /d "%ROOT%"
"%PY%" scripts\build_public_db.py >> "%LOG%" 2>&1

rem ---- 2. pregen AI reports (needs AI_API_KEY) ----
rem 密钥放在 scriptsi_key.bat（已 gitignore），不要写回本文件
if "%AI_API_KEY%"=="" if exist "%~dp0ai_key.bat" call "%~dp0ai_key.bat"
set "AI_BASE_URL=https://api.deepseek.com/v1"
set "AI_MODEL=deepseek-flash"
if "%AI_API_KEY%"=="PASTE_MINIMAX_KEY_HERE" (
  echo [WARN] AI_API_KEY not configured - skip AI report pregen >> "%LOG%"
) else (
  cd /d "%ROOT%"
  "%PY%" scripts\pregen_ai.py >> "%LOG%" 2>&1
)

rem ---- 3. rebuild static pages + commit + push (Vercel auto-deploys) ----
cd /d "%ROOT%\portal"
"%PY%" build_static.py >> "%LOG%" 2>&1
cd /d "%ROOT%"
git add -A >> "%LOG%" 2>&1
if errorlevel 1 echo [ERROR] git add failed - check reserved names (nul) or locks >> "%LOG%"
git commit -m "daily data refresh %date% %time%" >> "%LOG%" 2>&1
if errorlevel 1 echo [WARN] git commit skipped or failed >> "%LOG%"
rem ---- 4. push 已恢复（2026-11-20 晚）----
rem 旧沙盘的 Cloudflare Git 集成已在面板断开，推送不再覆盖 imfde.ai。
rem 历史坑：曾因同名 Worker + Git 集成导致 push 覆盖线上新版，现已从根上断开。
git push origin main >> "%LOG%" 2>&1
if errorlevel 1 echo [ERROR] git push failed >> "%LOG%"

echo [%date% %time%] === daily update done === >> "%LOG%"
endlocal

