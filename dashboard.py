import streamlit as st
import paho.mqtt.client as mqtt
import struct
import numpy as np
import time

# --- 1. KONFIGURASI ---
MQTT_SERVER = "91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1763790949177"
MQTT_PASSWORD = "16J#HVlkg?D5N0.jbi%L"
TOPIC = "v1/sensor/heartbeat"

# --- 2. GLOBAL STORAGE ---
# Variabel ini tetap hidup di memori meskipun Streamlit refresh
if 'heart_data' not in st.session_state:
    st.session_state.heart_data = [0] * 244
if 'last_rx' not in st.session_state:
    st.session_state.last_rx = 0

# --- 3. MQTT LOGIC ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(TOPIC)
        print("✅ Terhubung ke HiveMQ dan Subscribed ke Topik")
    else:
        print(f"❌ Koneksi Gagal, rc: {rc}")

def on_message(client, userdata, msg):
    # Cek panjang payload biner (250 byte)
    if len(msg.payload) == 250:
        # Parsing biner: <HH (Header, ID), 244B (Data), H (Checksum)
        unpacked = struct.unpack("<HH244BH", msg.payload)
        
        # Simpan ke session state (ambil data payload index 2 sampai 246)
        st.session_state.heart_data = list(unpacked[2:246])
        st.session_state.last_rx = time.time()
        print(f"📩 Data Diterima: {time.strftime('%H:%M:%S')}")

@st.cache_resource
def start_mqtt_client():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.tls_set() # Wajib untuk HiveMQ Cloud
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_SERVER, MQTT_PORT, 60)
    client.loop_start() # Menjalankan thread MQTT secara independen
    return client

# Jalankan client MQTT
mqtt_client = start_mqtt_client()

# --- 4. TAMPILAN DASHBOARD ---
st.set_page_config(page_title="Cardiac Telemetry", layout="wide")

st.title("🏥 Cardiac Binary Monitoring System")

# Layout kolom untuk status
col1, col2, col3 = st.columns(3)

# Hitung durasi sejak data terakhir masuk
time_diff = time.time() - st.session_state.last_rx
is_online = time_diff < 5 # Jika data masuk kurang dari 5 detik lalu, anggap online

with col1:
    status_label = "ONLINE" if is_online else "OFFLINE"
    st.metric("Sensor Status", status_label, delta=None, 
              delta_color="normal" if is_online else "inverse")

with col2:
    st.metric("Last Update", f"{int(time_diff)}s ago" if st.session_state.last_rx > 0 else "No Data")

with col3:
    st.metric("Binary Size", "250 Bytes")

# Grafik utama
st.subheader("BPM Waveform (Live Data)")
st.line_chart(st.session_state.heart_data)

# Jika offline, beri instruksi debugging
if not is_online:
    st.warning("⚠️ Menunggu data biner dari ESP32. Pastikan Serial Monitor menunjukkan '✓ Sent 250 bytes'.")

# Fungsi refresh otomatis agar dashboard update tiap detik
time.sleep(1)
st.rerun()