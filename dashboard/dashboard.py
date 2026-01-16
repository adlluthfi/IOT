import tkinter as tk
from tkinter import ttk, scrolledtext
import paho.mqtt.client as mqtt
import struct
import threading
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import ssl
import numpy as np

# ===== MQTT Configuration =====
MQTT_CONFIG = {
    'broker': '91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud',
    'port': 8883,
    'username': 'hivemq.webclient.1763790949177',
    'password': '16J#HVlkg?D5N0.jbi%L',
    'topic': 'health/streaming',  # Ubah topic sesuai ESP32
    'client_id': 'python_dashboard'
}

class HeartbeatDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("🫀 MAX30100 Health Monitor Dashboard")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        # Data storage - buffer untuk 10 detik (600 samples = 10 paket x 60 samples)
        self.buffer_size = 600  # 10 paket x 60 samples
        self.ir_data = [0] * self.buffer_size
        self.red_data = [0] * self.buffer_size
        self.heart_rate = 0.0
        self.spo2 = 0.0
        self.packet_count = 0
        self.mqtt_connected = False
        self.total_bytes_received = 0
        
        # Scrolling position untuk efek bergerak kanan ke kiri
        self.scroll_position = 0
        
        # Data rate tracking
        self.bytes_this_second = 0
        self.last_rate_update = datetime.now()
        self.current_bytes_per_second = 0
        
        # MQTT Client
        self.mqtt_client = None
        
        # Create UI
        self.create_widgets()
        
        # Start MQTT connection
        self.connect_mqtt()
        
        # Start animation
        self.ani = FuncAnimation(self.fig, self.update_plot, interval=100, blit=False)
        
        # Start data rate calculator
        self.calculate_data_rate()
        
    def create_widgets(self):
        # ===== Header Frame =====
        header_frame = tk.Frame(self.root, bg='#667eea', pady=15)
        header_frame.pack(fill='x')
        
        tk.Label(header_frame, text="🫀 MAX30100 Health Monitor Dashboard", 
                font=('Arial', 20, 'bold'), bg='#667eea', fg='white').pack()
        
        # Status bar
        status_frame = tk.Frame(header_frame, bg='#667eea')
        status_frame.pack(pady=5)
        
        self.status_label = tk.Label(status_frame, text="● Disconnected", 
                                     font=('Arial', 10), bg='#667eea', fg='#ff4444')
        self.status_label.pack(side='left', padx=10)
        
        self.device_label = tk.Label(status_frame, text="Device: -", 
                                     font=('Arial', 10), bg='#667eea', fg='white')
        self.device_label.pack(side='left', padx=10)
        
        self.time_label = tk.Label(status_frame, text="Last Update: -", 
                                   font=('Arial', 10), bg='#667eea', fg='white')
        self.time_label.pack(side='left', padx=10)
        
        # ===== Main Content =====
        content_frame = tk.Frame(self.root, bg='#f0f0f0')
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left panel - Graph
        left_frame = tk.LabelFrame(content_frame, text="📊 Real-time Waveform", 
                                   font=('Arial', 12, 'bold'), bg='white', padx=10, pady=10)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Matplotlib figure - 2 subplots untuk IR dan Red
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(8, 6), facecolor='white')
        
        # IR plot - tampilkan 600 samples (10 paket) dengan scrolling
        self.line_ir, = self.ax1.plot([], [], 'r-', linewidth=1.5, label='IR')
        self.ax1.set_ylim(-150, 150)
        self.ax1.set_xlim(0, self.buffer_size)
        self.ax1.set_ylabel('IR AC Signal', fontsize=10)
        self.ax1.set_title('IR Waveform (scrolling right to left)', fontsize=10)
        self.ax1.legend(loc='upper right')
        self.ax1.grid(True, alpha=0.3)
        self.ax1.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        
        # Red plot - tampilkan 600 samples (10 paket) dengan scrolling
        self.line_red, = self.ax2.plot([], [], 'b-', linewidth=1.5, label='Red')
        self.ax2.set_ylim(-150, 150)
        self.ax2.set_xlim(0, self.buffer_size)
        self.ax2.set_ylabel('Red AC Signal', fontsize=10)
        self.ax2.set_xlabel('Sample (scrolling view)', fontsize=10)
        self.ax2.set_title('Red Waveform (scrolling right to left)', fontsize=10)
        self.ax2.legend(loc='upper right')
        self.ax2.grid(True, alpha=0.3)
        self.ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)
        
        self.fig.tight_layout()
        
        canvas = FigureCanvasTkAgg(self.fig, left_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Right panel
        right_frame = tk.Frame(content_frame, bg='#f0f0f0')
        right_frame.pack(side='right', fill='both', padx=(5, 0))
        
        # Statistics
        stats_frame = tk.LabelFrame(right_frame, text="📈 Statistics", 
                                   font=('Arial', 12, 'bold'), bg='white', padx=15, pady=15)
        stats_frame.pack(fill='x', pady=(0, 10))
        
        # Stat boxes - tambah Heart Rate dan SpO2
        self.create_stat_box(stats_frame, "Heart Rate (BPM)", "heart_rate", 0)
        self.create_stat_box(stats_frame, "SpO2 (%)", "spo2", 1)
        self.create_stat_box(stats_frame, "Packets Received", "packet_count", 2)
        self.create_stat_box(stats_frame, "Data Rate", "bytes_received", 3)
        self.create_stat_box(stats_frame, "IR Avg", "ir_avg", 4)
        self.create_stat_box(stats_frame, "Red Avg", "red_avg", 5)
        
        # Console log
        log_frame = tk.LabelFrame(right_frame, text="📜 Console Log", 
                                 font=('Arial', 12, 'bold'), bg='white', padx=10, pady=10)
        log_frame.pack(fill='both', expand=True)
        
        self.console = scrolledtext.ScrolledText(log_frame, height=20, width=40, 
                                                font=('Consolas', 9), bg='#1e1e1e', 
                                                fg='#d4d4d4', insertbackground='white')
        self.console.pack(fill='both', expand=True)
        
        # Configure text tags for colored output
        self.console.tag_config('info', foreground='#569cd6')
        self.console.tag_config('success', foreground='#4ec9b0')
        self.console.tag_config('error', foreground='#f48771')
        self.console.tag_config('time', foreground='#858585')
    
    def create_stat_box(self, parent, label_text, var_name, row):
        frame = tk.Frame(parent, bg='#f8f9fa', relief='solid', borderwidth=1)
        frame.pack(fill='x', pady=5)
        
        tk.Label(frame, text=label_text, font=('Arial', 9), 
                bg='#f8f9fa', fg='#666').pack(anchor='w', padx=10, pady=(5, 0))
        
        var = tk.StringVar(value="0")
        setattr(self, f'{var_name}_var', var)
        
        tk.Label(frame, textvariable=var, font=('Arial', 18, 'bold'), 
                bg='#f8f9fa', fg='#333').pack(anchor='w', padx=10, pady=(0, 5))
    
    def log(self, message, level='info'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.console.insert('end', f'[{timestamp}] ', 'time')
        self.console.insert('end', f'{message}\n', level)
        self.console.see('end')
        
        # Keep only last 100 lines
        lines = int(self.console.index('end-1c').split('.')[0])
        if lines > 100:
            self.console.delete('1.0', f'{lines-100}.0')
    
    def update_status(self, connected):
        self.mqtt_connected = connected
        if connected:
            self.status_label.config(text="● Connected", fg='#44ff44')
        else:
            self.status_label.config(text="● Disconnected", fg='#ff4444')
    
    def calculate_checksum(self, data):
        """Calculate XOR checksum for data array"""
        crc = 0
        for byte in data:
            crc ^= byte
        return crc & 0xFFFF
    
    def parse_packet(self, raw):
        """Parse binary packet struktur baru: 250 bytes total
        - Header: uint16 (2 bytes) = 0xAABB
        - Heart Rate: float32 (4 bytes)
        - SpO2: float32 (4 bytes)
        - IR Data: uint16[60] (120 bytes)
        - Red Data: uint16[60] (120 bytes)
        """
        # Validate packet size
        if len(raw) != 250:
            self.log(f'Invalid packet size: {len(raw)} bytes (expected 250)', 'error')
            return None

        try:
            # ==============================
            # Decode packet menggunakan struct/numpy
            # ==============================

            # 1. Header (uint16 little-endian) - offset 0
            header = struct.unpack('<H', raw[0:2])[0]

            # 2. Heart Rate (float32 little-endian) - offset 2
            heart_rate = struct.unpack('<f', raw[2:6])[0]

            # 3. SpO2 (float32 little-endian) - offset 6
            spo2 = struct.unpack('<f', raw[6:10])[0]

            # 4. IR Data (60 x uint16 little-endian) - offset 10
            ir_data = np.frombuffer(raw, dtype='<u2', count=60, offset=10)

            # 5. Red Data (60 x uint16 little-endian) - offset 130
            red_data = np.frombuffer(raw, dtype='<u2', count=60, offset=130)

            # ==============================
            # Validate header
            # ==============================
            if header != 0xAABB:
                self.log(f'Invalid header: 0x{header:04X} (expected 0xAABB)', 'error')
                return None

            # ==============================
            # VALIDASI DATA: Jangan hitung jika HR/SpO2 = 0
            # ==============================
            # Jika ESP32 kirim HR=0 dan SpO2=0, berarti tidak ada jari
            # Jangan override dengan kalkulasi lokal!
            
            return {
                'header': header,
                'heart_rate': heart_rate,  # Gunakan langsung dari ESP32
                'spo2': spo2,              # Gunakan langsung dari ESP32
                'ir_data': ir_data,
                'red_data': red_data
            }

        except Exception as e:
            self.log(f'Parse error: {str(e)}', 'error')
            return None
    
    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT message"""
        # Track bytes received for data rate calculation
        payload_size = len(msg.payload)
        self.bytes_this_second += payload_size
        self.total_bytes_received += payload_size
        
        # Parse packet
        packet = self.parse_packet(msg.payload)
        if packet:
            # Shift buffer ke kiri (hapus 60 data lama, tambah 60 data baru di kanan)
            self.ir_data = self.ir_data[60:] + packet['ir_data'].tolist()
            self.red_data = self.red_data[60:] + packet['red_data'].tolist()
            
            # Update scroll position untuk efek bergerak
            self.scroll_position += 60
            
            # Update vital signs
            self.heart_rate = packet['heart_rate']
            self.spo2 = packet['spo2']
            self.packet_count += 1
            
            # Update UI in main thread
            self.root.after(0, self.update_ui, packet)
    
    def calculate_data_rate(self):
        """Calculate and update bytes per second"""
        now = datetime.now()
        time_diff = (now - self.last_rate_update).total_seconds()
        
        # Update every second
        if time_diff >= 1.0:
            # Prevent division by zero
            if time_diff > 0:
                self.current_bytes_per_second = self.bytes_this_second / time_diff
            else:
                self.current_bytes_per_second = 0
            
            # Reset counter
            self.bytes_this_second = 0
            self.last_rate_update = now
            
            # Format data rate display
            if self.current_bytes_per_second < 1024:
                rate_str = f"{self.current_bytes_per_second:.0f} B/s"
            elif self.current_bytes_per_second < 1024 * 1024:
                rate_str = f"{self.current_bytes_per_second / 1024:.2f} KB/s"
            else:
                rate_str = f"{self.current_bytes_per_second / (1024 * 1024):.2f} MB/s"
            
            self.bytes_received_var.set(rate_str)
        
        # Schedule next calculation
        self.root.after(100, self.calculate_data_rate)
    
    def update_ui(self, packet):
        """Update UI elements with new packet data"""
        # Ambil nilai langsung dari ESP32 (JANGAN kalkulasi ulang!)
        hr = packet['heart_rate']
        sp = packet['spo2']
        
        # Update vital signs - tampilkan "---" jika 0
        if hr > 0 and hr < 220:
            self.heart_rate_var.set(f"{hr:.1f}")
        else:
            self.heart_rate_var.set("---")
        
        if sp > 0 and sp <= 100:
            self.spo2_var.set(f"{sp:.0f}")
        else:
            self.spo2_var.set("---")
        
        # Update statistics
        self.packet_count_var.set(str(self.packet_count))
        
        # Calculate averages dari raw data (hanya untuk display, bukan kalkulasi HR/SpO2)
        ir_avg = np.mean(packet['ir_data'])
        red_avg = np.mean(packet['red_data'])
        
        self.ir_avg_var.set(f"{ir_avg:.0f}")
        self.red_avg_var.set(f"{red_avg:.0f}")
        
        # Update time
        time_str = datetime.now().strftime('%H:%M:%S')
        self.time_label.config(text=f"Last Update: {time_str}")
        
        # Log packet receipt dengan status
        if hr > 0 or sp > 0:
            status = '✓'
            self.log(f'{status} HR: {hr:.1f} bpm | SpO2: {sp:.0f}% | 250 bytes', 'success')
        else:
            status = '○'
            self.log(f'{status} No finger detected | 250 bytes', 'info')
    
    def update_plot(self, frame):
        """Update matplotlib plot (called by FuncAnimation) - scrolling dari kanan ke kiri"""
        # Convert raw data ke AC signal (kurangi rata-rata untuk center di 0)
        if len(self.ir_data) > 0 and max(self.ir_data) > 100:
            ir_mean = np.mean(self.ir_data)
            ir_ac = np.array([x - ir_mean for x in self.ir_data])
        else:
            ir_ac = np.zeros(self.buffer_size)
        
        if len(self.red_data) > 0 and max(self.red_data) > 100:
            red_mean = np.mean(self.red_data)
            red_ac = np.array([x - red_mean for x in self.red_data])
        else:
            red_ac = np.zeros(self.buffer_size)
        
        # Buat x-axis yang bergerak (efek scrolling kanan ke kiri)
        x_data = np.arange(self.buffer_size)
        
        # Update data plot
        self.line_ir.set_data(x_data, ir_ac)
        self.line_red.set_data(x_data, red_ac)
        
        # Fixed range -150 sampai 150 untuk melihat variasi seperti di rumah sakit
        self.ax1.set_ylim(-150, 150)
        self.ax2.set_ylim(-150, 150)
        
        # Xlim tetap fixed agar terlihat scrolling
        self.ax1.set_xlim(0, self.buffer_size)
        self.ax2.set_xlim(0, self.buffer_size)
        
        return self.line_ir, self.line_red
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        """Handle MQTT connection event"""
        if rc == 0:
            self.log('Connected to MQTT broker!', 'success')
            self.update_status(True)
            client.subscribe(MQTT_CONFIG['topic'])
            self.log(f"Subscribed to: {MQTT_CONFIG['topic']}", 'success')
        else:
            error_messages = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            error_msg = error_messages.get(rc, f"Unknown error code {rc}")
            self.log(f'Connection failed: {error_msg}', 'error')
            self.update_status(False)
    
    def on_disconnect(self, client, userdata, rc, properties=None):
        """Handle MQTT disconnection event"""
        if rc == 0:
            self.log('Disconnected from MQTT broker (clean)', 'info')
        else:
            self.log(f'Unexpected disconnection (code {rc})', 'error')
        self.update_status(False)
    
    def connect_mqtt(self):
        """Initialize and connect MQTT client"""
        self.log('Initializing MQTT client...', 'info')
        
        # Create client with version compatibility
        try:
            # For paho-mqtt 2.0+
            self.mqtt_client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=MQTT_CONFIG['client_id']
            )
        except AttributeError:
            # Fallback for paho-mqtt 1.x
            self.mqtt_client = mqtt.Client(MQTT_CONFIG['client_id'])
        
        # Set authentication
        self.mqtt_client.username_pw_set(MQTT_CONFIG['username'], MQTT_CONFIG['password'])
        
        # Configure TLS/SSL
        try:
            self.mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)
            self.log('TLS configured (secure mode)', 'info')
        except Exception as e:
            self.log(f'TLS setup warning: {str(e)}, trying fallback...', 'info')
            try:
                # Fallback: less strict TLS
                self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
                self.mqtt_client.tls_insecure_set(True)
                self.log('TLS configured (insecure mode)', 'info')
            except Exception as e2:
                self.log(f'TLS fallback error: {str(e2)}', 'error')
        
        # Set callbacks
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        
        # Connect in separate thread to prevent UI blocking
        def connect_thread():
            try:
                self.log(f'Connecting to {MQTT_CONFIG["broker"]}:{MQTT_CONFIG["port"]}...', 'info')
                self.mqtt_client.connect(MQTT_CONFIG['broker'], MQTT_CONFIG['port'], 60)
                self.mqtt_client.loop_start()
            except Exception as e:
                self.log(f'Connection error: {str(e)}', 'error')
                self.log('Retrying in 5 seconds...', 'info')
                self.root.after(5000, self.connect_mqtt)
        
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()
    
    def on_closing(self):
        """Handle window close event"""
        self.log('Shutting down...', 'info')
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = HeartbeatDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == '__main__':
    main()