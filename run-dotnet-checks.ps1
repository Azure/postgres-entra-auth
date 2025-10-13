param(
    [string]$Configuration = "Release",
    [switch]$Verbose,
    [switch]$Help
)

<#
.SYNOPSIS
  Run .NET quality checks (restore, build, test) locally.

.DESCRIPTION
  Mirrors the CI steps in pr-dotnet.yml for confidence before pushing.

.PARAMETER Configuration
  Build configuration (Release or Debug). Defaults to Release to match CI.

.PARAMETER Verbose
  Show full command output (otherwise minimal).

.EXAMPLE
  ./run-dotnet-checks.ps1

.EXAMPLE
  ./run-dotnet-checks.ps1 -Configuration Debug
#>

if ($Help) {
    Get-Help -Detailed -ErrorAction SilentlyContinue
    Write-Host "Usage: ./run-dotnet-checks.ps1 [-Configuration Release|Debug] [-Verbose]" -ForegroundColor Cyan
    exit 0
}

function Write-CheckResult {
    param([string]$Name, [bool]$Success, [string]$Message = "")
    if ($Success) {
        Write-Host "PASS  $Name" -ForegroundColor Green
        if ($Message) { Write-Host "  $Message" -ForegroundColor Gray }
    } else {
        Write-Host "FAIL  $Name" -ForegroundColor Red
        if ($Message) { Write-Host "  $Message" -ForegroundColor Gray }
        $script:OverallSuccess = $false
    }
}

$OverallSuccess = $true
$dotnetRoot = Join-Path (Get-Location) "dotnet"
if (-not (Test-Path $dotnetRoot)) {
    Write-Host "dotnet/ directory not found" -ForegroundColor Red
    exit 1
}

Push-Location $dotnetRoot
try {
    if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
        Write-Host ".NET SDK not found in PATH" -ForegroundColor Red
        exit 1
    }

    $sdkVersion = dotnet --version
    Write-Host "Using .NET SDK $sdkVersion (Configuration=$Configuration)"

    Write-Host "Restoring packages" -ForegroundColor Blue
    if ($Verbose) { dotnet restore } else { dotnet restore --verbosity minimal }
    Write-CheckResult "restore" ($LASTEXITCODE -eq 0)

    Write-Host "Building solution" -ForegroundColor Blue
    if ($Verbose) { dotnet build --no-restore --configuration $Configuration } else { dotnet build --no-restore --configuration $Configuration --verbosity minimal }
    Write-CheckResult "build" ($LASTEXITCODE -eq 0)

    Write-Host "Running tests" -ForegroundColor Blue
    if ($Verbose) { dotnet test --no-build --configuration $Configuration --verbosity normal } else { dotnet test --no-build --configuration $Configuration --verbosity minimal }
    Write-CheckResult "test" ($LASTEXITCODE -eq 0)
}
finally {
    Pop-Location
}

if (-not $OverallSuccess) { exit 1 }
