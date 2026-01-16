Write-Host "Building MQTT APK..." -ForegroundColor Cyan

# Set Gradle path
$env:PATH = "C:\gradle-8.5\bin;" + $env:PATH

# Build
cd platforms\android
.\gradlew assembleDebug

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build success!" -ForegroundColor Green
    
    # Copy APK
    $apk = "app\build\outputs\apk\debug\app-debug.apk"
    copy $apk "..\..\MQTT-App.apk"
    
    Write-Host "APK saved: MQTT-App.apk" -ForegroundColor Green
    Write-Host "Size: $((Get-Item '..\..\MQTT-App.apk').Length / 1MB) MB" -ForegroundColor Yellow
} else {
    Write-Host "Build failed!" -ForegroundColor Red
}
