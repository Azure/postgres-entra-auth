param(
    [switch]$Verbose,
    [switch]$Help,
    [switch]$RecreateVenv
)

<#
.SYNOPSIS
  Run Python quality checks (lint, type, tests) locally.

.DESCRIPTION
  Mirrors the CI steps defined in pr-python.yml: install deps (.[all]), Ruff lint, mypy (target + package), pytest, and import validation.

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
$pythonRoot = Join-Path (Get-Location) "python"
if (-not (Test-Path $pythonRoot)) {
    Write-Host "python/ directory not found" -ForegroundColor Red
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

    Write-Host "Installing project deps (editable .[all])" -ForegroundColor Blue
    & $venvPython -m pip install -e .[all] | Out-Null
    $depsOk = $LASTEXITCODE -eq 0
    if (-not $depsOk) { Write-CheckResult "Install deps" $false; exit 1 } else { Write-CheckResult "Install deps" $true }

    & $venvPython -m pip install types-psycopg2 aiohttp | Out-Null
    Write-CheckResult "Extra deps (types-psycopg2,aiohttp)" ($LASTEXITCODE -eq 0)

    # Ruff
    Write-Host "Running Ruff lint" -ForegroundColor Blue
    if ($Verbose) { & $venvPython -m ruff check ./src ./tests } else { & $venvPython -m ruff check ./src ./tests *> $null }
    Write-CheckResult "ruff lint" ($LASTEXITCODE -eq 0)

    # mypy target
    if ($Verbose) { & $venvPython -m mypy ./src/azurepg_entra/psycopg2/psycopg2_entra_id_extension.py } else { & $venvPython -m mypy ./src/azurepg_entra/psycopg2/psycopg2_entra_id_extension.py *> $null }
    Write-CheckResult "mypy (target)" ($LASTEXITCODE -eq 0)

    # mypy all
    if ($Verbose) { & $venvPython -m mypy ./src/azurepg_entra/ } else { & $venvPython -m mypy ./src/azurepg_entra/ *> $null }
    Write-CheckResult "mypy (all)" ($LASTEXITCODE -eq 0)

    if (Test-Path "tests") {
        Write-Host "Running pytest" -ForegroundColor Blue
        
        # Run tests for each subdirectory separately to avoid import collisions
        $testDirs = @(
            "tests/azure/data/postgresql/psycopg2",
            "tests/azure/data/postgresql/psycopg3", 
            "tests/azure/data/postgresql/sqlalchemy",
            "tests/azure/data/postgresql/test_core_functionality.py"
        )
        
        $allTestsPass = $true
        foreach ($testDir in $testDirs) {
            if (Test-Path $testDir) {
                Write-Host "  Testing $testDir" -ForegroundColor Gray
                if ($Verbose) { 
                    & $venvPython -m pytest $testDir -v 
                } else { 
                    & $venvPython -m pytest $testDir -q *> $null 
                }
                if ($LASTEXITCODE -ne 0) { $allTestsPass = $false }
            }
        }
        Write-CheckResult "pytest" $allTestsPass
    } else {
        Write-Host "WARN No tests directory present" -ForegroundColor Yellow
    }

    & $venvPython -c "import sys; sys.path.insert(0, 'src'); import azurepg_entra, azurepg_entra.core" 2>$null
    Write-CheckResult "Import validation" ($LASTEXITCODE -eq 0)
}
finally {
    Pop-Location
}

if (-not $OverallSuccess) { exit 1 }
