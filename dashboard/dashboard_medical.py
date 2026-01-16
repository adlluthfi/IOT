import tkinter as tk
from tkinter import ttk
import paho.mqtt.client as mqtt
import struct
import threading
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import ssl
import numpy as np
from collections import deque

# ===== MQTT Configuration =====
MQTT_CONFIG = {
    'broker': '91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud',
    'port': 8883,
    'username': 'hivemq.webclient.1763790949177',
    'password': '16J#HVlkg?D5N0.jbi%L',
    'topic': 'health/streaming',
    'client_id': 'medical_monitor'
}

class MedicalMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Medical Patient Monitor")
        self.root.geometry("1400x900")
        self.root.configure(bg='#1a1a1a')
        
        # Data buffers - 10 detik untuk waveform yang smooth
        self.buffer_size = 600  # 10 paket x 60 samples = 10 detik
        self.ir_buffer = deque([0] * self.buffer_size, maxlen=self.buffer_size)
        self.red_buffer = deque([0] * self.buffer_size, maxlen=self.buffer_size)
        
        # Vital signs
        self.heart_rate = 0
        self.spo2 = 0
        self.hr_history = deque([0] * 60, maxlen=60)  # 1 menit history
        self.spo2_history = deque([0] * 60, maxlen=60)
        
        # Alarm thresholds
        self.hr_min = 50
        self.hr_max = 120
        self.spo2_min = 90
        
        # Status
        self.mqtt_connected = False
        self.alarm_active = False
        
        # Create UI
        self.create_widgets()
        
        # Connect MQTT
        self.connect_mqtt()
        
        # Start animations
        self.ani = FuncAnimation(self.fig, self.update_plot, interval=50, blit=False)
        
        # Update time
        self.update_clock()
        
    def create_widgets(self):
        # ===== Top Bar (Patient Info & Time) =====
        top_bar = tk.Frame(self.root, bg='#2d2d2d', height=60)
        top_bar.pack(fill='x')
        top_bar.pack_propagate(False)
        
        tk.Label(top_bar, text="PATIENT MONITOR", font=('Arial', 16, 'bold'), 
                bg='#2d2d2d', fg='white').pack(side='left', padx=20, pady=10)
        
        self.clock_label = tk.Label(top_bar, text="00:00:00", font=('Arial', 14), 
                                    bg='#2d2d2d', fg='#00ff00')
        self.clock_label.pack(side='right', padx=20)
        
        self.status_indicator = tk.Label(top_bar, text="●", font=('Arial', 20), 
                                        bg='#2d2d2d', fg='#ff0000')
        self.status_indicator.pack(side='right', padx=5)
        
        # ===== Main Content =====
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left: Vital Signs Display
        left_panel = tk.Frame(main_frame, bg='#1a1a1a', width=400)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Heart Rate Box (Red)
        self.create_vital_box(left_panel, "HEART RATE", "bpm", 
                             'hr_value', 'hr_status', '#ff0000', 0)
        
        # SpO2 Box (Blue)
        self.create_vital_box(left_panel, "SpO₂", "%", 
                             'spo2_value', 'spo2_status', '#00aaff', 1)
        
        # Alarm Status
        alarm_frame = tk.Frame(left_panel, bg='#2d2d2d', relief='solid', borderwidth=2)
        alarm_frame.pack(fill='x', pady=20, padx=10)
        
        self.alarm_label = tk.Label(alarm_frame, text="SYSTEM NORMAL", 
                                    font=('Arial', 14, 'bold'), 
                                    bg='#2d2d2d', fg='#00ff00', pady=10)
        self.alarm_label.pack()
        
        # Trend Info
        trend_frame = tk.LabelFrame(left_panel, text="TRENDS (Last 60s)", 
                                   font=('Arial', 10, 'bold'), 
                                   bg='#1a1a1a', fg='white', pady=10)
        trend_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.hr_trend = tk.Label(trend_frame, text="HR: --- / --- / ---", 
                                font=('Courier', 10), bg='#1a1a1a', fg='#ffaa00')
        self.hr_trend.pack(pady=5)
        
        self.spo2_trend = tk.Label(trend_frame, text="SpO₂: --- / --- / ---", 
                                  font=('Courier', 10), bg='#1a1a1a', fg='#ffaa00')
        self.spo2_trend.pack(pady=5)
        
        # Right: Waveforms
        right_panel = tk.Frame(main_frame, bg='#1a1a1a')
        right_panel.pack(side='right', fill='both', expand=True)
        
        # Create matplotlib figure dengan background hitam
        self.fig = plt.Figure(figsize=(10, 8), facecolor='#1a1a1a')
        
        # Plethysmograph (IR signal - red waveform)
        self.ax_pleth = self.fig.add_subplot(211, facecolor='#000000')
        self.line_pleth, = self.ax_pleth.plot([], [], 'r-', linewidth=2)
        self.ax_pleth.set_ylim(-150, 150)
        self.ax_pleth.set_xlim(0, self.buffer_size)
        self.ax_pleth.set_ylabel('PLETH', color='red', fontweight='bold', fontsize=12)
        self.ax_pleth.tick_params(colors='white')
        self.ax_pleth.grid(True, color='#003300', alpha=0.3)
        self.ax_pleth.axhline(y=0, color='#005500', linestyle='-', linewidth=0.5)
        self.ax_pleth.set_xticklabels([])
        
        # SpO2 waveform (Red signal - blue waveform)
        self.ax_spo2 = self.fig.add_subplot(212, facecolor='#000000')
        self.line_spo2, = self.ax_spo2.plot([], [], 'c-', linewidth=2)
        self.ax_spo2.set_ylim(-150, 150)
        self.ax_spo2.set_xlim(0, self.buffer_size)
        self.ax_spo2.set_ylabel('SpO₂', color='cyan', fontweight='bold', fontsize=12)
        self.ax_spo2.set_xlabel('Time (10 seconds)', color='white', fontsize=10)
        self.ax_spo2.tick_params(colors='white')
        self.ax_spo2.grid(True, color='#003333', alpha=0.3)
        self.ax_spo2.axhline(y=0, color='#005555', linestyle='-', linewidth=0.5)
        
        self.fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(self.fig, right_panel)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def create_vital_box(self, parent, label, unit, value_var, status_var, color, row):
        frame = tk.Frame(parent, bg='#2d2d2d', relief='solid', borderwidth=3, 
                        highlightbackground=color, highlightthickness=2)
        frame.pack(fill='x', pady=10, padx=10)
        
        # Label
        tk.Label(frame, text=label, font=('Arial', 14, 'bold'), 
                bg='#2d2d2d', fg=color).pack(pady=(10, 0))
        
        # Value
        value_label = tk.Label(frame, text="---", font=('Arial', 60, 'bold'), 
                              bg='#2d2d2d', fg=color)
        value_label.pack()
        setattr(self, value_var, value_label)
        
        # Unit
        tk.Label(frame, text=unit, font=('Arial', 16), 
                bg='#2d2d2d', fg='white').pack()
        
        # Status
        status_label = tk.Label(frame, text="NO SIGNAL", font=('Arial', 10), 
                               bg='#2d2d2d', fg='#ffaa00')
        status_label.pack(pady=(0, 10))
        setattr(self, status_var, status_label)
    
    def update_clock(self):
        now = datetime.now().strftime('%H:%M:%S')
        self.clock_label.config(text=now)
        self.root.after(1000, self.update_clock)
    
    def check_alarms(self):
        alarm = False
        messages = []
        
        if self.heart_rate > 0:
            if self.heart_rate < self.hr_min:
                alarm = True
                messages.append("BRADYCARDIA")
            elif self.heart_rate > self.hr_max:
                alarm = True
                messages.append("TACHYCARDIA")
        
        if self.spo2 > 0:
            if self.spo2 < self.spo2_min:
                alarm = True
                messages.append("LOW SpO₂")
        
        if alarm:
            self.alarm_label.config(text=" | ".join(messages), fg='#ff0000', bg='#ffff00')
            self.root.configure(bg='#ff0000')
        else:
            if self.heart_rate > 0 or self.spo2 > 0:
                self.alarm_label.config(text="SYSTEM NORMAL", fg='#00ff00', bg='#2d2d2d')
            else:
                self.alarm_label.config(text="NO SIGNAL", fg='#ffaa00', bg='#2d2d2d')
            self.root.configure(bg='#1a1a1a')
    
    def parse_packet(self, raw):
        if len(raw) != 250:
            return None
        try:
            header = struct.unpack('<H', raw[0:2])[0]
            if header != 0xAABB:
                return None
            
            heart_rate = struct.unpack('<f', raw[2:6])[0]
            spo2 = struct.unpack('<f', raw[6:10])[0]
            ir_data = np.frombuffer(raw, dtype='<u2', count=60, offset=10)
            red_data = np.frombuffer(raw, dtype='<u2', count=60, offset=130)
            
            return {
                'heart_rate': heart_rate,
                'spo2': spo2,
                'ir_data': ir_data,
                'red_data': red_data
            }
        except:
            return None
    
    def on_message(self, client, userdata, msg):
        packet = self.parse_packet(msg.payload)
        if packet:
            # Extend buffers dengan data baru
            self.ir_buffer.extend(packet['ir_data'].tolist())
            self.red_buffer.extend(packet['red_data'].tolist())
            
            # Update vital signs
            self.heart_rate = int(packet['heart_rate'])
            self.spo2 = int(packet['spo2'])
            
            # Update history
            self.hr_history.append(self.heart_rate if self.heart_rate > 0 else 0)
            self.spo2_history.append(self.spo2 if self.spo2 > 0 else 0)
            
            # Update UI
            self.root.after(0, self.update_vitals)
    
    def update_vitals(self):
        # Update HR display
        if self.heart_rate > 0:
            self.hr_value.config(text=str(self.heart_rate))
            self.hr_status.config(text="MONITORING", fg='#00ff00')
        else:
            self.hr_value.config(text="---")
            self.hr_status.config(text="NO SIGNAL", fg='#ffaa00')
        
        # Update SpO2 display
        if self.spo2 > 0:
            self.spo2_value.config(text=str(self.spo2))
            self.spo2_status.config(text="MONITORING", fg='#00ff00')
        else:
            self.spo2_value.config(text="---")
            self.spo2_status.config(text="NO SIGNAL", fg='#ffaa00')
        
        # Update trends
        valid_hr = [x for x in self.hr_history if x > 0]
        valid_spo2 = [x for x in self.spo2_history if x > 0]
        
        if valid_hr:
            hr_min, hr_max, hr_avg = min(valid_hr), max(valid_hr), int(np.mean(valid_hr))
            self.hr_trend.config(text=f"HR: {hr_min} / {hr_avg} / {hr_max}")
        
        if valid_spo2:
            spo2_min, spo2_max, spo2_avg = min(valid_spo2), max(valid_spo2), int(np.mean(valid_spo2))
            self.spo2_trend.config(text=f"SpO₂: {spo2_min} / {spo2_avg} / {spo2_max}")
        
        # Check alarms
        self.check_alarms()
    
    def update_plot(self, frame):
        # Convert to AC signal
        if len(self.ir_buffer) > 0 and max(self.ir_buffer) > 100:
            ir_data = list(self.ir_buffer)
            ir_mean = np.mean(ir_data)
            ir_ac = [x - ir_mean for x in ir_data]
            self.line_pleth.set_data(range(len(ir_ac)), ir_ac)
        else:
            self.line_pleth.set_data([], [])
        
        if len(self.red_buffer) > 0 and max(self.red_buffer) > 100:
            red_data = list(self.red_buffer)
            red_mean = np.mean(red_data)
            red_ac = [x - red_mean for x in red_data]
            self.line_spo2.set_data(range(len(red_ac)), red_ac)
        else:
            self.line_spo2.set_data([], [])
        
        return self.line_pleth, self.line_spo2
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.mqtt_connected = True
            self.status_indicator.config(fg='#00ff00')
            client.subscribe(MQTT_CONFIG['topic'])
    
    def connect_mqtt(self):
        try:
            self.mqtt_client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=MQTT_CONFIG['client_id']
            )
        except:
            self.mqtt_client = mqtt.Client(MQTT_CONFIG['client_id'])
        
        self.mqtt_client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
        
        try:
            self.mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)
        except:
            self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
            self.mqtt_client.tls_insecure_set(True)
        
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        def connect_thread():
            try:
                self.mqtt_client.connect(MQTT_CONFIG['broker'], MQTT_CONFIG['port'], 60)
                self.mqtt_client.loop_start()
            except:
                self.root.after(5000, self.connect_mqtt)
        
        threading.Thread(target=connect_thread, daemon=True).start()

def main():
    root = tk.Tk()
    app = MedicalMonitor(root)
    root.mainloop()

if __name__ == '__main__':
    main()
