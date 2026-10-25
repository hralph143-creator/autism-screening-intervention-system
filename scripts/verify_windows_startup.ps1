$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backendPort = 8001
$frontendPort = 5173

if (Get-NetTCPConnection -State Listen -LocalPort $backendPort, $frontendPort -ErrorAction SilentlyContinue) {
    throw '端口 8001 或 5173 已被占用，无法进行隔离启动验收。'
}

$backend = $null
$frontend = $null
try {
    $backend = Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') `
        -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8001','--no-access-log' `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru
    $frontend = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev','--','--host','127.0.0.1' `
        -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden -PassThru

    $backendReady = $false
    $frontendReady = $false
    foreach ($attempt in 1..30) {
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8001/api/health' -TimeoutSec 1
            $backendReady = $health.status -eq 'ok'
        } catch {}
        try {
            $response = Invoke-WebRequest 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 1
            $frontendReady = $response.StatusCode -eq 200
        } catch {}
        if ($backendReady -and $frontendReady) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $backendReady) { throw '后端未能在限定时间内通过健康检查。' }
    if (-not $frontendReady) { throw '前端未能在限定时间内返回页面。' }
    Write-Output '[成功] 后端 8001 健康检查通过'
    Write-Output '[成功] 前端 5173 页面访问通过'
} finally {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $backendPort, $frontendPort -ErrorAction SilentlyContinue
    $processIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($backend) { $processIds += $backend.Id }
    if ($frontend) { $processIds += $frontend.Id }
    $processIds | Where-Object { $_ -gt 0 } | Select-Object -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
}
