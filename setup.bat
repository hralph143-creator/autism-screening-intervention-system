@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONUTF8=1
pushd "%~dp0"
echo [1/9] 检查 Python 版本...
python -c "import sys; assert sys.version_info.major == 3 and sys.version_info.minor in (11,12), '需要 Python 3.11 或 3.12'; print(sys.version)" || goto :fail
echo [2/9] 检查 Node.js 与 npm...
node --version || goto :fail
call npm --version || goto :fail
echo [3/9] 创建 Python 虚拟环境...
if not exist ".venv\Scripts\python.exe" python -m venv ".venv" || goto :fail
echo [4/9] 安装后端依赖...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :fail
call ".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt" || goto :fail
echo [5/9] 安装前端依赖...
call npm --prefix "frontend" install || goto :fail
echo [6/9] 下载并真实加载验证 MediaPipe 官方模型...
call ".venv\Scripts\python.exe" "scripts\download_models.py" || goto :fail
echo [7/9] 初始化 SQLite 数据库并执行增量迁移...
call ".venv\Scripts\python.exe" -m scripts.init_db || goto :fail
echo [8/9] 检查安装结果...
call ".venv\Scripts\python.exe" -m pip check || goto :fail
call npm --prefix "frontend" run typecheck || goto :fail
echo [9/9] 检查数据库与模型状态...
call ".venv\Scripts\python.exe" "scripts\check_database.py" || goto :fail
call ".venv\Scripts\python.exe" "scripts\check_models.py" || goto :fail
echo.
echo 初始化成功。请双击 run.bat 启动系统。
popd
pause
exit /b 0
:fail
echo.
echo 初始化失败，请根据上方错误信息修复后重新运行 setup.bat。
popd
pause
exit /b 1
