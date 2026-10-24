@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONUTF8=1
pushd "%~dp0"
echo ===== 系统环境检查 =====
python --version >nul 2>&1 && (echo [成功] Python 可用 & python --version) || echo [失败] Python 不可用
node --version >nul 2>&1 && (echo [成功] Node.js 可用 & node --version) || echo [失败] Node.js 不可用
call npm --version >nul 2>&1 && (echo [成功] npm 可用 & call npm --version) || echo [失败] npm 不可用
if exist ".venv\Scripts\python.exe" (echo [成功] Python 虚拟环境存在) else echo [失败] Python 虚拟环境不存在
if exist ".venv\Scripts\python.exe" call ".venv\Scripts\python.exe" -c "import fastapi,uvicorn,sqlalchemy,pydantic; print('[成功] 后端核心依赖可导入')" 2>nul || echo [失败] 后端核心依赖不完整
if exist "frontend\node_modules" (call npm --prefix "frontend" list --depth=0 >nul 2>&1 && echo [成功] 前端依赖完整 || echo [失败] 前端依赖存在异常) else echo [失败] 前端依赖不存在
if exist "data\app.db" (echo [成功] 数据库文件存在) else echo [失败] 数据库文件不存在
if exist ".venv\Scripts\python.exe" call ".venv\Scripts\python.exe" -m scripts.check_database 2>nul || echo [失败] 数据库连接或基础表异常
powershell -NoProfile -Command "try { $r=Invoke-RestMethod 'http://127.0.0.1:8001/api/health' -TimeoutSec 2; if($r.status -eq 'ok'){'[成功] 后端接口可访问'}else{'[失败] 后端响应异常'} } catch {'[提示] 后端服务当前未启动'}"
powershell -NoProfile -Command "try { Invoke-WebRequest 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2 | Out-Null; '[成功] 前端服务可访问' } catch {'[提示] 前端服务当前未启动'}"
echo ============================
popd
pause

