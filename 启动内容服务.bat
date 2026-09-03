@echo off
rem imfde.ai 本地开发启动：内容服务(Python :8850) + 打开静态门户
chcp 65001 >nul
cd /d "%~dp0"

rem ---- Python 解释器（优先用托管版，回退系统 python）----
set "PY=C:\Users\14798\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"

echo ============================================
echo   imfde.ai 内容服务 (学习社区 / world / cases)
echo   http://127.0.0.1:8850/
echo ============================================

rem 通过环境变量告诉内容服务"返回门户"的地址（本地开发用静态页地址）
set "IMFDE_PORTAL_URL=http://127.0.0.1:8850/index.html"

rem 在默认浏览器打开内容服务首页
start "" "http://127.0.0.1:8850/"

cd /d "%~dp0portal\site"
"%PY%" server.py
