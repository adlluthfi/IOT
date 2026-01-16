# Cara Build APK Health Monitor

## Persiapan

1. **Install Node.js** (jika belum ada)
   - Download dari: https://nodejs.org
   - Install versi LTS

2. **Install Cordova**
   ```powershell
   npm install -g cordova
   ```

3. **Install Java JDK 17**
   - Download dari: https://adoptium.net/
   - Set JAVA_HOME environment variable

4. **Install Android Studio**
   - Download dari: https://developer.android.com/studio
   - Install Android SDK
   - Set ANDROID_HOME environment variable

## Build APK

### Langkah 1: Buka Terminal di Folder Project

```powershell
cd d:\apk\laragon\www\iot\mqtt_mobile_app
```

### Langkah 2: Add Platform Android (jika belum)

```powershell
cordova platform add android
```

### Langkah 3: Build APK

**Debug APK (untuk testing):**
```powershell
cordova build android
```

**Release APK (untuk distribusi):**
```powershell
cordova build android --release
```

### Langkah 4: Lokasi APK

APK akan tersimpan di:
- **Debug**: `platforms\android\app\build\outputs\apk\debug\app-debug.apk`
- **Release**: `platforms\android\app\build\outputs\apk\release\app-release-unsigned.apk`

## Install ke HP

### Via USB:

```powershell
cordova run android --device
```

### Via File APK:

1. Copy file `app-debug.apk` ke HP
2. Buka file manager di HP
3. Tap file APK
4. Izinkan "Install from Unknown Sources"
5. Install

## Troubleshooting

### Error: JAVA_HOME not set

Set environment variable:
```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.x"
```

### Error: ANDROID_HOME not set

Set environment variable:
```powershell
$env:ANDROID_HOME = "C:\Users\YourUsername\AppData\Local\Android\Sdk"
$env:Path += ";$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\tools"
```

### Error: Gradle build failed

Update Gradle di `platforms\android\build.gradle` atau rebuild:
```powershell
cordova platform remove android
cordova platform add android
cordova build android
```

## Cara Cepat (Script Otomatis)

Gunakan script yang sudah ada:

```powershell
.\build-apk.ps1
```

Script ini akan otomatis build APK debug.

## Testing Tanpa Build APK

Test di browser dulu:
1. Buka `www\health.html` di Chrome
2. Tekan F12 untuk dev tools
3. Klik icon mobile device
4. Test semua fitur

## File Penting

- `config.xml` - Konfigurasi Cordova
- `www/health.html` - Main app
- `www/js/health.js` - App logic
- `www/css/health.css` - Styling
