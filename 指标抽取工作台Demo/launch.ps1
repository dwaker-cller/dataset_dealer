param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$demoRoot = $PSScriptRoot
$pythonExe = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$port = if ($env:GRID_DEMO_PORT) { $env:GRID_DEMO_PORT } else { '18864' }
$url = "http://127.0.0.1:$port"
$logRoot = Join-Path $demoRoot 'outputs'
function Test-Ready {
    try {
        $reply = Invoke-RestMethod -Uri "$url/api/defaults" -TimeoutSec 2
        return [bool]($reply.folder -and $reply.template -and $reply.owl)
    } catch { return $false }
}
try {
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Python runtime not found: $pythonExe" }
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    if (-not (Test-Ready)) {
        $serverId = & $pythonExe (Join-Path $demoRoot 'boot_server.py')
        if ($LASTEXITCODE -ne 0) { throw 'Unable to start local service.' }
        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if (Test-Ready) { $ready = $true; break }
            if (-not (Get-Process -Id ([int]$serverId) -ErrorAction SilentlyContinue)) { throw "Server exited. See outputs\server.stderr.log" }
            Start-Sleep -Milliseconds 500
        }
        if (-not $ready) { throw "Server did not become ready. See outputs\server.stderr.log" }
    }
    if (-not $NoBrowser) {
        $browserStart = New-Object System.Diagnostics.ProcessStartInfo
        $browserStart.FileName = $url
        $browserStart.UseShellExecute = $true
        [System.Diagnostics.Process]::Start($browserStart) | Out-Null
    }
    Write-Output "READY $url"
    exit 0
} catch {
    $message = $_.Exception.Message
    Write-Host "Launch failed: $message" -ForegroundColor Red
    if (Test-Path -LiteralPath $logRoot) { $message | Out-File -LiteralPath (Join-Path $logRoot 'launcher-error.log') -Encoding utf8 }
    exit 1
}
