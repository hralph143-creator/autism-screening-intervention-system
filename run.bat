@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONUTF8=1
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo [失败] Python 虚拟环境不存在，请先运行 setup.bat。& goto :fail)
if not exist "frontend\node_modules" (echo [失败] 前端依赖不存在，请先运行 setup.bat。& goto :fail)
netstat -ano | findstr /R /C:":8001 .*LISTENING" >nul && (echo [失败] 后端端口 8001 已被占用。& goto :fail)
netstat -ano | findstr /R /C:":5173 .*LISTENING" >nul && (echo [失败] 前端端口 5173 已被占用。& goto :fail)
echo 正在启动后端服务...
start "自闭症筛查系统-后端" "%ComSpec%" /k ""%CD%\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --no-access-log"
echo 正在启动前端服务...
start "自闭症筛查系统-前端" "%ComSpec%" /k "cd /d ""%CD%\frontend"" && npm run dev"
echo 正在验证服务是否真正可用...
powershell -NoProfile -Command "$ok=$false; 1..20 | ForEach-Object { try { $r=Invoke-RestMethod 'http://127.0.0.1:8001/api/health' -TimeoutSec 1; if($r.status -eq 'ok'){$ok=$true;break} } catch {}; Start-Sleep -Milliseconds 500 }; if(-not $ok){exit 1}" || (echo [失败] 后端未能在 10 秒内启动，请查看后端窗口。& goto :fail)
powershell -NoProfile -Command "$ok=$false; 1..20 | ForEach-Object { try { Invoke-WebRequest 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 1 | Out-Null; $ok=$true; break } catch {}; Start-Sleep -Milliseconds 500 }; if(-not $ok){exit 1}" || (echo [失败] 前端未能在 10 秒内启动，请查看前端窗口。& goto :fail)
echo [成功] 前后端服务均已验证。
start "" "http://127.0.0.1:5173"
popd
exit /b 0
:fail
popd
pause
exit /b 1

