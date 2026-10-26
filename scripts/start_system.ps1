[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendPath = Join-Path $projectRoot 'frontend'
$nodeModulesPath = Join-Path $frontendPath 'node_modules'
$backendUrl = 'http://127.0.0.1:8001'
$frontendUrl = 'http://127.0.0.1:5173'
$startedProcesses = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

function Write-Step([string]$Message) {
    Write-Host "[启动] $Message" -ForegroundColor Cyan
}

function Test-BackendHealthy {
    try {
        $health = Invoke-RestMethod "$backendUrl/api/health" -TimeoutSec 2
        return $health.status -eq 'ok'
    } catch {
        return $false
    }
}

function Test-BackendReady {
    if (-not (Test-BackendHealthy)) { return $false }
    try {
        $openApi = Invoke-RestMethod "$backendUrl/openapi.json" -TimeoutSec 2
        $requiredRoute = '/api/children/{child_id}/overview'
        return $openApi.paths.PSObject.Properties.Name -contains $requiredRoute
    } catch {
        return $false
    }
}

function Test-FrontendReady {
    try {
        $response = Invoke-WebRequest $frontendUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-PortOwner([int]$Port) {
    $netstatPath = Join-Path $env:SystemRoot 'System32\netstat.exe'
    $pattern = "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$"
    $match = & $netstatPath -ano -p tcp 2>$null |
        Select-String -Pattern $pattern |
        Select-Object -First 1
    if (-not $match -or $match.Matches.Count -eq 0) { return $null }

    $processId = [int]$match.Matches[0].Groups[1].Value
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    $name = if ($process) { $process.ProcessName } else { '未知进程' }
    return "PID $processId（$name）"
}

function Assert-PortAvailable([int]$Port, [bool]$ServiceReady, [string]$ServiceName) {
    if ($ServiceReady) { return }
    $owner = Get-PortOwner $Port
    if ($owner) {
        throw "$ServiceName 端口 $Port 已被 $owner 占用，但该服务未通过健康检查。请关闭占用程序后重试。"
    }
}

function Stop-StartedProcesses {
    foreach ($process in $startedProcesses) {
        if ($process -and -not $process.HasExited) {
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
        }
    }
}

try {
    Set-Location $projectRoot

    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        throw 'Python 虚拟环境不存在，请先双击 setup.bat 完成初始化。'
    }
    if (-not (Test-Path -LiteralPath $nodeModulesPath -PathType Container)) {
        throw '前端依赖不存在，请先双击 setup.bat 完成初始化。'
    }
    if (-not (Get-Command 'npm.cmd' -ErrorAction SilentlyContinue)) {
        throw '未找到 npm，请安装 Node.js 后重新运行 setup.bat。'
    }

    Write-Step '检查视频分析模型'
    & $pythonPath (Join-Path $projectRoot 'scripts\check_models.py') --quick *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning '视频模型尚未就绪；档案、观察和家庭互动等功能仍可使用。可运行 scripts\download_models.py 修复视频分析。'
    }

    $backendHealthy = Test-BackendHealthy
    $backendReady = Test-BackendReady
    $frontendReady = Test-FrontendReady
    if ($backendHealthy -and -not $backendReady) {
        $owner = Get-PortOwner 8001
        throw "检测到旧版后端仍在运行（$owner）。请关闭旧后端窗口，再重新双击 run.bat。"
    }
    Assert-PortAvailable -Port 8001 -ServiceReady $backendReady -ServiceName '后端'
    Assert-PortAvailable -Port 5173 -ServiceReady $frontendReady -ServiceName '前端'

    if ($backendReady) {
        Write-Host '[复用] 后端服务已在运行。' -ForegroundColor DarkGreen
    } else {
        Write-Step '启动后端服务'
        $backendCommand = 'title Autism System Backend && "{0}" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --no-access-log' -f $pythonPath
        $backendProcess = Start-Process -FilePath $env:ComSpec -ArgumentList '/k', $backendCommand `
            -WorkingDirectory $projectRoot -WindowStyle Minimized -PassThru
        $startedProcesses.Add($backendProcess)
    }

    if ($frontendReady) {
        Write-Host '[复用] 前端服务已在运行。' -ForegroundColor DarkGreen
    } else {
        Write-Step '启动前端服务'
        $frontendCommand = 'title Autism System Frontend && npm.cmd run dev'
        $frontendProcess = Start-Process -FilePath $env:ComSpec -ArgumentList '/k', $frontendCommand `
            -WorkingDirectory $frontendPath -WindowStyle Minimized -PassThru
        $startedProcesses.Add($frontendProcess)
    }

    Write-Step '等待前后端健康检查（最长 30 秒）'
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        if (-not $backendReady) { $backendReady = Test-BackendReady }
        if (-not $frontendReady) { $frontendReady = Test-FrontendReady }
        if ($backendReady -and $frontendReady) { break }
        Start-Sleep -Milliseconds 500
    }

    if (-not $backendReady) { throw '后端未能在 30 秒内启动，请查看后端窗口中的错误信息。' }
    if (-not $frontendReady) { throw '前端未能在 30 秒内启动，请查看前端窗口中的错误信息。' }

    Write-Host ''
    Write-Host '[成功] 系统已就绪' -ForegroundColor Green
    Write-Host "  系统地址：$frontendUrl"
    Write-Host "  接口文档：$backendUrl/docs"

    if (-not $NoBrowser -and $env:AUTISM_SYSTEM_NO_BROWSER -ne '1') {
        Start-Process $frontendUrl
    }
    exit 0
} catch {
    Stop-StartedProcesses
    Write-Host ''
    Write-Host "[失败] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
