@echo off
rem imfde.ai 本地一体化启动：静态门户(http.server :8080) + 内容服务(python :8850)
chcp 65001 >nul
cd /d "%~dp0"

rem ---- Python 解释器（优先托管版，回退系统 python）----
set "PY=C:\Users\14798\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PY%" set "PY=python"

echo ==========================================================
echo   imfde.ai 本地开发
echo   静态门户  http://127.0.0.1:8080/index.html
echo   内容服务  http://127.0.0.1:8850/  (世界动态/案例/方法/world3d)
echo ==========================================================

rem 静态门户：把整个 imfde 项目根目录作为站点根，供相对链接/资源访问
start "" "http://127.0.0.1:8080/index.html"
start "imfde-http" "%PY%" -m http.server 8080 --directory "%~dp0"

rem 内容服务：返回门户指向静态门户地址
set "IMFDE_PORTAL_URL=http://127.0.0.1:8080/index.html"
cd /d "%~dp0portal\site"
"%PY%" server.py
