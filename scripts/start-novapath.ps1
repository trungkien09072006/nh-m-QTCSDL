$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = (Get-Command python.exe -ErrorAction Stop).Source
$node = (Get-Command node.exe -ErrorAction Stop).Source
$viteRoot = Join-Path $repoRoot "vite_app"
$viteEntry = Join-Path $viteRoot "node_modules\vite\bin\vite.js"
$flaskEntry = Join-Path $repoRoot "06_web_app\app.py"
$startedProcesses = @()

function Test-PortOpen([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-ForEndpoint([string]$Url, [System.Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($Process -and $Process.HasExited) {
            throw "NovaPath server exited before becoming ready: $Url"
        }
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Timed out waiting for $Url"
}

function Find-Browser {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
        (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    foreach ($name in @("chrome.exe", "msedge.exe")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }
    throw "Install Google Chrome or Microsoft Edge to open the Vite app window."
}

try {
    if (-not (Test-Path $viteEntry)) {
        throw "Vite dependencies are missing. Run 'npm install --prefix .\vite_app' once, then retry."
    }
    if (-not (Test-Path $flaskEntry)) {
        throw "Flask entry point not found: $flaskEntry"
    }

    Set-Location $repoRoot
    if (-not $env:FLASK_SECRET_KEY) {
        $env:FLASK_SECRET_KEY = (& $python -c "import secrets; print(secrets.token_hex(32))").Trim()
    }

    $flaskProcess = $null
    if (-not (Test-PortOpen 5000)) {
        $flaskProcess = Start-Process `
            -FilePath $python `
            -ArgumentList @($flaskEntry) `
            -WorkingDirectory $repoRoot `
            -WindowStyle Hidden `
            -PassThru
        $startedProcesses += $flaskProcess
    }
    Wait-ForEndpoint "http://127.0.0.1:5000/login" $flaskProcess

    $viteProcess = $null
    if (-not (Test-PortOpen 5173)) {
        $viteProcess = Start-Process `
            -FilePath $node `
            -ArgumentList @($viteEntry, $viteRoot, "--host", "127.0.0.1", "--strictPort") `
            -WorkingDirectory $repoRoot `
            -WindowStyle Hidden `
            -PassThru
        $startedProcesses += $viteProcess
    }
    Wait-ForEndpoint "http://127.0.0.1:5173/" $viteProcess

    $browser = Find-Browser
    Start-Process -FilePath $browser -ArgumentList @("http://127.0.0.1:5000/login")
    Start-Process -FilePath $browser -ArgumentList @("--app=http://127.0.0.1:5173/")

    Write-Host "NovaPath web: http://127.0.0.1:5000/login"
    Write-Host "NovaPath app window: http://127.0.0.1:5173/"
    Write-Host "Both use the same Flask backend and SQL Server. Press Ctrl+C to stop servers started by this script."

    while ($true) {
        foreach ($process in $startedProcesses) {
            if ($process.HasExited) {
                throw "A NovaPath server process exited unexpectedly (PID $($process.Id))."
            }
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    foreach ($process in $startedProcesses) {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }
}
