@echo off
rem imfde 每日数据更新（本地计划任务调用）：抓取 → 预生成报告 → 提交推送
chcp 65001 >nul
cd /d "%~dp0.."

set "PY=C:\Users\14798\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"

echo [%date% %time%] 开始每日更新 >> daily_update.log

rem ---- 1. 抓取最新数据写入 fde.db ----
cd portal
"%PY%" ingest_world.py --daily >> ..\daily_update.log 2>&1
cd ..

rem ---- 2. 预生成解读报告（含 AI 调用，需要 AI_API_KEY 环境变量或本脚本内联） ----
if "%AI_API_KEY%"=="" set "AI_API_KEY=sk-1HMYi1KWNnjWV9TzDQ83aBzp63DOpuWwlq2ALuRMIV1uWAzu"
set "AI_BASE_URL=https://api.airy.work/v1"
set "AI_MODEL=gpt-5.6-luna"
"%PY%" scripts\pregen_ai.py >> daily_update.log 2>&1

rem ---- 3. 重新导出静态页 + 提交推送（Vercel 自动部署） ----
cd portal
"%PY%" build_static.py >> ..\daily_update.log 2>&1
cd ..
git add -A
git commit -m "daily data refresh %date% %time%" >> daily_update.log 2>&1
git push origin main >> daily_update.log 2>&1

echo [%date% %time%] 每日更新完成 >> daily_update.log
