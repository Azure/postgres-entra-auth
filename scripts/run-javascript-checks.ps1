#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run JavaScript quality checks locally before pushing to GitHub.

.DESCRIPTION
    This script mirrors the pr-javascript.yml workflow, running:
    - ESLint (linting)

.PARAMETER SkipInstall
    Skip npm install step (useful if dependencies are already installed)

.EXAMPLE
    .\run-javascript-checks.ps1
    Run all checks with npm install

.EXAMPLE
    .\run-javascript-checks.ps1 -SkipInstall
    Run all checks without installing dependencies
#>

param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $PSScriptRoot
$javascriptDir = Join-Path $scriptRoot "javascript"

# Track overall success
$allChecksPassed = $true

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "JavaScript Quality Checks" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to javascript directory
Push-Location $javascriptDir

try {
    # Install dependencies
    if (-not $SkipInstall) {
        Write-Host "[1/2] Installing dependencies..." -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host "X Dependency installation failed" -ForegroundColor Red
            $allChecksPassed = $false
            throw "npm install failed"
        }
        Write-Host "OK Dependencies installed" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host "[Skipped] npm install" -ForegroundColor Gray
        Write-Host ""
    }

    # ESLint
    Write-Host "[2/2] Running ESLint..." -ForegroundColor Yellow
    npm run lint
    if ($LASTEXITCODE -ne 0) {
        Write-Host "X ESLint failed" -ForegroundColor Red
        $allChecksPassed = $false
    } else {
        Write-Host "OK ESLint passed" -ForegroundColor Green
        Write-Host ""
    }

    # Final summary
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    if ($allChecksPassed) {
        Write-Host "OK All checks passed!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        exit 0
    } else {
        Write-Host "X Some checks failed" -ForegroundColor Red
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        exit 1
    }
} finally {
    Pop-Location
}
