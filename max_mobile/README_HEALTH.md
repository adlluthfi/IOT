# Health Monitor Mobile App

Aplikasi mobile untuk monitoring kesehatan real-time dari sensor MAX30100 (Heart Rate & SpO2) dengan kontrol sensor via MQTT.

## Fitur

✅ **Real-time Monitoring**
- Heart Rate (BPM)
- SpO2 (%)
- Status device

✅ **Sensor Control**
- Button Turn ON sensor
- Button Turn OFF sensor
- Feedback status sensor

✅ **MQTT TLS Connection**
- Secure connection ke HiveMQ Cloud
- Auto-reconnect
- Activity log

## Cara Menggunakan

### 1. Buka Aplikasi di Browser (Testing)

```bash
cd d:\apk\laragon\www\iot\mqtt_mobile_app\www
```

Buka file `health.html` di browser atau via localhost

### 2. Koneksi ke MQTT

- Broker: `91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud`
- Username: (sesuaikan dengan HiveMQ Anda)
- Password: (sesuaikan dengan HiveMQ Anda)
- Klik "Connect"

### 3. Monitoring Data

Setelah terkoneksi, Anda akan melihat:
- Data Heart Rate real-time
- Data SpO2 real-time  
- Status normal/alert
- Last update time

### 4. Kontrol Sensor

- **Turn ON Sensor**: Aktifkan sensor MAX30100
- **Turn OFF Sensor**: Matikan sensor (kirim data 0)

### 5. Build APK (Optional)

Untuk build menjadi APK Android:

```powershell
cd d:\apk\laragon\www\iot\mqtt_mobile_app
.\build-apk.ps1
```

## Topics MQTT

- `health/heartrate` - Data heart rate (subscribe)
- `health/spo2` - Data SpO2 (subscribe)
- `health/status` - Status device (subscribe)
- `health/control` - Perintah ON/OFF (publish)
- `health/control/response` - Response dari ESP32 (subscribe)

## Screenshot Fitur

1. **Login Screen**: Input broker, username, password
2. **Dashboard**: Tampilan data Heart Rate & SpO2
3. **Control Panel**: Button ON/OFF sensor
4. **Activity Log**: Log semua aktivitas MQTT

## Requirements

- ESP32-S3 dengan sensor MAX30100
- Koneksi internet
- HiveMQ Cloud account

## Troubleshooting

**Tidak bisa connect?**
- Pastikan internet aktif
- Cek username/password HiveMQ
- Cek URL broker

**Tidak terima data?**
- Pastikan ESP32 online dan terhubung WiFi
- Cek ESP32 serial monitor untuk konfirmasi publish
- Pastikan topic sama antara ESP32 dan app

**Sensor tidak OFF saat ditekan?**
- Cek ESP32 subscribe ke topic `health/control`
- Lihat serial monitor ESP32 untuk pesan control
