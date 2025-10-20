#!/usr/bin/env pwsh
# Script to run .NET checks locally before pushing to GitHub
# This mirrors the logic in .github/workflows/pr-dotnet.yml

param(
    [string]$Configuration = "Release",
    [string[]]$DotNetVersions = @("8.0", "9.0")
)

$ErrorActionPreference = "Stop"
$OriginalLocation = Get-Location

try {
    # Determine the correct path to the dotnet directory
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $repoRoot = Split-Path -Parent $scriptDir
    $dotnetDir = Join-Path $repoRoot "dotnet"
    
    if (-not (Test-Path $dotnetDir)) {
        throw "Cannot find dotnet directory at: $dotnetDir"
    }
    
    # Change to dotnet directory
    Set-Location $dotnetDir
    
    Write-Host "Starting .NET checks..." -ForegroundColor Green
    
    foreach ($version in $DotNetVersions) {
        Write-Host "`nRunning checks for .NET $version" -ForegroundColor Cyan
        
        # Check if .NET version is installed
        $installedSdks = dotnet --list-sdks
        $versionInstalled = $installedSdks | Where-Object { $_ -match "^$version\." }
        if (-not $versionInstalled) {
            Write-Warning ".NET $version is not installed. Skipping this version."
            continue
        }
        
        Write-Host "1. Restoring dependencies..." -ForegroundColor Yellow
        dotnet restore
        if ($LASTEXITCODE -ne 0) { throw "Restore failed for .NET $version" }
        
        Write-Host "2. Building..." -ForegroundColor Yellow
        dotnet build --no-restore --configuration $Configuration
        if ($LASTEXITCODE -ne 0) { throw "Build failed for .NET $version" }
        
        Write-Host "3. Checking format..." -ForegroundColor Yellow
        dotnet format --verify-no-changes --verbosity diagnostic
        if ($LASTEXITCODE -ne 0) { throw "Format check failed for .NET $version" }
        
        Write-Host "4. Running tests..." -ForegroundColor Yellow
        dotnet test "tests\Azure\Data\Postgresql\Npgsql\Azure.Data.Postgresql.Npgsql.Tests.csproj" --configuration $Configuration --logger trx --results-directory "TestResults"
        if ($LASTEXITCODE -ne 0) { throw "Tests failed for .NET $version" }
        
        Write-Host "5. Packing..." -ForegroundColor Yellow
        dotnet pack --no-build --configuration $Configuration --output "nupkgs"
        if ($LASTEXITCODE -ne 0) { throw "Pack failed for .NET $version" }
        
        Write-Host "All checks passed for .NET $version" -ForegroundColor Green
    }
    
    Write-Host "`nAll .NET checks completed successfully!" -ForegroundColor Green
    
    # Display output locations
    Write-Host "`nOutput locations:" -ForegroundColor Cyan
    if (Test-Path "TestResults") {
        Write-Host "  Test results: $(Resolve-Path 'TestResults')" -ForegroundColor Gray
    }
    if (Test-Path "nupkgs") {
        Write-Host "  NuGet packages: $(Resolve-Path 'nupkgs')" -ForegroundColor Gray
    }
}
catch {
    Write-Error ".NET checks failed: $($_.Exception.Message)"
    exit 1
}
finally {
    Set-Location $OriginalLocation
}