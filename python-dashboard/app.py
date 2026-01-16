import streamlit as st
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from collections import deque
import threading
import queue

# ===== KONFIGURASI =====
INFLUX_CONFIG = {
    'url': 'http://localhost:8181',
    'token': 'NWzRfPZ8Qs3-D2it8nuIvhx93riCPGgJ9S4SxxV-8fN_GV6J8HkkdaDOIWwtfs8axmEs-qzV6HDYxKqgyBSkVA==',
    'org': 'my-org',
    'bucket': 'max30100'
}

MQTT_CONFIG = {
    'broker': '91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud',
    'port': 8883,
    'username': 'hivemq.webclient.1763790949177',
    'password': '16J#HVlkg?D5N0.jbi%L',
    'topics': {
        'heartrate': 'health/heartrate',
        'spo2': 'health/spo2',
        'status': 'health/status'
    }
}

# ===== HEALTH THRESHOLDS =====
HEALTH_THRESHOLDS = {
    'hr_high': 100,
    'hr_critical': 110,
    'hr_low': 60,
    'spo2_low': 95,
    'spo2_critical': 92
}

# ===== INFLUXDB CLIENT =====
@st.cache_resource
def get_influx_client():
    """Cached InfluxDB client - hanya dibuat sekali"""
    return InfluxDBClient(
        url=INFLUX_CONFIG['url'],
        token=INFLUX_CONFIG['token'],
        org=INFLUX_CONFIG['org']
    )

# ===== MQTT CLIENT MANAGER =====
class MQTTManager:
    """Thread-safe MQTT manager dengan auto-reconnect"""
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.data_queue = queue.Queue(maxsize=100)
        self.lock = threading.Lock()
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        
        # Data storage
        self.current_data = {
            'heartrate': 0,
            'spo2': 0,
            'last_update': None
        }
        self.realtime_buffer = deque(maxlen=50)
        self.alerts = deque(maxlen=20)
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            with self.lock:
                self.connected = True
                self.reconnect_delay = 5
            
            print(f"✅ Connected to MQTT at {datetime.now().strftime('%H:%M:%S')}")
            
            for topic in MQTT_CONFIG['topics'].values():
                client.subscribe(topic)
                print(f"📡 Subscribed: {topic}")
        else:
            with self.lock:
                self.connected = False
            print(f"❌ Connection failed (code: {rc})")
    
    def on_disconnect(self, client, userdata, rc):
        """MQTT disconnection dengan auto-reconnect"""
        with self.lock:
            self.connected = False
        
        print(f"🔌 Disconnected (code: {rc})")
        
        if rc != 0:
            print(f"🔄 Reconnecting in {self.reconnect_delay}s...")
            time.sleep(self.reconnect_delay)
            
            try:
                client.reconnect()
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
            except Exception as e:
                print(f"❌ Reconnect failed: {e}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message callback - masukkan ke queue"""
        try:
            topic = msg.topic
            value = float(msg.payload.decode())
            timestamp = datetime.now()
            
            self.data_queue.put({
                'topic': topic,
                'value': value,
                'timestamp': timestamp
            }, block=False)
            
        except queue.Full:
            print("⚠️ Queue penuh, data dropped")
        except Exception as e:
            print(f"❌ Message error: {e}")
    
    def process_data(self, influx_write_api):
        """Proses data dari queue - dipanggil berkala"""
        processed = 0
        
        while not self.data_queue.empty() and processed < 10:
            try:
                data = self.data_queue.get_nowait()
                topic = data['topic']
                value = data['value']
                timestamp = data['timestamp']
                
                # Tulis ke InfluxDB
                self._write_to_influx(influx_write_api, topic, value, timestamp)
                
                # Update data current
                with self.lock:
                    if topic == MQTT_CONFIG['topics']['heartrate']:
                        self.current_data['heartrate'] = value
                        self.current_data['last_update'] = timestamp
                        
                        self.realtime_buffer.append({
                            'time': timestamp,
                            'heartrate': value,
                            'spo2': self.current_data['spo2']
                        })
                        
                        self._check_anomalies(value, self.current_data['spo2'], timestamp)
                        
                    elif topic == MQTT_CONFIG['topics']['spo2']:
                        self.current_data['spo2'] = value
                        
                        if len(self.realtime_buffer) > 0:
                            self.realtime_buffer[-1]['spo2'] = value
                
                processed += 1
                
            except queue.Empty:
                break
            except Exception as e:
                print(f"❌ Processing error: {e}")
        
        return processed
    
    def _write_to_influx(self, write_api, topic, value, timestamp):
        """Tulis ke InfluxDB"""
        try:
            field_name = topic.split('/')[-1]
            point = Point("health_metrics") \
                .tag("device", "ESP32-S3") \
                .tag("location", "home") \
                .field(field_name, value) \
                .time(timestamp)
            
            write_api.write(bucket=INFLUX_CONFIG['bucket'], record=point)
            
        except Exception as e:
            print(f"❌ InfluxDB error: {e}")
    
    def _check_anomalies(self, hr, spo2, timestamp):
        """Deteksi anomali kesehatan"""
        alerts = []
        time_str = timestamp.strftime('%H:%M:%S')
        
        # Kondisi kritis
        if hr > HEALTH_THRESHOLDS['hr_critical'] and spo2 < HEALTH_THRESHOLDS['spo2_critical']:
            alerts.append({
                'severity': 'critical',
                'message': f'🚨 KRITIS: HR Tinggi ({hr:.0f}) + SpO2 Rendah ({spo2:.0f}%)',
                'time': time_str,
                'recommendation': '⚠️ Segera hubungi dokter atau call 119'
            })
        
        # Heart rate tinggi
        elif hr > HEALTH_THRESHOLDS['hr_high']:
            alerts.append({
                'severity': 'high',
                'message': f'⚠️ Heart Rate Tinggi: {hr:.0f} BPM',
                'time': time_str,
                'recommendation': '💡 Istirahat dan pantau kondisi'
            })
        
        # Heart rate rendah
        elif hr < HEALTH_THRESHOLDS['hr_low'] and hr > 0:
            alerts.append({
                'severity': 'high',
                'message': f'⚠️ Heart Rate Rendah: {hr:.0f} BPM',
                'time': time_str,
                'recommendation': '💡 Konsultasi dengan dokter'
            })
        
        # SpO2 rendah
        if spo2 < HEALTH_THRESHOLDS['spo2_low'] and spo2 > 0:
            severity = 'critical' if spo2 < HEALTH_THRESHOLDS['spo2_critical'] else 'medium'
            alerts.append({
                'severity': severity,
                'message': f'⚡ SpO2 Rendah: {spo2:.0f}%',
                'time': time_str,
                'recommendation': '💡 Periksa sensor atau konsultasi dokter'
            })
        
        for alert in alerts:
            self.alerts.append(alert)
    
    def get_current_data(self):
        """Ambil data sensor saat ini (thread-safe)"""
        with self.lock:
            return self.current_data.copy()
    
    def get_realtime_buffer(self):
        """Ambil buffer realtime (thread-safe)"""
        with self.lock:
            return list(self.realtime_buffer)
    
    def get_alerts(self):
        """Ambil alerts terbaru (thread-safe)"""
        with self.lock:
            return list(self.alerts)
    
    def start(self):
        """Start MQTT client"""
        if self.client is None:
            self.client = mqtt.Client()
            self.client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
            self.client.tls_set()
            
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message
            
            try:
                print(f"🔌 Connecting to {MQTT_CONFIG['broker']}...")
                self.client.connect(MQTT_CONFIG['broker'], MQTT_CONFIG['port'], 60)
                self.client.loop_start()
                print("✅ MQTT started")
            except Exception as e:
                print(f"❌ Connection error: {e}")
                self.connected = False
    
    def stop(self):
        """Stop MQTT client"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
    
    def is_connected(self):
        """Cek status koneksi"""
        with self.lock:
            return self.connected

# ===== CACHED RESOURCES =====
@st.cache_resource
def get_mqtt_manager():
    """Singleton MQTT manager"""
    manager = MQTTManager()
    manager.start()
    return manager

# ===== QUERY HISTORICAL DATA =====
def get_historical_data(query_api, time_range='1h'):
    """Query data historis dari InfluxDB"""
    query = f'''
    from(bucket: "{INFLUX_CONFIG['bucket']}")
        |> range(start: -{time_range})
        |> filter(fn: (r) => r._measurement == "health_metrics")
        |> filter(fn: (r) => r._field == "heartrate" or r._field == "spo2")
        |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
    '''
    
    try:
        result = query_api.query(query=query)
        
        data = []
        for table in result:
            for record in table.records:
                data.append({
                    'time': record.get_time(),
                    'field': record.get_field(),
                    'value': record.get_value()
                })
        
        if data:
            df = pd.DataFrame(data)
            df_pivot = df.pivot(index='time', columns='field', values='value').reset_index()
            df_pivot['time'] = pd.to_datetime(df_pivot['time'])
            return df_pivot
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Query error: {e}")
        return pd.DataFrame()

# ===== DETEKSI ANOMALY ZONES =====
def detect_anomaly_zones(df):
    """Deteksi zona anomali dari data historis"""
    if df.empty:
        return []
    
    zones = []
    current_zone = None
    
    for idx, row in df.iterrows():
        hr = row.get('heartrate', 0)
        sp = row.get('spo2', 0)
        
        is_anomalous = (
            (hr > HEALTH_THRESHOLDS['hr_high'] or hr < HEALTH_THRESHOLDS['hr_low']) or 
            (sp < HEALTH_THRESHOLDS['spo2_low']) or 
            (hr > HEALTH_THRESHOLDS['hr_critical'] and sp < HEALTH_THRESHOLDS['spo2_critical'])
        )
        
        if is_anomalous:
            if current_zone is None:
                current_zone = {
                    'start': row['time'],
                    'severity': 'warning',
                    'reasons': []
                }
            
            if hr > HEALTH_THRESHOLDS['hr_critical'] and sp < HEALTH_THRESHOLDS['spo2_critical']:
                current_zone['severity'] = 'critical'
                current_zone['reasons'].append('Kritis: HR Tinggi + SpO2 Rendah')
            elif hr > HEALTH_THRESHOLDS['hr_high']:
                if current_zone['severity'] != 'critical':
                    current_zone['severity'] = 'high'
                current_zone['reasons'].append('Heart Rate Tinggi')
            elif hr < HEALTH_THRESHOLDS['hr_low']:
                if current_zone['severity'] != 'critical':
                    current_zone['severity'] = 'high'
                current_zone['reasons'].append('Heart Rate Rendah')
            
            if sp < HEALTH_THRESHOLDS['spo2_low']:
                if current_zone['severity'] not in ['critical', 'high']:
                    current_zone['severity'] = 'medium'
                current_zone['reasons'].append('SpO2 Rendah')
        else:
            if current_zone:
                current_zone['end'] = df.iloc[idx - 1]['time']
                current_zone['reasons'] = list(set(current_zone['reasons']))
                zones.append(current_zone)
                current_zone = None
    
    if current_zone:
        current_zone['end'] = df.iloc[-1]['time']
        current_zone['reasons'] = list(set(current_zone['reasons']))
        zones.append(current_zone)
    
    return zones

# ===== STREAMLIT UI =====
def main():
    st.set_page_config(
        page_title="Health Monitoring Dashboard",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Initialize resources
    influx_client = get_influx_client()
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)
    query_api = influx_client.query_api()
    mqtt_manager = get_mqtt_manager()
    
    # Process MQTT data queue
    processed = mqtt_manager.process_data(write_api)
    
    # Header
    st.title("🏥 Real-Time Health Monitoring Dashboard")
    st.caption("Monitoring Heart Rate & SpO2 dengan ESP32-S3 + MAX30100")
    
    # Status Bar
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        current = mqtt_manager.get_current_data()
        if current['last_update']:
            time_diff = (datetime.now() - current['last_update']).total_seconds()
            if time_diff < 5:
                st.success(f"✅ Live • Last update: {current['last_update'].strftime('%H:%M:%S')}")
            else:
                st.warning(f"⏳ Delayed • Last: {int(time_diff)}s ago")
        else:
            st.info("⏳ Waiting for data...")
    
    with col2:
        if mqtt_manager.is_connected():
            st.success("🔗 MQTT Connected")
        else:
            st.error("❌ MQTT Disconnected")
    
    with col3:
        st.caption(f"📊 Processed: {processed} msgs")
    
    st.divider()
    
    # ===== CURRENT VITALS =====
    st.subheader("📊 Current Vitals")
    
    current_data = mqtt_manager.get_current_data()
    hr = current_data['heartrate']
    spo2 = current_data['spo2']
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        hr_delta = None
        hr_color = "normal"
        if hr > HEALTH_THRESHOLDS['hr_high']:
            hr_color = "inverse"
        elif hr < HEALTH_THRESHOLDS['hr_low'] and hr > 0:
            hr_color = "inverse"
        
        st.metric(
            label="❤️ Heart Rate",
            value=f"{hr:.0f} BPM" if hr > 0 else "-- BPM",
            delta=hr_delta,
            delta_color=hr_color
        )
    
    with col2:
        spo2_color = "normal"
        if spo2 < HEALTH_THRESHOLDS['spo2_low'] and spo2 > 0:
            spo2_color = "inverse"
        
        st.metric(
            label="🫁 SpO2",
            value=f"{spo2:.0f} %" if spo2 > 0 else "-- %",
            delta_color=spo2_color
        )
    
    with col3:
        is_critical = (hr > HEALTH_THRESHOLDS['hr_critical'] and spo2 < HEALTH_THRESHOLDS['spo2_critical']) or hr > 120 or spo2 < 90
        is_warning = (hr > HEALTH_THRESHOLDS['hr_high'] or hr < HEALTH_THRESHOLDS['hr_low']) or spo2 < HEALTH_THRESHOLDS['spo2_low']
        
        if is_critical:
            st.error("🚨 CRITICAL")
        elif is_warning:
            st.warning("⚠️ WARNING")
        else:
            st.success("✅ NORMAL")
    
    # ===== ALERTS =====
    alerts = mqtt_manager.get_alerts()
    if alerts:
        st.subheader("🚨 Recent Alerts")
        for alert in list(reversed(alerts))[:5]:
            severity_map = {
                'critical': ('error', '🚨'),
                'high': ('warning', '⚠️'),
                'medium': ('info', '⚡')
            }
            method_name, icon = severity_map.get(alert['severity'], ('info', '📊'))
            method = getattr(st, method_name)
            
            method(f"**{alert['time']}** - {alert['message']}\n{alert['recommendation']}")
    
    st.divider()
    
    # ===== REAL-TIME CHART =====
    st.subheader("📡 Real-Time Monitoring (Last 50 readings)")
    
    realtime_data = mqtt_manager.get_realtime_buffer()
    
    if len(realtime_data) > 0:
        df_realtime = pd.DataFrame(realtime_data)
        df_realtime['time_str'] = df_realtime['time'].apply(lambda x: x.strftime('%H:%M:%S'))
        
        fig = go.Figure()
        
        # Heart Rate trace
        fig.add_trace(go.Scatter(
            x=df_realtime['time_str'],
            y=df_realtime['heartrate'],
            mode='lines+markers',
            name='Heart Rate',
            line=dict(color='#ff6b6b', width=2),
            marker=dict(size=4),
            hovertemplate='<b>HR:</b> %{y:.0f} BPM<extra></extra>'
        ))
        
        # SpO2 trace
        fig.add_trace(go.Scatter(
            x=df_realtime['time_str'],
            y=df_realtime['spo2'],
            mode='lines+markers',
            name='SpO2',
            line=dict(color='#4ecdc4', width=2),
            marker=dict(size=4),
            yaxis='y2',
            hovertemplate='<b>SpO2:</b> %{y:.0f}%<extra></extra>'
        ))
        
        # Threshold lines
        fig.add_hline(
            y=HEALTH_THRESHOLDS['hr_high'], 
            line_dash="dash", 
            line_color="rgba(255, 107, 107, 0.3)",
            annotation_text="HR High",
            annotation_position="right"
        )
        
        fig.add_hline(
            y=HEALTH_THRESHOLDS['spo2_low'], 
            line_dash="dash", 
            line_color="rgba(78, 205, 196, 0.3)",
            annotation_text="SpO2 Low",
            annotation_position="right",
            yref='y2'
        )
        
        fig.update_layout(
            xaxis=dict(title='Time', tickangle=-45),
            yaxis=dict(
                title='Heart Rate (BPM)', 
                side='left',
                range=[40, 140]
            ),
            yaxis2=dict(
                title='SpO2 (%)', 
                overlaying='y', 
                side='right',
                range=[80, 105]
            ),
            height=450,
            hovermode='x unified',
            showlegend=True,
            legend=dict(x=0.01, y=0.99),
            margin=dict(t=30, b=60)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"📊 Showing {len(df_realtime)} data points")
        with col2:
            if st.button("🗑️ Clear Buffer", use_container_width=True):
                mqtt_manager.realtime_buffer.clear()
                st.rerun()
    
    else:
        st.info("⏳ Waiting for real-time data... Pastikan ESP32 mengirim data ke MQTT.")
    
    st.divider()
    
    # ===== HISTORICAL DATA =====
    st.subheader("📈 Historical Data Analysis")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        time_range = st.selectbox(
            "Time Range:",
            options=['1h', '6h', '24h', '7d', '30d'],
            format_func=lambda x: {
                '1h': '⏱️ Last 1 Hour',
                '6h': '⏱️ Last 6 Hours',
                '24h': '📅 Last 24 Hours',
                '7d': '📅 Last 7 Days',
                '30d': '📅 Last 30 Days'
            }[x],
            index=0
        )
    
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    with col3:
        auto_refresh = st.checkbox("♻️ Auto-refresh", value=True)
    
    # Query historical data
    with st.spinner("📊 Loading historical data..."):
        df_hist = get_historical_data(query_api, time_range)
    
    if not df_hist.empty:
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Total Records", f"{len(df_hist):,}")
        
        with col2:
            if 'heartrate' in df_hist.columns:
                avg_hr = df_hist['heartrate'].mean()
                st.metric("💓 Avg Heart Rate", f"{avg_hr:.1f} BPM")
        
        with col3:
            if 'spo2' in df_hist.columns:
                avg_spo2 = df_hist['spo2'].mean()
                st.metric("🫁 Avg SpO2", f"{avg_spo2:.1f}%")
        
        with col4:
            zones = detect_anomaly_zones(df_hist)
            st.metric("⚠️ Anomaly Periods", len(zones))
        
        # Anomaly zones
        if zones:
            st.subheader("⚠️ Anomaly Timeline")
            
            for zone in zones:
                severity_icons = {
                    'critical': '🚨',
                    'high': '⚠️',
                    'medium': '⚡',
                    'warning': '📊'
                }
                
                icon = severity_icons.get(zone['severity'], '📊')
                start_str = zone['start'].strftime('%Y-%m-%d %H:%M:%S')
                end_str = zone['end'].strftime('%Y-%m-%d %H:%M:%S')
                duration = (zone['end'] - zone['start']).total_seconds() / 60
                
                with st.expander(f"{icon} {start_str} → {end_str} ({duration:.0f} min)"):
                    st.write(f"**Severity:** {zone['severity'].upper()}")
                    st.write("**Reasons:**")
                    for reason in zone['reasons']:
                        st.write(f"- {reason}")
                    
                    if zone['severity'] == 'critical':
                        st.error("🚨 **Urgent:** Segera konsultasi dokter!")
                    elif zone['severity'] == 'high':
                        st.warning("⚠️ **Perhatian:** Monitoring ketat diperlukan")
        
        # Historical chart
        st.subheader("📊 Historical Trends")
        
        fig_hist = go.Figure()
        
        # Plot data
        if 'heartrate' in df_hist.columns:
            fig_hist.add_trace(go.Scatter(
                x=df_hist['time'],
                y=df_hist['heartrate'],
                mode='lines',
                name='Heart Rate',
                line=dict(color='#ff6b6b', width=2)
            ))
        
        if 'spo2' in df_hist.columns:
            fig_hist.add_trace(go.Scatter(
                x=df_hist['time'],
                y=df_hist['spo2'],
                mode='lines',
                name='SpO2',
                line=dict(color='#4ecdc4', width=2),
                yaxis='y2'
            ))
        
        # Add anomaly zones
        shapes = []
        for zone in zones:
            color_map = {
                'critical': 'rgba(255, 71, 87, 0.2)',
                'high': 'rgba(255, 165, 2, 0.15)',
                'medium': 'rgba(255, 211, 42, 0.1)',
                'warning': 'rgba(112, 161, 255, 0.1)'
            }
            
            shapes.append(dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=zone['start'],
                x1=zone['end'],
                y0=0,
                y1=1,
                fillcolor=color_map.get(zone['severity'], 'rgba(128, 128, 128, 0.1)'),
                line=dict(width=0),
                layer="below"
            ))
        
        fig_hist.update_layout(
            shapes=shapes,
            xaxis=dict(title='Time'),
            yaxis=dict(title='Heart Rate (BPM)', side='left'),
            yaxis2=dict(title='SpO2 (%)', overlaying='y', side='right'),
            height=500,
            hovermode='x unified',
            showlegend=True
        )
        
        # Threshold lines
        fig_hist.add_hline(
            y=HEALTH_THRESHOLDS['hr_high'], 
            line_dash="dash", 
            line_color="rgba(255, 0, 0, 0.3)"
        )
        fig_hist.add_hline(
            y=HEALTH_THRESHOLDS['spo2_low'], 
            line_dash="dash", 
            line_color="rgba(0, 255, 255, 0.3)",
            yref='y2'
        )
        
        st.plotly_chart(fig_hist, use_container_width=True)
        
        # Export button
        if st.button("📥 Export to CSV", use_container_width=False):
            csv = df_hist.to_csv(index=False)
            st.download_button(
                label="💾 Download CSV",
                data=csv,
                file_name=f"health_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    else:
        st.info(f"📊 No data available for {time_range} range")
        st.caption("Data akan muncul setelah ESP32 mengirim data ke MQTT dan InfluxDB")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(2)
        st.rerun()

if __name__ == "__main__":
    main()