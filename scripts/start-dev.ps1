param(
    [int]$Port = 8000,
    [string]$HostAddress = "127.0.0.1",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $ProjectRoot "logs"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-PortInUse {
    param([int]$TargetPort)

    $connection = Get-NetTCPConnection -LocalAddress $HostAddress -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1

    return $null -ne $connection
}

function Find-FreePort {
    $candidate = $Port
    while (Test-PortInUse -TargetPort $candidate) {
        $candidate++
    }

    return $candidate
}

function Wait-ForHealth {
    param([int]$TargetPort)

    $deadline = (Get-Date).AddSeconds(25)
    $healthUrl = "http://$HostAddress`:$TargetPort/health"

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }

    throw "Dev server did not pass /health within 25 seconds."
}

$ActualPort = Find-FreePort
$StdOutLog = Join-Path $LogDir "dev-server-$ActualPort.out.log"
$StdErrLog = Join-Path $LogDir "dev-server-$ActualPort.err.log"
$PidFile = Join-Path $LogDir "dev-server-$ActualPort.pid"
$InfoFile = Join-Path $LogDir "dev-server-$ActualPort.info.txt"

$arguments = @(
    "-m",
    "uvicorn",
    "app.main:app",
    "--reload",
    "--host",
    $HostAddress,
    "--port",
    "$ActualPort"
)

$server = Start-Process `
    -FilePath $Python `
    -ArgumentList $arguments `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError $StdErrLog `
    -WindowStyle Hidden `
    -PassThru

$server.Id | Set-Content -Encoding ASCII -Path $PidFile

Wait-ForHealth -TargetPort $ActualPort

$summary = @(
    "Dev server ready: http://$HostAddress`:$ActualPort/",
    "ProcessId: $($server.Id)",
    "Stdout: $StdOutLog",
    "Stderr: $StdErrLog",
    "PidFile: $PidFile"
)

$summary | Set-Content -Encoding UTF8 -Path $InfoFile
$summary | Write-Output
