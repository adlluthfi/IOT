Write-Host "Installing MQTT App to Phone..." -ForegroundColor Cyan

# Check if device connected
$devices = adb devices | Select-String "device$"

if ($devices) {
    Write-Host "Device found! Installing..." -ForegroundColor Green
    
    # Install
    adb install -r d:\MQTT-App.apk
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "App installed successfully!" -ForegroundColor Green
        
        # Launch
        Write-Host "Launching app..." -ForegroundColor Cyan
        adb shell am start -n com.mqtt.app/.MainActivity
        
        Write-Host "Done!" -ForegroundColor Green
    } else {
        Write-Host "Installation failed!" -ForegroundColor Red
    }
} else {
    Write-Host "No device connected!" -ForegroundColor Red
    Write-Host "Please:" -ForegroundColor Yellow
    Write-Host "1. Enable USB Debugging on phone" -ForegroundColor Yellow
    Write-Host "2. Connect phone via USB" -ForegroundColor Yellow
    Write-Host "3. Run this script again" -ForegroundColor Yellow
}
