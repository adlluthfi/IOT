import json 
import threading 
import time 
import os 
from datetime import datetime 
import paho.mqtt.client as mqtt 
from flask import Flask, render_template 
import mysql.connector 

app = Flask(__name__) 

# Database configuration
db_config = { 
    'user': 'root',   
    'password': 'your_password',  # Ganti dengan password MySQL Anda
    'host': 'localhost', 
    'database': 'sensor_db' 
}

mqtt_started = False 

def create_table_if_not_exists():
    """Create table if not exists"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sensor_type VARCHAR(50) NOT NULL,
                value FLOAT NOT NULL,
                timestamp DATETIME NOT NULL
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] Tabel sensor_data siap")
    except Exception as e:
        print(f"[DB ERROR] Gagal membuat tabel: {e}")

def save_to_db(sensor_type, value): 
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        timestamp = datetime.now()
        query = "INSERT INTO sensor_data (sensor_type, value, timestamp) VALUES (%s, %s, %s)"
        cursor.execute(query, (sensor_type, value, timestamp))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[DB] Data disimpan: {sensor_type}, {value}, {timestamp}")
    except Exception as e:
        print(f"[DB ERROR] Gagal menyimpan data: {e}")

def get_all_data(): 
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT id, sensor_type, value, timestamp FROM sensor_data ORDER BY timestamp DESC")
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return data
    except Exception as e:
        print(f"[DB ERROR] Gagal mengambil data: {e}")
        return []

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Terhubung ke broker sukses | Thread: {threading.get_ident()}")
        print("[MQTT] Subscribe ke topik: sensor/data")
        client.subscribe("sensor/data")
    else:
        print(f"[MQTT ERROR] Gagal terhubung, RC={rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        sensor_type = data['sensor_type']
        value = data['value']
        print(f"[MQTT] Pesan diterima: {data} | Thread: {threading.get_ident()}")
        save_to_db(sensor_type, value)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e} | Payload: {msg.payload}")
    except KeyError as e:
        print(f"[ERROR] Key tidak ditemukan: {e} | Data: {data}")
    except Exception as e:
        print(f"[ERROR] Gagal processing pesan: {e}")

def run_mqtt():
    print(f"[THREAD] Menjalankan MQTT client... | Thread ID: {threading.get_ident()}")
    try:
        client = mqtt.Client()
        client.on_connect = on_connect
        client.on_message = on_message
        
        # GUNAKAN PORT 1883 (bukan 1884)
        client.connect("localhost", 1883, 60)
        print("[MQTT] Client connected, starting loop...")
        client.loop_forever()
    except Exception as e:
        print(f"[MQTT ERROR] {e}")

@app.route('/')
def index():
    data = get_all_data()
    return render_template('index.html', data=data)

if __name__ == '__main__':
    print(f"[MAIN] Aplikasi dimulai | PID: {os.getpid()} | Thread utama: {threading.get_ident()}")
    
    # Buat tabel jika belum ada
    create_table_if_not_exists()
    
    # Start MQTT thread hanya sekali
    global mqtt_started
    if not mqtt_started:
        mqtt_started = True
        mqtt_thread = threading.Thread(target=run_mqtt)
        mqtt_thread.daemon = True
        mqtt_thread.start()
        print(f"[MAIN] MQTT thread dimulai | Thread ID: {mqtt_thread.ident}")
    
    # Jangan lupa buat template folder dan file index.html
    app.run(debug=True, use_reloader=False, port=5000)