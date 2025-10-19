#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run Java quality checks locally before pushing to GitHub.

.DESCRIPTION
    This script runs the same checks as the pr-java.yml GitHub Actions workflow:
    - Maven compile
    - Spotless format check

.EXAMPLE
    .\run-java-checks.ps1
#>

# Set error action preference to stop on any error
$ErrorActionPreference = "Stop"

# Get the script directory and navigate to the Java project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$javaProjectDir = Join-Path $repoRoot "java\entra-id-authentication"

# Check if the Java project directory exists
if (-not (Test-Path $javaProjectDir)) {
    Write-Error "Java project directory not found at: $javaProjectDir"
    exit 1
}

# Navigate to the Java project directory
Write-Host "Navigating to Java project directory: $javaProjectDir" -ForegroundColor Cyan
Push-Location $javaProjectDir

# Function to print section headers
function Write-SectionHeader {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Yellow
    Write-Host $Message -ForegroundColor Yellow
    Write-Host "========================================`n" -ForegroundColor Yellow
}

# Function to check exit code and exit if failed
function Test-ExitCode {
    param(
        [string]$StepName,
        [int]$ExitCode
    )
    if ($ExitCode -ne 0) {
        Write-Host "`n$StepName FAILED with exit code $ExitCode" -ForegroundColor Red
        exit $ExitCode
    } else {
        Write-Host "`n$StepName PASSED" -ForegroundColor Green
    }
}

# Step 1: Compile Java code
Write-SectionHeader "Step 1: Compiling Java code"
mvn clean compile
Test-ExitCode "Maven Compile" $LASTEXITCODE

# Step 2: Run Spotless format check
Write-SectionHeader "Step 2: Running Spotless format check"
Write-Host "Checking code formatting (4-space indentation, no trailing whitespace)..." -ForegroundColor Cyan
mvn spotless:check
Test-ExitCode "Spotless Format Check" $LASTEXITCODE

# All checks passed
Write-Host "`n" -NoNewline
Write-Host "========================================" -ForegroundColor Green
Write-Host "ALL CHECKS PASSED!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nYour code is ready to push to GitHub!" -ForegroundColor Green
Write-Host "`nTip: If you need to fix formatting issues, run:" -ForegroundColor Cyan
Write-Host "  mvn spotless:apply" -ForegroundColor White

# Return to the original directory
Pop-Location

exit 0
