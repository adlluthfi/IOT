Write-Host "Installing Android Build Tools 35.0.0..." -ForegroundColor Cyan

C:\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat "build-tools;35.0.0"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build tools installed!" -ForegroundColor Green
    Write-Host "Now run: cordova build android" -ForegroundColor Yellow
} else {
    Write-Host "Installation failed!" -ForegroundColor Red
}
