import tkinter as tk
from tkinter import ttk, messagebox
import paho.mqtt.client as mqtt
import json
import threading
import time
import math
import ssl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

class MPU6500MQTTDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("MPU6500 Real-time 3D Dashboard - MQTT")
        self.root.geometry("1400x900")
        self.root.configure(bg='#1e1e2e')
        
        # MQTT Configuration
        self.mqtt_client = None
        self.connected = False
        self.broker = "91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud"
        self.port = 8883
        self.topic = "mpu6500/sensor/data"
        self.username = "hivemq.webclient.1761741197053"
        self.password = "z*PMdw?YvfF.0G1,a9H2"
        
        # Data storage
        self.current_data = {
            'accel': {'x': 0, 'y': 0, 'z': 0},
            'gyro': {'x': 0, 'y': 0, 'z': 0},
            'temperature': 0,
            'rssi': 0,
            'client_id': 'Unknown'
        }
        
        # UI Variables
        self.setup_ui_variables()
        self.setup_ui()
        
    def setup_ui_variables(self):
        self.accel_vars = {
            'X': tk.StringVar(value="0.000"),
            'Y': tk.StringVar(value="0.000"), 
            'Z': tk.StringVar(value="0.000")
        }
        self.gyro_vars = {
            'X': tk.StringVar(value="0.00"),
            'Y': tk.StringVar(value="0.00"),
            'Z': tk.StringVar(value="0.00")
        }
        self.temp_var = tk.StringVar(value="0.0 °C")
        self.accel_total_var = tk.StringVar(value="0.000 g")
        self.gyro_total_var = tk.StringVar(value="0.00 °/s")
        self.connection_var = tk.StringVar(value="Disconnected")
        self.client_id_var = tk.StringVar(value="Not connected")
        self.rssi_var = tk.StringVar(value="0 dBm")
        self.update_time_var = tk.StringVar(value="Last update: Never")
        
    def setup_ui(self):
        # Configure style
        self.setup_styles()
        
        # Main container
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Header
        self.setup_header(main_container)
        
        # Connection Panel
        self.setup_connection_panel(main_container)
        
        # Main Content
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Left Panel - Sensor Data and Controls
        left_panel = ttk.Frame(content_frame, width=400)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        self.setup_sensor_cards(left_panel)
        self.setup_visual_indicators(left_panel)
        
        # Right Panel - 3D Visualization
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.setup_3d_visualization(right_panel)
        
        # Footer
        self.setup_footer(main_container)
        
        # Initial message
        self.add_log("🚀 System initialized. Ready to connect to MQTT broker.")
        self.add_log("🎯 3D visualization will show real-time orientation")
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Custom.TFrame', background='#2a2d3e')
        style.configure('Title.TLabel', background='#2a2d3e', foreground='white', font=('Arial', 16, 'bold'))
        style.configure('Card.TLabelframe', background='#2a2d3e', foreground='#ff79c6')
        style.configure('Card.TLabelframe.Label', background='#2a2d3e', foreground='#ff79c6', font=('Arial', 11, 'bold'))
        
    def setup_header(self, parent):
        header_frame = ttk.Frame(parent, style='Custom.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(header_frame, 
                               text="🎯 MPU6500 3D REAL-TIME DASHBOARD", 
                               style='Title.TLabel')
        title_label.pack(side=tk.LEFT)
        
        # Connection status
        status_frame = ttk.Frame(header_frame, style='Custom.TFrame')
        status_frame.pack(side=tk.RIGHT)
        
        self.connection_dot = tk.Canvas(status_frame, width=20, height=20, bg='#2a2d3e', highlightthickness=0)
        self.connection_dot.pack(side=tk.LEFT, padx=(0, 8))
        self.draw_connection_dot('red')
        
        ttk.Label(status_frame, 
                 textvariable=self.connection_var, 
                 style='Title.TLabel').pack(side=tk.RIGHT)
        
    def setup_connection_panel(self, parent):
        conn_frame = ttk.LabelFrame(parent, text="🔗 MQTT CONNECTION", style='Card.TLabelframe')
        conn_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Broker info
        broker_frame = ttk.Frame(conn_frame)
        broker_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(broker_frame, text="HiveMQ Cloud Broker:", 
                 font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(broker_frame, 
                 text="91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud:8883",
                 font=('Arial', 10), foreground='#3498db').grid(row=0, column=1, sticky=tk.W, padx=10)
        
        # Buttons
        button_frame = ttk.Frame(conn_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.connect_btn = ttk.Button(button_frame, text="🔌 CONNECT MQTT", 
                                     command=self.toggle_mqtt_connection,
                                     width=15)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="🔍 TEST CONNECTION", 
                  command=self.test_mqtt_connection,
                  width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="🔄 RESET VIEW", 
                  command=self.reset_3d_view,
                  width=12).pack(side=tk.LEFT, padx=5)
        
    def setup_sensor_cards(self, parent):
        # Status Cards
        status_cards_frame = ttk.Frame(parent)
        status_cards_frame.pack(fill=tk.X, pady=(0, 15))
        
        status_cards = [
            ("🌡️ TEMPERATURE", self.temp_var, "#e74c3c"),
            ("📊 TOTAL ACCEL", self.accel_total_var, "#3498db"), 
            ("🔄 TOTAL GYRO", self.gyro_total_var, "#9b59b6"),
            ("📶 WIFI RSSI", self.rssi_var, "#f39c12")
        ]
        
        for i, (title, var, color) in enumerate(status_cards):
            card = tk.Frame(status_cards_frame, bg=color, relief=tk.RAISED, bd=2)
            card.grid(row=0, column=i, sticky='nsew', padx=(0, 5))
            status_cards_frame.columnconfigure(i, weight=1)
            
            inner_frame = tk.Frame(card, bg='#2a2d3e', padx=8, pady=6)
            inner_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            
            ttk.Label(inner_frame, text=title, 
                     font=('Arial', 8, 'bold'), background='#2a2d3e', 
                     foreground='white').pack(anchor=tk.W)
            ttk.Label(inner_frame, textvariable=var, 
                     font=('Courier New', 10, 'bold'), background='#2a2d3e', 
                     foreground='white').pack(anchor=tk.W, pady=(2, 0))
        
        # Sensor Data Cards
        sensor_frame = ttk.Frame(parent)
        sensor_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Accelerometer Card
        accel_frame = ttk.LabelFrame(sensor_frame, text="📈 ACCELEROMETER (g)", style='Card.TLabelframe')
        accel_frame.pack(fill=tk.X, pady=(0, 8))
        
        for axis in ['X', 'Y', 'Z']:
            row_frame = ttk.Frame(accel_frame)
            row_frame.pack(fill=tk.X, padx=10, pady=3)
            
            ttk.Label(row_frame, text=f"Axis {axis}:", 
                     font=('Arial', 9), width=6).pack(side=tk.LEFT)
            value_label = ttk.Label(row_frame, textvariable=self.accel_vars[axis],
                                  font=('Courier New', 10, 'bold'), foreground='#e74c3c')
            value_label.pack(side=tk.RIGHT)
        
        # Gyroscope Card
        gyro_frame = ttk.LabelFrame(sensor_frame, text="🔄 GYROSCOPE (°/s)", style='Card.TLabelframe')
        gyro_frame.pack(fill=tk.X, pady=(0, 8))
        
        for axis in ['X', 'Y', 'Z']:
            row_frame = ttk.Frame(gyro_frame)
            row_frame.pack(fill=tk.X, padx=10, pady=3)
            
            ttk.Label(row_frame, text=f"Axis {axis}:", 
                     font=('Arial', 9), width=6).pack(side=tk.LEFT)
            value_label = ttk.Label(row_frame, textvariable=self.gyro_vars[axis],
                                  font=('Courier New', 10, 'bold'), foreground='#3498db')
            value_label.pack(side=tk.RIGHT)
        
        # Client Info Card
        client_frame = ttk.LabelFrame(sensor_frame, text="🆔 DEVICE INFORMATION", style='Card.TLabelframe')
        client_frame.pack(fill=tk.X)
        
        info_frame = ttk.Frame(client_frame)
        info_frame.pack(fill=tk.X, padx=10, pady=6)
        
        ttk.Label(info_frame, text="Client ID:", font=('Arial', 8)).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(info_frame, textvariable=self.client_id_var, 
                 font=('Courier New', 8), foreground='#2ecc71').grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(info_frame, text="Last Update:", font=('Arial', 8)).grid(row=1, column=0, sticky=tk.W, pady=(2,0))
        ttk.Label(info_frame, textvariable=self.update_time_var, 
                 font=('Courier New', 8), foreground='#f39c12').grid(row=1, column=1, sticky=tk.W, padx=5, pady=(2,0))
        
    def setup_visual_indicators(self, parent):
        visual_frame = ttk.LabelFrame(parent, text="📊 VISUAL INDICATORS", style='Card.TLabelframe')
        visual_frame.pack(fill=tk.BOTH, expand=True)
        
        # Acceleration Magnitude
        magnitude_frame = ttk.Frame(visual_frame)
        magnitude_frame.pack(fill=tk.X, padx=10, pady=8)
        
        ttk.Label(magnitude_frame, text="Acceleration Magnitude:", 
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        
        self.magnitude_canvas = tk.Canvas(magnitude_frame, width=280, height=60, 
                                         bg='#1e1e2e', highlightthickness=0)
        self.magnitude_canvas.pack(pady=3)
        self.draw_magnitude_indicator(0)
        
        # Orientation Help
        help_frame = ttk.Frame(visual_frame)
        help_frame.pack(fill=tk.X, padx=10, pady=5)
        
        help_text = """
3D Visualization Guide:
• Red Arrow: X-axis (Roll)
• Green Arrow: Y-axis (Pitch)  
• Blue Arrow: Z-axis (Yaw)
• Cube shows device orientation
• Colors indicate axis direction
        """
        
        help_label = ttk.Label(help_frame, text=help_text, font=('Arial', 8),
                              background='#2a2d3e', foreground='#bdc3c7', justify=tk.LEFT)
        help_label.pack(anchor=tk.W)
        
    def setup_3d_visualization(self, parent):
        viz_frame = ttk.LabelFrame(parent, text="🎮 3D ORIENTATION VISUALIZATION", style='Card.TLabelframe')
        viz_frame.pack(fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Create matplotlib figure
        self.fig = plt.Figure(figsize=(8, 6), facecolor='#2a2d3e')
        self.ax = self.fig.add_subplot(111, projection='3d')
        
        # Configure plot appearance
        self.ax.set_facecolor('#1e1e2e')
        self.fig.patch.set_facecolor('#2a2d3e')
        
        # Set initial view
        self.ax.set_xlim([-1.5, 1.5])
        self.ax.set_ylim([-1.5, 1.5])
        self.ax.set_zlim([-1.5, 1.5])
        
        # Labels and title
        self.ax.set_xlabel('X', color='white', fontweight='bold')
        self.ax.set_ylabel('Y', color='white', fontweight='bold')
        self.ax.set_zlabel('Z', color='white', fontweight='bold')
        
        # Color the axes
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('red')
        self.ax.yaxis.label.set_color('green')
        self.ax.zaxis.label.set_color('blue')
        
        # Initial coordinate system
        self.draw_coordinate_system()
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, viz_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def draw_coordinate_system(self):
        """Draw the initial coordinate system"""
        # Clear previous drawings
        self.ax.clear()
        
        # Set limits and labels
        self.ax.set_xlim([-1.5, 1.5])
        self.ax.set_ylim([-1.5, 1.5])
        self.ax.set_zlim([-1.5, 1.5])
        self.ax.set_xlabel('X', color='white', fontweight='bold')
        self.ax.set_ylabel('Y', color='white', fontweight='bold')
        self.ax.set_zlabel('Z', color='white', fontweight='bold')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('red')
        self.ax.yaxis.label.set_color('green')
        self.ax.zaxis.label.set_color('blue')
        
        # Draw coordinate axes
        self.ax.quiver(0, 0, 0, 1, 0, 0, color='red', arrow_length_ratio=0.1, linewidth=2, label='X')
        self.ax.quiver(0, 0, 0, 0, 1, 0, color='green', arrow_length_ratio=0.1, linewidth=2, label='Y')
        self.ax.quiver(0, 0, 0, 0, 0, 1, color='blue', arrow_length_ratio=0.1, linewidth=2, label='Z')
        
        # Draw a simple cube using wireframe instead of trisurf
        self.draw_device_cube_simple()
        
        self.ax.legend(facecolor='#2a2d3e', edgecolor='white', labelcolor='white')
        
    def draw_device_cube_simple(self, rotation=None):
        """Draw a simple cube using wireframe - more reliable than trisurf"""
        # Cube vertices
        vertices = np.array([
            [-0.5, -0.5, -0.5],
            [0.5, -0.5, -0.5],
            [0.5, 0.5, -0.5],
            [-0.5, 0.5, -0.5],
            [-0.5, -0.5, 0.5],
            [0.5, -0.5, 0.5],
            [0.5, 0.5, 0.5],
            [-0.5, 0.5, 0.5]
        ])
        
        if rotation is not None:
            # Apply rotation
            vertices = np.dot(vertices, rotation.T)
        
        # Define cube edges
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # bottom face
            [4, 5], [5, 6], [6, 7], [7, 4],  # top face
            [0, 4], [1, 5], [2, 6], [3, 7]   # vertical edges
        ]
        
        # Draw edges
        for edge in edges:
            points = vertices[edge]
            self.ax.plot3D(points[:, 0], points[:, 1], points[:, 2], 'white', alpha=0.8, linewidth=2)
        
        # Draw vertices as points
        self.ax.scatter(vertices[:, 0], vertices[:, 1], vertices[:, 2], c='yellow', s=50, alpha=0.6)
    
    def update_3d_visualization(self, accel_data):
        """Update the 3D visualization based on accelerometer data"""
        self.ax.clear()
        
        # Set limits and labels
        self.ax.set_xlim([-1.5, 1.5])
        self.ax.set_ylim([-1.5, 1.5])
        self.ax.set_zlim([-1.5, 1.5])
        self.ax.set_xlabel('X', color='white', fontweight='bold')
        self.ax.set_ylabel('Y', color='white', fontweight='bold')
        self.ax.set_zlabel('Z', color='white', fontweight='bold')
        self.ax.tick_params(colors='white')
        self.ax.xaxis.label.set_color('red')
        self.ax.yaxis.label.set_color('green')
        self.ax.zaxis.label.set_color('blue')
        
        # Normalize acceleration vector for visualization
        accel = np.array([accel_data['x'], accel_data['y'], accel_data['z']])
        accel_norm = accel / np.linalg.norm(accel) if np.linalg.norm(accel) > 0 else np.array([0, 0, 1])
        
        # Calculate rotation matrix from acceleration (simplified)
        # This is a basic approach - for full orientation you'd need sensor fusion
        z = accel_norm
        x = np.cross([0, 1, 0], z)
        if np.linalg.norm(x) < 0.001:
            x = np.cross([1, 0, 0], z)
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        
        rotation_matrix = np.column_stack([x, y, z])
        
        # Draw coordinate axes with rotation
        self.ax.quiver(0, 0, 0, rotation_matrix[0, 0], rotation_matrix[1, 0], rotation_matrix[2, 0], 
                      color='red', arrow_length_ratio=0.1, linewidth=3, label='X')
        self.ax.quiver(0, 0, 0, rotation_matrix[0, 1], rotation_matrix[1, 1], rotation_matrix[2, 1], 
                      color='green', arrow_length_ratio=0.1, linewidth=3, label='Y')
        self.ax.quiver(0, 0, 0, rotation_matrix[0, 2], rotation_matrix[1, 2], rotation_matrix[2, 2], 
                      color='blue', arrow_length_ratio=0.1, linewidth=3, label='Z')
        
        # Draw device cube with rotation
        self.draw_device_cube_simple(rotation_matrix)
        
        # Add acceleration vector
        self.ax.quiver(0, 0, 0, accel_norm[0], accel_norm[1], accel_norm[2],
                      color='yellow', arrow_length_ratio=0.15, linewidth=4, linestyle='--', 
                      alpha=0.7, label='Acceleration')
        
        self.ax.legend(facecolor='#2a2d3e', edgecolor='white', labelcolor='white')
        self.canvas.draw()
    
    def setup_footer(self, parent):
        footer_frame = ttk.Frame(parent)
        footer_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(footer_frame, 
                 text="ESP32-S3 + MPU6500 | 3D Orientation Dashboard with SSL",
                 font=('Arial', 9), foreground='#95a5a6').pack(side=tk.LEFT)
        
        ttk.Label(footer_frame, 
                 textvariable=self.update_time_var,
                 font=('Arial', 9), foreground='#95a5a6').pack(side=tk.RIGHT)
    
    def draw_connection_dot(self, color):
        self.connection_dot.delete("all")
        self.connection_dot.create_oval(5, 5, 15, 15, fill=color, outline="")
    
    def draw_magnitude_indicator(self, magnitude):
        self.magnitude_canvas.delete("all")
        width = 280
        height = 60
        
        # Draw gauge background
        self.magnitude_canvas.create_rectangle(20, 25, width-20, 45, fill='#34495e', outline='#7f8c8d', width=2)
        
        # Calculate fill width
        fill_width = min(int((magnitude / 3.0) * (width-40)), width-40)
        
        # Color gradient
        if magnitude < 1.0:
            color = '#2ecc71'  # Green
        elif magnitude < 2.0:
            color = '#f39c12'  # Orange
        else:
            color = '#e74c3c'  # Red
            
        if fill_width > 0:
            self.magnitude_canvas.create_rectangle(20, 25, 20 + fill_width, 45, fill=color, outline="")
        
        # Draw scale markers
        for i in range(0, 4):
            x = 20 + (i * (width-40) // 3)
            self.magnitude_canvas.create_line(x, 45, x, 55, fill='#ecf0f1', width=1)
            self.magnitude_canvas.create_text(x, 58, text=f"{i}g", fill='#bdc3c7', font=('Arial', 7))
        
        # Draw current value
        self.magnitude_canvas.create_text(width//2, 15, 
                                         text=f"Current: {magnitude:.3f} g", 
                                         fill='#ecf0f1', font=('Arial', 10, 'bold'))
    
    def add_log(self, message, level='info'):
        # Simple logging (removed the text widget to save space for 3D visualization)
        print(f"[{time.strftime('%H:%M:%S')}] {message}")
    
    # MQTT Callbacks
    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            self.add_log("✅ Successfully connected to HiveMQ Cloud!", 'success')
            client.subscribe(self.topic)
            self.add_log(f"📡 Subscribed to topic: {self.topic}", 'info')
            self.root.after(0, self.update_connection_status)
        else:
            self.add_log(f"❌ Connection failed with code: {rc}", 'error')
    
    def on_mqtt_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            data = json.loads(payload)
            self.current_data = data
            self.root.after(0, self.update_display)
            
        except json.JSONDecodeError as e:
            self.add_log(f"❌ JSON decode error: {str(e)}", 'error')
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        self.connected = False
        self.add_log("🔌 Disconnected from MQTT broker", 'warning')
        self.root.after(0, self.update_connection_status)
    
    def test_mqtt_connection(self):
        self.add_log("Testing SSL connection to HiveMQ Cloud...", 'info')
        try:
            test_client = mqtt.Client()
            test_client.username_pw_set(self.username, self.password)
            test_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
            test_client.connect(self.broker, self.port, 5)
            test_client.disconnect()
            self.add_log("✅ SSL connection test successful!", 'success')
            messagebox.showinfo("Connection Test", "SSL connection to HiveMQ Cloud successful!")
        except Exception as e:
            self.add_log(f"❌ SSL connection failed: {str(e)}", 'error')
            messagebox.showerror("Connection Test", f"Cannot connect to HiveMQ Cloud:\n{str(e)}")
    
    def toggle_mqtt_connection(self):
        if not self.connected:
            self.connect_mqtt()
        else:
            self.disconnect_mqtt()
    
    def connect_mqtt(self):
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.username_pw_set(self.username, self.password)
            self.mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
            
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            
            self.add_log("🔐 Connecting to HiveMQ Cloud with SSL...", 'info')
            self.mqtt_client.connect(self.broker, self.port, 60)
            self.mqtt_client.loop_start()
            
            self.connect_btn.config(text="🔌 DISCONNECT")
            
        except Exception as e:
            self.add_log(f"❌ MQTT connection failed: {str(e)}", 'error')
            messagebox.showerror("MQTT Error", f"Cannot connect to HiveMQ Cloud:\n{str(e)}")
    
    def disconnect_mqtt(self):
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        self.connected = False
        self.connect_btn.config(text="🔌 CONNECT MQTT")
        self.add_log("⏹️ MQTT connection stopped", 'warning')
        self.update_connection_status()
    
    def reset_3d_view(self):
        """Reset the 3D view to default"""
        self.draw_coordinate_system()
        self.canvas.draw()
        self.add_log("🔄 3D view reset to default orientation", 'info')
    
    def update_connection_status(self):
        if self.connected:
            self.connection_var.set("Connected")
            self.draw_connection_dot('#2ecc71')  # Green
        else:
            self.connection_var.set("Disconnected")
            self.draw_connection_dot('#e74c3c')  # Red
    
    def update_display(self):
        data = self.current_data
        
        # Update sensor values
        self.accel_vars['X'].set(f"{data['accel']['x']:.3f}")
        self.accel_vars['Y'].set(f"{data['accel']['y']:.3f}")
        self.accel_vars['Z'].set(f"{data['accel']['z']:.3f}")
        
        self.gyro_vars['X'].set(f"{data['gyro']['x']:.2f}")
        self.gyro_vars['Y'].set(f"{data['gyro']['y']:.2f}")
        self.gyro_vars['Z'].set(f"{data['gyro']['z']:.2f}")
        
        self.temp_var.set(f"{data['temperature']:.1f} °C")
        self.rssi_var.set(f"{data['rssi']} dBm")
        self.client_id_var.set(data['client_id'][:15] + "...")
        
        # Calculate totals
        accel_total = math.sqrt(data['accel']['x']**2 + data['accel']['y']**2 + data['accel']['z']**2)
        gyro_total = math.sqrt(data['gyro']['x']**2 + data['gyro']['y']**2 + data['gyro']['z']**2)
        
        self.accel_total_var.set(f"{accel_total:.3f} g")
        self.gyro_total_var.set(f"{gyro_total:.2f} °/s")
        
        # Update visual indicators
        self.draw_magnitude_indicator(accel_total)
        
        # Update 3D visualization
        self.update_3d_visualization(data['accel'])
        
        # Update connection status
        self.connection_var.set("Connected")
        self.draw_connection_dot('#2ecc71')
        
        # Update timestamp
        self.update_time_var.set(f"Last update: {time.strftime('%H:%M:%S')}")
    
    def on_closing(self):
        self.disconnect_mqtt()
        self.root.destroy()

def main():
    try:
        import paho.mqtt.client as mqtt
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        import numpy as np
    except ImportError as e:
        print(f"Please install required packages: {e}")
        print("Run: pip install paho-mqtt matplotlib numpy")
        return
    
    root = tk.Tk()
    app = MPU6500MQTTDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Center the window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()