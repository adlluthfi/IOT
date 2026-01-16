# Health Monitoring Dashboard

Dashboard React untuk monitoring real-time data kesehatan dari ESP32-S3 dengan sensor MAX30100 melalui MQTT HiveMQ.

## Fitur

- 📊 Real-time monitoring Heart Rate dan SpO2
- 📈 Grafik line chart untuk visualisasi data
- 🔒 Koneksi MQTT dengan TLS/SSL
- 🎨 UI modern dengan gradient dan glassmorphism
- 📱 Responsive design
- 🔄 Auto-reconnect MQTT

## Instalasi

1. Install dependencies:
```bash
npm install
```

2. Konfigurasi MQTT di `src/App.js`:
```javascript
const mqttConfig = {
  broker: 'wss://broker.hivemq.com:8884/mqtt',
  username: 'username_anda', // Ganti dengan username Anda
  password: 'password_anda', // Ganti dengan password Anda
  ...
};
```

3. Jalankan aplikasi:
```bash
npm start
```

Aplikasi akan berjalan di `http://localhost:3000`

## Data yang Ditampilkan

- **Heart Rate**: Detak jantung dalam BPM (Beats Per Minute)
- **SpO2**: Saturasi oksigen dalam persen (%)
- **Status**: Status koneksi device
- **Chart**: Grafik real-time 20 data terakhir

## Topics MQTT

- `health/heartrate` - Data heart rate
- `health/spo2` - Data SpO2
- `health/status` - Status device

## Build untuk Production

```bash
npm run build
```

File production akan tersimpan di folder `build/`
