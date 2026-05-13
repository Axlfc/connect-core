# ═══════════════════════════════════════════════════════════════════
#  Cognito Stack — Installer for PowerShell Profile
#  Setup directory, config, and register in $PROFILE
# ═══════════════════════════════════════════════════════════════════

$cognitoDir = Join-Path $env:USERPROFILE ".cognito"
$configFile = Join-Path $cognitoDir "config.json"
$exampleFile = Join-Path $PSScriptRoot "config.example.json"
$profileScript = Join-Path $PSScriptRoot "test-voice-api.ps1"

Write-Host "Setting up Cognito Stack..." -ForegroundColor Cyan

# 1. Create .cognito directory
if (-not (Test-Path $cognitoDir)) {
    New-Item -Path $cognitoDir -ItemType Directory | Out-Null
    Write-Host "  [OK] Created $cognitoDir" -ForegroundColor Green
}

# 2. Copy config.json if not exists
if (-not (Test-Path $configFile)) {
    if (Test-Path $exampleFile) {
        Copy-Item -Path $exampleFile -Destination $configFile
        Write-Host "  [OK] Created $configFile (from example)" -ForegroundColor Green
    } else {
        # Create a default one if example is missing
        $defaultConfig = @{
            UncertaintyThreshold = 0.55
            EnableUncertainty    = $true
            ColorMode            = "full"
        }
        $defaultConfig | ConvertTo-Json | Out-File -FilePath $configFile -Encoding utf8
        Write-Host "  [OK] Created $configFile (default settings)" -ForegroundColor Green
    }
}

# 3. Add to $PROFILE
if (-not (Test-Path $PROFILE)) {
    New-Item -Path $PROFILE -ItemType File -Force | Out-Null
}

$profileContent = Get-Content $PROFILE
$importLine = ". '$profileScript'"

if ($profileContent -notcontains $importLine) {
    Add-Content -Path $PROFILE -Value "`n# Cognito Stack Profile`n$importLine"
    Write-Host "  [OK] Registered Cognito in PowerShell Profile ($PROFILE)" -ForegroundColor Green
} else {
    Write-Host "  [OK] Cognito already registered in PowerShell Profile" -ForegroundColor Yellow
}

Write-Host "`nInstallation Complete! Restart PowerShell to apply changes." -ForegroundColor Cyan
