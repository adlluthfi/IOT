let client;
let heartRate = 0;
let spo2Value = 0;

// Hardcoded credentials
const MQTT_CONFIG = {
    broker: '91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud',
    username: 'hivemq.webclient.1763790949177',
    password: '16J#HVlkg?D5N0.jbi%L'
};

document.addEventListener('deviceready', function() {
    console.log('Device ready');
    addMessage('✓ App ready');
    
    // Auto connect
    setTimeout(function() {
        connect();
    }, 500);
}, false);

function connect() {
    const broker = MQTT_CONFIG.broker;
    const username = MQTT_CONFIG.username;
    const password = MQTT_CONFIG.password;

    const clientId = 'health_mobile_' + Math.random().toString(16).substr(2, 8);
    const url = 'wss://' + broker + ':8884/mqtt';
    
    addMessage('🔄 Connecting...');

    if (client && client.connected) {
        client.end(true);
    }

    try {
        client = mqtt.connect(url, {
            clientId: clientId,
            username: username,
            password: password,
            reconnectPeriod: 1000,
            clean: true
        });

        client.on('connect', function() {
            addMessage('✅ Connected to MQTT broker');
            document.getElementById('status').className = 'status connected';
            document.getElementById('status').innerHTML = '<span class="status-dot"></span>Connected';
            document.getElementById('loginSection').classList.add('hidden');
            document.getElementById('mainSection').classList.remove('hidden');

            // Subscribe to topics
            client.subscribe('health/heartrate');
            client.subscribe('health/spo2');
            client.subscribe('health/status');
            client.subscribe('health/control/response');
            
            addMessage('📡 Subscribed to health topics');
        });

        client.on('message', function(topic, message) {
            const msg = message.toString();
            const timestamp = new Date().toLocaleTimeString();
            
            addMessage('📨 ' + topic + ': ' + msg);
            
            if (topic === 'health/heartrate') {
                heartRate = parseFloat(msg);
                document.getElementById('heartRate').textContent = heartRate.toFixed(1);
                document.getElementById('lastUpdate').textContent = timestamp;
                
                // Update status
                if (heartRate >= 60 && heartRate <= 100) {
                    document.getElementById('hrStatus').textContent = 'Normal';
                } else if (heartRate > 0) {
                    document.getElementById('hrStatus').textContent = 'Alert';
                } else {
                    document.getElementById('hrStatus').textContent = 'No Data';
                }
            } 
            else if (topic === 'health/spo2') {
                spo2Value = parseFloat(msg);
                document.getElementById('spo2').textContent = spo2Value.toFixed(1);
                
                // Update status
                if (spo2Value >= 95) {
                    document.getElementById('spo2Status').textContent = 'Normal';
                } else if (spo2Value > 0) {
                    document.getElementById('spo2Status').textContent = 'Low';
                } else {
                    document.getElementById('spo2Status').textContent = 'No Data';
                }
            }
            else if (topic === 'health/status') {
                document.getElementById('deviceStatus').textContent = msg;
            }
            else if (topic === 'health/control/response') {
                document.getElementById('sensorState').textContent = msg;
            }
        });

        client.on('error', function(err) {
            addMessage('❌ Connection error: ' + err.message);
        });

        client.on('close', function() {
            addMessage('⚠️ Connection closed');
            document.getElementById('status').className = 'status disconnected';
            document.getElementById('status').innerHTML = '<span class="status-dot"></span>Disconnected';
        });

    } catch (err) {
        addMessage('❌ Error: ' + err.message);
        alert('Connection failed: ' + err.message);
    }
}

function turnOnSensor() {
    if (!client || !client.connected) {
        alert('Not connected to MQTT broker');
        return;
    }
    
    client.publish('health/control', 'ON', function(err) {
        if (!err) {
            addMessage('✅ Sensor ON command sent');
            document.getElementById('sensorState').textContent = 'Turning ON...';
        } else {
            addMessage('❌ Failed to send command');
        }
    });
}

function turnOffSensor() {
    if (!client || !client.connected) {
        alert('Not connected to MQTT broker');
        return;
    }
    
    client.publish('health/control', 'OFF', function(err) {
        if (!err) {
            addMessage('✅ Sensor OFF command sent');
            document.getElementById('sensorState').textContent = 'Turning OFF...';
        } else {
            addMessage('❌ Failed to send command');
        }
    });
}

function disconnect() {
    if (client) {
        client.end(true);
        addMessage('🔌 Disconnected');
        document.getElementById('loginSection').classList.remove('hidden');
        document.getElementById('mainSection').classList.add('hidden');
        document.getElementById('status').className = 'status disconnected';
        document.getElementById('status').innerHTML = '<span class="status-dot"></span>Disconnected';
    }
}

function addMessage(msg) {
    const messagesDiv = document.getElementById('messages');
    const messageEl = document.createElement('div');
    messageEl.className = 'message';
    const timestamp = new Date().toLocaleTimeString();
    messageEl.textContent = '[' + timestamp + '] ' + msg;
    messagesDiv.appendChild(messageEl);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function clearMessages() {
    document.getElementById('messages').innerHTML = '';
    addMessage('🗑️ Log cleared');
}
