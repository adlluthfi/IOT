# Python Health Monitoring Dashboard

Dashboard monitoring kesehatan real-time menggunakan Python, Streamlit, MQTT, dan InfluxDB.

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
streamlit run app.py
```

Dashboard akan buka di http://localhost:8501

## Features

- ✅ Real-time monitoring dari MQTT
- ✅ Auto-save ke InfluxDB
- ✅ Historical data visualization
- ✅ Anomaly detection & timeline
- ✅ Medical recommendations
- ✅ Export to CSV
- ✅ Auto-refresh setiap 5 detik
- ✅ Interactive charts dengan Plotly

## Configuration

Edit konfigurasi di `app.py`:
- INFLUX_CONFIG: InfluxDB settings
- MQTT_CONFIG: MQTT broker settings
