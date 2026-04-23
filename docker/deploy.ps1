param(
    [switch]$Down,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"

$dockerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $dockerDir
$appEnv = Join-Path $dockerDir "app.env"
$appEnvExample = Join-Path $dockerDir "app.env.example"

function Ensure-EnvFile {
    param(
        [string]$TargetPath,
        [string]$ExamplePath
    )

    if (-not (Test-Path $TargetPath)) {
        Copy-Item -LiteralPath $ExamplePath -Destination $TargetPath
        Write-Host "Generated $(Split-Path -Leaf $TargetPath). Update passwords before public deployment."
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker command not found. Please install Docker Desktop or Docker Engine first."
}

Ensure-EnvFile -TargetPath $appEnv -ExamplePath $appEnvExample

Push-Location $projectRoot
try {
    if ($Down) {
        docker compose down
        exit $LASTEXITCODE
    }

    if ($Logs) {
        docker compose logs -f app
        exit $LASTEXITCODE
    }

    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    Write-Host ""
    Write-Host "Deployment completed."
    Write-Host "API docs: http://127.0.0.1:8000/docs"
    Write-Host "View logs: .\\docker\\deploy.ps1 -Logs"
    Write-Host "Stop services: .\\docker\\deploy.ps1 -Down"
}
finally {
    Pop-Location
}
