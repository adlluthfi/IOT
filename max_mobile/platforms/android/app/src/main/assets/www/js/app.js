let client;

document.addEventListener('deviceready', function() {
    console.log('Device ready');
    addMessage('✓ App ready');
    
    // Check if mqtt library loaded
    if (typeof mqtt === 'undefined') {
        addMessage('❌ MQTT library not loaded!');
        alert('ERROR: MQTT library not found!\n\nPlease ensure mqtt.min.js exists in www/js folder');
    } else {
        addMessage('✓ MQTT library loaded');
    }
}, false);

function connect() {
    // Check MQTT library
    if (typeof mqtt === 'undefined') {
        alert('MQTT library not loaded! Check console for errors.');
        addMessage('❌ MQTT library missing');
        return;
    }

    const broker = document.getElementById('broker').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (!broker || !username || !password) {
        alert('Please fill all fields');
        return;
    }

    const clientId = 'mqtt_mobile_' + Math.random().toString(16).substr(2, 8);
    const url = 'wss://' + broker + ':8884/mqtt';
    
    addMessage('🔄 Connecting...');
    addMessage('URL: ' + url);
    addMessage('Client: ' + clientId);

    // Disconnect old client if exists
    if (client && client.connected) {
        addMessage('Closing old connection...');
        client.end(true);
    }

    try {
        client = mqtt.connect(url, {
            clientId: clientId,
            username: username,
            password: password,
            protocol: 'wss',
            clean: true,
            reconnectPeriod: 0, // Disable auto-reconnect
            connectTimeout: 30000,
            keepalive: 60, // Increase to 60 seconds
            protocolVersion: 4,
            resubscribe: false
        });

        client.on('connect', function() {
            addMessage('✅ CONNECTED!');
            addMessage('Status: Online - Connection stable');
            updateStatus('connected', 'Connected ✓');
            document.getElementById('loginSection').classList.add('hidden');
            document.getElementById('mainSection').classList.remove('hidden');
            
            // Subscribe to system topic to keep connection alive
            client.subscribe('$SYS/broker/uptime', { qos: 0 });
        });

        client.on('reconnect', function() {
            addMessage('🔄 Reconnecting...');
            updateStatus('disconnected', 'Reconnecting...');
        });

        client.on('close', function() {
            addMessage('⚠️ Connection closed');
            updateStatus('disconnected', 'Closed');
            // Show login again
            document.getElementById('loginSection').classList.remove('hidden');
            document.getElementById('mainSection').classList.add('hidden');
        });

        client.on('offline', function() {
            addMessage('❌ Client went offline');
            updateStatus('disconnected', 'Offline');
        });

        client.on('error', function(error) {
            addMessage('❌ Error: ' + error.toString());
            updateStatus('disconnected', 'Error');
        });

        client.on('message', function(topic, message) {
            addMessage('📨 [' + topic + ']: ' + message.toString());
        });

    } catch (e) {
        addMessage('❌ Exception: ' + e.message);
        alert('Connection error: ' + e.message);
    }
}

function publish() {
    if (!client || !client.connected) {
        alert('Not connected!');
        addMessage('❌ Not connected - cannot publish');
        return;
    }

    const topic = document.getElementById('pubTopic').value;
    const messageText = document.getElementById('pubMessage').value;

    if (!topic || !messageText) {
        alert('Please enter topic and message');
        return;
    }

    addMessage('📤 Publishing to [' + topic + ']...');

    client.publish(topic, messageText, { qos: 1, retain: false }, function(error) {
        if (error) {
            addMessage('❌ Publish error: ' + error);
            alert('Publish failed: ' + error);
        } else {
            addMessage('✅ Published to [' + topic + ']: ' + messageText);
            document.getElementById('pubMessage').value = '';
        }
    });
}

function subscribe() {
    if (!client || !client.connected) {
        alert('Not connected!');
        return;
    }

    const topic = document.getElementById('subTopic').value;

    if (!topic) {
        alert('Please enter topic');
        return;
    }

    client.subscribe(topic, { qos: 1 }, function(error) {
        if (error) {
            addMessage('❌ Subscribe error: ' + error);
        } else {
            addMessage('✓ Subscribed to [' + topic + ']');
        }
    });
}

function disconnect() {
    if (client) {
        client.end();
        updateStatus('disconnected', 'Disconnected');
        document.getElementById('loginSection').classList.remove('hidden');
        document.getElementById('mainSection').classList.add('hidden');
        addMessage('Disconnected');
    }
}

function updateStatus(status, text) {
    const statusEl = document.getElementById('status');
    statusEl.className = 'status ' + status;
    statusEl.textContent = text;
}

function addMessage(msg) {
    const time = new Date().toLocaleTimeString();
    const messagesDiv = document.getElementById('messages');
    const messageEl = document.createElement('div');
    messageEl.className = 'message';
    messageEl.textContent = '[' + time + '] ' + msg;
    messagesDiv.insertBefore(messageEl, messagesDiv.firstChild);
    
    // Keep last 50 messages
    while (messagesDiv.children.length > 50) {
        messagesDiv.removeChild(messagesDiv.lastChild);
    }
}

function clearMessages() {
    document.getElementById('messages').innerHTML = '';
}
