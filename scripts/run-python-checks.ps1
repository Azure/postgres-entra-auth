param(
    [switch]$Verbose,
    [switch]$Help,
    [switch]$RecreateVenv
)

<#
.SYNOPSIS
  Run Python quality checks (lint, type, tests) locally.

.DESCRIPTION
  Mirrors the CI steps defined in pr-python.yml: install deps (.[all]), Ruff lint, mypy, and pytest.

.PARAMETER Verbose
  Show full tool output instead of suppressing it.

.PARAMETER RecreateVenv
  Delete and recreate the .venv before installing dependencies.

.EXAMPLE
  ./run-python-checks.ps1

.EXAMPLE
  ./run-python-checks.ps1 -Verbose

.EXAMPLE
  ./run-python-checks.ps1 -RecreateVenv
#>

if ($Help) {
    Get-Help -Detailed -ErrorAction SilentlyContinue
    Write-Host "Usage: ./run-python-checks.ps1 [-Verbose] [-RecreateVenv]" -ForegroundColor Cyan
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

# Find repository root (look for python/ directory up to 2 levels up)
$scriptDir = $PSScriptRoot
$repoRoot = $scriptDir
$pythonRoot = Join-Path $repoRoot "python"

if (-not (Test-Path $pythonRoot)) {
    $repoRoot = Split-Path $scriptDir -Parent
    $pythonRoot = Join-Path $repoRoot "python"
}

if (-not (Test-Path $pythonRoot)) {
    Write-Host "python/ directory not found. Run from repository root or scripts/ directory." -ForegroundColor Red
    exit 1
}

$venvPath   = Join-Path $pythonRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts/python.exe"

Push-Location $pythonRoot
try {
  # Use explicit parentheses so PowerShell doesn't mis-bind -and as a parameter to Test-Path on some shells
  if ((Test-Path $venvPath) -and $RecreateVenv) {
        Write-Host "Recreating virtual environment..." -ForegroundColor Blue
        Remove-Item -Recurse -Force $venvPath
    }
    if (-not (Test-Path $venvPath)) {
        Write-Host "Creating virtual environment" -ForegroundColor Blue
        python -m venv $venvPath
        if ($LASTEXITCODE -ne 0) { Write-CheckResult "Prepare venv" $false "python -m venv failed"; exit 1 }
        Write-CheckResult "Prepare venv" $true "Created new venv"
    } else {
        Write-CheckResult "Prepare venv" $true "Reused existing venv"
    }

    if (-not (Test-Path $venvPython)) { Write-CheckResult "Venv Python present" $false "Not found"; exit 1 }
    $pythonVersion = & $venvPython --version 2>&1
    Write-Host "Using $pythonVersion"

    & $venvPython -m pip install --upgrade pip | Out-Null
    Write-CheckResult "pip upgrade" ($LASTEXITCODE -eq 0)

    Write-Host "Installing project deps (.[all])" -ForegroundColor Blue
    & $venvPython -m pip install .[all] | Out-Null
    $depsOk = $LASTEXITCODE -eq 0
    if (-not $depsOk) { Write-CheckResult "Install deps" $false; exit 1 } else { Write-CheckResult "Install deps" $true }

    Write-Host "Installing build tool" -ForegroundColor Blue
    & $venvPython -m pip install build | Out-Null
    Write-CheckResult "Install build" ($LASTEXITCODE -eq 0)

    # Ruff
    Write-Host "Running Ruff lint" -ForegroundColor Blue
    if ($Verbose) { & $venvPython -m ruff check src tests } else { & $venvPython -m ruff check src tests *> $null }
    Write-CheckResult "ruff lint" ($LASTEXITCODE -eq 0)

    # mypy
    Write-Host "Running mypy type check" -ForegroundColor Blue
    if ($Verbose) { & $venvPython -m mypy src/azure_postgresql_auth/ } else { & $venvPython -m mypy src/azure_postgresql_auth/ *> $null }
    Write-CheckResult "mypy" ($LASTEXITCODE -eq 0)

    if (Test-Path "tests") {
        Write-Host "Running pytest" -ForegroundColor Blue
        
        # Create test results directory
        $testResultsDir = "test-results"
        if (-not (Test-Path $testResultsDir)) {
            New-Item -ItemType Directory -Path $testResultsDir | Out-Null
        }
        
        # Use importlib mode to avoid import collisions from files with same basename
        # This allows pytest to handle multiple test_entra_id_extension.py files
        if ($Verbose) { 
            & $venvPython -m pytest tests --import-mode=importlib -v --junit-xml="$testResultsDir/test-results.xml"
        } else { 
            & $venvPython -m pytest tests --import-mode=importlib -q --junit-xml="$testResultsDir/test-results.xml" *> $null 
        }
        $allTestsPass = ($LASTEXITCODE -eq 0)
        Write-CheckResult "pytest" $allTestsPass
    } else {
        Write-Host "WARN No tests directory present" -ForegroundColor Yellow
    }

    # Build package
    Write-Host "Building package" -ForegroundColor Blue
    $distDir = "dist"
    if (Test-Path $distDir) {
        Remove-Item -Recurse -Force $distDir
    }
    if ($Verbose) { 
        & $venvPython -m build 
    } else { 
        & $venvPython -m build *> $null 
    }
    $buildOk = ($LASTEXITCODE -eq 0)
    Write-CheckResult "build package" $buildOk
}
finally {
    Pop-Location
}

if (-not $OverallSuccess) { exit 1 }

# Display output locations
Write-Host ""
Write-Host "Output locations:" -ForegroundColor Cyan
$testResults = Join-Path $pythonRoot "test-results"
$distPath = Join-Path $pythonRoot "dist"
if (Test-Path $testResults) {
    Write-Host "  Test results: $(Resolve-Path $testResults)" -ForegroundColor Gray
}
if (Test-Path $distPath) {
    Write-Host "  Package: $(Resolve-Path $distPath)" -ForegroundColor Gray
}
