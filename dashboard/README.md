# Heartbeat Monitor Dashboard (Python)

Dashboard real-time untuk memonitor data heartbeat dari ESP32 via MQTT.

## Requirements

- Python 3.8+
- pip

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Jalankan dashboard:
```bash
python dashboard.py
```

Dashboard akan otomatis:
- Connect ke HiveMQ Cloud broker
- Subscribe ke topic `v1/sensor/heartbeat`
- Menampilkan waveform real-time
- Validasi checksum data
- Menampilkan statistik

## Features

✅ Real-time waveform visualization
✅ MQTT TLS connection
✅ Binary data parsing (250 bytes)
✅ Checksum validation
✅ Statistics tracking
✅ Console logging with colors
✅ Auto-reconnect

## Troubleshooting

Jika koneksi gagal:
1. Pastikan WiFi/internet aktif
2. Cek credentials MQTT di `MQTT_CONFIG`
3. Pastikan ESP32 sudah publish data
