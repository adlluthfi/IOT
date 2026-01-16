import React, { useState, useEffect, useRef } from 'react';
import mqtt from 'mqtt';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { InfluxDB, Point } from '@influxdata/influxdb-client';
import './App.css';

// --- KONFIGURASI INFLUXDB ---
const INFLUX_CONFIG = {
  url: 'http://localhost:8181',
  token: '-J9sz2t8MprPQedPJSNg-ZYXF153_YEAVfrgOE29OBIyrLINFp_JZuwD4Ql0QoJwHqD_05H9hM_TIyn6g_UXVw==',
  org: 'my-org',
  bucket: 'max30100',
  timeout: 10000 // Timeout 10 detik
};

const influxDB = new InfluxDB({ 
  url: INFLUX_CONFIG.url, 
  token: INFLUX_CONFIG.token,
  timeout: INFLUX_CONFIG.timeout
});

const queryApi = influxDB.getQueryApi(INFLUX_CONFIG.org);

function App() {
  const [heartRate, setHeartRate] = useState(0);
  const [spo2, setSpo2] = useState(0);
  const [status, setStatus] = useState('Disconnected');
  const [connected, setConnected] = useState(false);
  const [chartData, setChartData] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [alerts, setAlerts] = useState([]);
  
  // Advanced health metrics
  const [heartRateVariability, setHeartRateVariability] = useState(0);
  const [healthScore, setHealthScore] = useState(100);
  const [riskLevel, setRiskLevel] = useState('Low');
  const [anomalyDetected, setAnomalyDetected] = useState(false);
  
  // Historical data states
  const [historicalData, setHistoricalData] = useState([]);
  const [anomalyZones, setAnomalyZones] = useState([]); // Tambahkan state untuk anomaly zones
  const [dataStats, setDataStats] = useState({
    totalRecords: 0,
    avgHeartRate: 0,
    avgSpO2: 0,
    minHeartRate: 0,
    maxHeartRate: 0,
    minSpO2: 0,
    maxSpO2: 0,
    lastSync: null,
    anomalyCount: 0, // Tambahkan counter anomali
    anomalyPeriods: [] // Tambahkan periode anomali
  });
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [timeRange, setTimeRange] = useState('1h'); // 1h, 24h, 7d
  
  // Log data states
  const [logData, setLogData] = useState([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [logTimeRange, setLogTimeRange] = useState('1h');
  const [currentPage, setCurrentPage] = useState(1);
  const logsPerPage = 50;
  
  // Pattern detection
  const heartRateHistory = useRef([]);
  const spo2History = useRef([]);
  const alertHistory = useRef([]);
  const clientRef = useRef(null);
  const writeApiRef = useRef(null); // Tambahkan ref untuk writeApi

  const mqttConfig = {
    broker: 'wss://91c95e4b1fc04b6f9eb2e90b69199494.s1.eu.hivemq.cloud:8884/mqtt',
    username: 'hivemq.webclient.1763790949177',
    password: '16J#HVlkg?D5N0.jbi%L',
    topics: {
      heartrate: 'health/heartrate',
      spo2: 'health/spo2',
      status: 'health/status'
    }
  };

  // --- SEMUA LOGIKA ANALISIS ASLI ANDA ---
  const detectAdvancedAnomalies = (hr, sp) => {
    const newAlerts = [];
    const timestamp = new Date().toLocaleTimeString();
    
    heartRateHistory.current.push(hr);
    spo2History.current.push(sp);
    
    if (heartRateHistory.current.length > 60) {
      heartRateHistory.current.shift();
      spo2History.current.shift();
    }

    if (heartRateHistory.current.length < 3) return newAlerts;

    const recentHR = heartRateHistory.current.slice(-10);
    const trend = calculateTrend(recentHR);
    
    if (trend.isIncreasing && trend.slope > 2) {
      newAlerts.push({ id: Date.now(), type: 'trend', severity: 'warning', message: `📈 TREND NAIK: Konsisten (${trend.slope.toFixed(1)} BPM/m)`, timestamp, recommendation: 'Istirahat dan minum air' });
    } else if (trend.isDecreasing && trend.slope < -2) {
      newAlerts.push({ id: Date.now() + 1, type: 'trend', severity: 'warning', message: `📉 TREND TURUN: Konsisten (${Math.abs(trend.slope).toFixed(1)} BPM/m)`, timestamp, recommendation: 'Pastikan kondisi stabil' });
    }

    const hrv = calculateHRV(heartRateHistory.current.slice(-10));
    setHeartRateVariability(hrv);
    
    if (hrv < 10 && hr > 70) {
      newAlerts.push({ id: Date.now() + 2, type: 'hrv', severity: 'medium', message: `⚡ HRV RENDAH: ${hrv.toFixed(1)} - Stres/Lelah`, timestamp, recommendation: 'Teknik pernapasan dalam' });
    }

    if (hr > 110 && sp < 92) {
      newAlerts.push({ id: Date.now() + 3, type: 'critical', severity: 'critical', message: `🚨 KRITIS: HR ${hr} + SpO2 ${sp}%`, timestamp, recommendation: 'HUBUNGI 119' });
      setAnomalyDetected(true);
    }

    const arrhythmia = detectArrhythmia(heartRateHistory.current.slice(-20));
    if (arrhythmia.detected) {
      newAlerts.push({ id: Date.now() + 4, type: 'arrhythmia', severity: 'high', message: `💔 ARITMIA: Detak tidak teratur (${arrhythmia.irregularityScore.toFixed(1)}%)`, timestamp, recommendation: 'Konsultasi dokter kardiologi' });
    }

    const recentSpO2 = spo2History.current.slice(-10);
    const spo2Trend = calculateTrend(recentSpO2);
    if (spo2Trend.isDecreasing && sp < 94) {
      newAlerts.push({ id: Date.now() + 5, type: 'hypoxia', severity: 'high', message: `🫁 HIPOKSIA: SpO2 turun ke ${sp}%`, timestamp, recommendation: 'Duduk tegak, buka jendela' });
    }

    const score = calculateHealthScore(hr, sp, hrv, arrhythmia.irregularityScore);
    setHealthScore(score);
    setRiskLevel(calculateRiskLevel(score, newAlerts));

    return newAlerts;
  };

  const calculateTrend = (data) => {
    if (data.length < 2) return { isIncreasing: false, isDecreasing: false, slope: 0 };
    const n = data.length;
    const xMean = (n - 1) / 2;
    const yMean = average(data);
    let num = 0, den = 0;
    for (let i = 0; i < n; i++) {
      num += (i - xMean) * (data[i] - yMean);
      den += (i - xMean) ** 2;
    }
    const slope = num / den;
    return { isIncreasing: slope > 0.5, isDecreasing: slope < -0.5, slope };
  };

  const calculateHRV = (data) => {
    if (data.length < 2) return 0;
    let sumSq = 0;
    for (let i = 1; i < data.length; i++) {
      const diff = data[i] - data[i - 1];
      sumSq += diff * diff;
    }
    return Math.sqrt(sumSq / (data.length - 1));
  };

  const detectArrhythmia = (data) => {
    if (data.length < 5) return { detected: false, irregularityScore: 0 };
    const diffs = [];
    for (let i = 1; i < data.length; i++) diffs.push(Math.abs(data[i] - data[i - 1]));
    const avgDiff = average(diffs);
    const irregular = diffs.filter(d => d > avgDiff * 2).length;
    const score = (irregular / diffs.length) * 100;
    return { detected: score > 30, irregularityScore: score };
  };

  const calculateHealthScore = (hr, sp, hrv, arrScore) => {
    let score = 100;
    if (hr > 100 || hr < 60) score -= 20;
    if (sp < 95) score -= 20;
    if (hrv < 20) score -= 10;
    if (arrScore > 20) score -= 20;
    return Math.max(0, score);
  };

  const calculateRiskLevel = (score, alerts) => {
    if (score < 50 || alerts.some(a => a.severity === 'critical')) return 'Critical';
    if (score < 75) return 'High';
    if (score < 85) return 'Medium';
    return 'Low';
  };

  const average = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;

  // --- EFFECT UNTUK MQTT & INFLUXDB ---
  useEffect(() => {
    if (clientRef.current) {
      console.log('⚠️ Client already exists, skipping connection');
      return;
    }

    console.log('🔌 Attempting to connect to MQTT broker...');
    console.log('📊 Initializing InfluxDB WriteApi...');
    
    // Inisialisasi writeApi dengan error handling
    try {
      writeApiRef.current = influxDB.getWriteApi(INFLUX_CONFIG.org, INFLUX_CONFIG.bucket, 'ns', {
        batchSize: 1,
        flushInterval: 0,
        maxRetries: 3,
        maxRetryDelay: 1000,
        exponentialBase: 2
      });
      
      writeApiRef.current.useDefaultTags({source: 'dashboard'});
      console.log('✅ WriteApi initialized successfully');
      console.log('📋 Config:', {
        url: INFLUX_CONFIG.url,
        org: INFLUX_CONFIG.org,
        bucket: INFLUX_CONFIG.bucket
      });
    } catch (err) {
      console.error('❌ Failed to initialize WriteApi:', err);
    }
    
    const client = mqtt.connect(mqttConfig.broker, {
      username: mqttConfig.username,
      password: mqttConfig.password,
      reconnectPeriod: 5000,
      connectTimeout: 30000,
      clean: true,
      keepalive: 60,
      clientId: 'health_dashboard_' + Math.random().toString(16).substr(2, 8),
      rejectUnauthorized: false,
      protocol: 'wss',
      protocolVersion: 4,
    });

    clientRef.current = client;

    client.on('connect', () => {
      console.log('✅ MQTT Connected successfully');
      setConnected(true);
      setStatus('Connected');
      setAnomalyDetected(false);
      
      // Pastikan writeApi sudah ready
      if (!writeApiRef.current) {
        console.warn('⚠️ WriteApi not initialized during connect, initializing now...');
        try {
          writeApiRef.current = influxDB.getWriteApi(INFLUX_CONFIG.org, INFLUX_CONFIG.bucket, 'ns', {
            batchSize: 1,
            flushInterval: 0,
            maxRetries: 3,
            maxRetryDelay: 1000,
            exponentialBase: 2
          });
          writeApiRef.current.useDefaultTags({source: 'dashboard'});
          console.log('✅ WriteApi initialized on connect');
        } catch (err) {
          console.error('❌ Failed to initialize WriteApi on connect:', err);
        }
      }
      
      Object.values(mqttConfig.topics).forEach(topic => {
        client.subscribe(topic, { qos: 1 }, (err) => {
          if (err) {
            console.error(`❌ Failed to subscribe to ${topic}:`, err);
          } else {
            console.log(`📡 Subscribed to: ${topic}`);
          }
        });
      });
    });

    client.on('reconnect', () => {
      console.log('🔄 Attempting to reconnect...');
      setStatus('Reconnecting...');
    });

    client.on('message', async (topic, message) => {
      const val = parseFloat(message.toString());
      console.log(`📨 Received: ${topic} = ${val}`);
      
      if (isNaN(val)) {
        console.warn(`⚠️ Invalid value received: ${message.toString()}`);
        return;
      }
      
      const timestamp = new Date().toLocaleTimeString();

      // --- LOGIKA WRITE INFLUXDB (DIPERBAIKI) ---
      try {
        const field = topic.split('/').pop();
        
        if (!field || (field !== 'heartrate' && field !== 'spo2')) {
          console.error(`❌ Invalid field name: ${field}`);
          return;
        }

        // Cek dan reinitialize writeApi jika perlu
        if (!writeApiRef.current) {
          console.warn('⚠️ WriteApi not available, initializing...');
          try {
            writeApiRef.current = influxDB.getWriteApi(INFLUX_CONFIG.org, INFLUX_CONFIG.bucket, 'ns', {
              batchSize: 1,
              flushInterval: 0,
              maxRetries: 3,
              maxRetryDelay: 1000,
              exponentialBase: 2
            });
            writeApiRef.current.useDefaultTags({source: 'dashboard'});
            console.log('✅ WriteApi reinitialized');
          } catch (initErr) {
            console.error('❌ Failed to reinitialize WriteApi:', initErr);
            return;
          }
        }

        console.log(`📝 Writing to InfluxDB: ${field} = ${val}`);
        
        const point = new Point('health_metrics')
          .tag('device', 'ESP32-S3')
          .tag('location', 'home')
          .floatField(field, val)
          .timestamp(new Date());
        
        writeApiRef.current.writePoint(point);
        
        // Flush dengan timeout
        const flushPromise = writeApiRef.current.flush();
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Flush timeout')), 5000)
        );
        
        await Promise.race([flushPromise, timeoutPromise])
          .then(() => {
            console.log(`✅ Written to InfluxDB: ${field} = ${val}`);
          })
          .catch(err => {
            console.error('❌ InfluxDB flush error:', err);
            
            // Reinitialize jika closed atau error
            if (err.message && (err.message.includes('closed') || err.message.includes('timeout'))) {
              console.warn('⚠️ Reinitializing WriteApi due to error...');
              try {
                writeApiRef.current = influxDB.getWriteApi(INFLUX_CONFIG.org, INFLUX_CONFIG.bucket, 'ns', {
                  batchSize: 1,
                  flushInterval: 0,
                  maxRetries: 3,
                  maxRetryDelay: 1000,
                  exponentialBase: 2
                });
                writeApiRef.current.useDefaultTags({source: 'dashboard'});
                console.log('✅ WriteApi reinitialized after error');
              } catch (reinitErr) {
                console.error('❌ Failed to reinitialize WriteApi:', reinitErr);
              }
            }
          });
          
      } catch (err) {
        console.error('❌ InfluxDB write error:', err);
        console.error('Error details:', {
          message: err.message,
          name: err.name,
          stack: err.stack
        });
      }

      if (topic === mqttConfig.topics.heartrate) {
        setHeartRate(val);
        setLastUpdate(timestamp);
        
        setSpo2(currentSpO2 => {
          console.log(`💓 HR: ${val}, SpO2: ${currentSpO2}`);
          const newAlerts = detectAdvancedAnomalies(val, currentSpO2);
          
          if (newAlerts.length > 0) {
            setAlerts(prev => [...newAlerts, ...prev].slice(0, 10));
            alertHistory.current.push(...newAlerts);
          }
          
          setChartData(prevData => {
            const newData = [...prevData, { 
              time: timestamp, 
              heartRate: val, 
              spo2: currentSpO2,
              healthScore: healthScore
            }];
            console.log(`📊 Chart data updated: ${newData.length} points`);
            return newData.slice(-30);
          });
          
          return currentSpO2;
        });
        
      } else if (topic === mqttConfig.topics.spo2) {
        setSpo2(val);
        console.log(`🫁 SpO2 updated: ${val}`);
        
        setChartData(prevData => {
          if (prevData.length > 0) {
            const updated = [...prevData];
            updated[updated.length - 1] = { ...updated[updated.length - 1], spo2: val };
            console.log(`📊 Chart updated with SpO2: ${val}`);
            return updated;
          }
          return prevData;
        });
        
      } else if (topic === mqttConfig.topics.status) {
        setStatus(message.toString());
      }
    });

    client.on('error', (err) => {
      console.error('❌ MQTT Error:', err);
      setStatus('Error: ' + err.message);
      setConnected(false);
    });

    client.on('close', () => {
      console.log('⚠️ MQTT Connection closed');
      setConnected(false);
      setStatus('Disconnected');
    });

    client.on('offline', () => {
      console.log('📴 MQTT Client offline');
      setConnected(false);
      setStatus('Offline');
    });

    client.on('end', () => {
      console.log('🔚 MQTT Connection ended');
    });

    return () => {
      console.log('🔌 Cleaning up MQTT connection');
      
      // Cleanup MQTT
      if (clientRef.current) {
        clientRef.current.removeAllListeners();
        clientRef.current.end(true);
        clientRef.current = null;
      }
      
      // Cleanup WriteApi
      if (writeApiRef.current) {
        writeApiRef.current.flush()
          .then(() => {
            console.log('✅ Final flush completed');
            return writeApiRef.current.close();
          })
          .then(() => {
            console.log('✅ WriteApi closed successfully');
            writeApiRef.current = null;
          })
          .catch(err => {
            console.error('❌ Error during cleanup:', err);
            writeApiRef.current = null;
          });
      }
    };
  }, []); // Hapus dependency yang menyebabkan re-render

  // Fungsi untuk detect anomaly zones dalam data
  const detectAnomalyZones = (data) => {
    const zones = [];
    let currentZone = null;
    
    data.forEach((point, index) => {
      const hr = point.heartRate || 0;
      const sp = point.spo2 || 0;
      
      // Kriteria anomali
      const isAnomalous = 
        (hr > 100 || hr < 60) || 
        (sp < 95) || 
        (hr > 110 && sp < 92);
      
      if (isAnomalous) {
        if (!currentZone) {
          // Mulai zone baru
          currentZone = {
            start: point.time,
            startIndex: index,
            severity: 'warning',
            reasons: []
          };
        }
        
        // Tambahkan alasan anomali
        if (hr > 110 && sp < 92) {
          currentZone.severity = 'critical';
          currentZone.reasons.push('Critical: High HR + Low SpO2');
        } else if (hr > 100) {
          currentZone.severity = currentZone.severity === 'critical' ? 'critical' : 'high';
          currentZone.reasons.push('High Heart Rate');
        } else if (hr < 60) {
          currentZone.severity = currentZone.severity === 'critical' ? 'critical' : 'high';
          currentZone.reasons.push('Low Heart Rate');
        } else if (sp < 95) {
          currentZone.severity = currentZone.severity === 'critical' ? 'critical' : 'medium';
          currentZone.reasons.push('Low SpO2');
        }
      } else {
        if (currentZone) {
          // Tutup zone
          currentZone.end = data[index - 1].time;
          currentZone.endIndex = index - 1;
          currentZone.reasons = [...new Set(currentZone.reasons)]; // Remove duplicates
          zones.push(currentZone);
          currentZone = null;
        }
      }
    });
    
    // Tutup zone terakhir jika masih terbuka
    if (currentZone) {
      currentZone.end = data[data.length - 1].time;
      currentZone.endIndex = data.length - 1;
      currentZone.reasons = [...new Set(currentZone.reasons)];
      zones.push(currentZone);
    }
    
    return zones;
  };

  // Custom shape untuk highlight anomaly zones
  const AnomalyZone = ({ zone, xScale, chartHeight }) => {
    if (!xScale) return null;
    
    const x1 = xScale(zone.startIndex);
    const x2 = xScale(zone.endIndex);
    const width = x2 - x1;
    
    const colors = {
      critical: 'rgba(255, 71, 87, 0.2)',
      high: 'rgba(255, 165, 2, 0.15)',
      medium: 'rgba(255, 211, 42, 0.1)',
      warning: 'rgba(112, 161, 255, 0.1)'
    };
    
    return (
      <rect
        x={x1}
        y={0}
        width={width}
        height={chartHeight}
        fill={colors[zone.severity]}
        stroke={colors[zone.severity].replace('0.2', '0.5').replace('0.15', '0.5').replace('0.1', '0.5')}
        strokeWidth={2}
        strokeDasharray="5,5"
      />
    );
  };

  // Fungsi untuk fetch log data dari InfluxDB
  const fetchLogData = async (range = '1h') => {
    setLoadingLogs(true);
    try {
      const fluxQuery = `
        from(bucket: "${INFLUX_CONFIG.bucket}")
          |> range(start: -${range})
          |> filter(fn: (r) => r._measurement == "health_metrics")
          |> filter(fn: (r) => r._field == "heartrate" or r._field == "spo2")
          |> sort(columns: ["_time"], desc: true)
      `;

      console.log('🔍 Querying Logs from InfluxDB:', fluxQuery);

      const logs = [];

      await queryApi.queryRows(fluxQuery, {
        next(row, tableMeta) {
          const o = tableMeta.toObject(row);
          logs.push({
            time: new Date(o._time).toLocaleString('id-ID', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            }),
            timestamp: new Date(o._time).getTime(),
            field: o._field === 'heartrate' ? 'Heart Rate' : 'SpO2',
            value: o._value.toFixed(1),
            unit: o._field === 'heartrate' ? 'BPM' : '%',
            status: o._field === 'heartrate' 
              ? (o._value > 100 ? '⚠️ High' : o._value < 60 ? '⚠️ Low' : '✅ Normal')
              : (o._value < 95 ? '⚠️ Low' : '✅ Normal')
          });
        },
        error(error) {
          console.error('❌ InfluxDB Log Query Error:', error);
          setLoadingLogs(false);
        },
        complete() {
          console.log('✅ Log query completed:', logs.length, 'records');
          setLogData(logs);
          setLoadingLogs(false);
          setCurrentPage(1);
        }
      });
    } catch (error) {
      console.error('❌ Error fetching log data:', error);
      setLoadingLogs(false);
    }
  };

  // Fungsi untuk query data dari InfluxDB (UPDATE)
  const fetchHistoricalData = async (range = '1h') => {
    setLoadingHistory(true);
    try {
      const fluxQuery = `
        from(bucket: "${INFLUX_CONFIG.bucket}")
          |> range(start: -${range})
          |> filter(fn: (r) => r._measurement == "health_metrics")
          |> filter(fn: (r) => r._field == "heartrate" or r._field == "spo2")
          |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
          |> yield(name: "mean")
      `;

      console.log('🔍 Querying InfluxDB:', fluxQuery);

      const data = [];
      const heartRateData = [];
      const spo2Data = [];

      await queryApi.queryRows(fluxQuery, {
        next(row, tableMeta) {
          const o = tableMeta.toObject(row);
          data.push(o);
          
          if (o._field === 'heartrate') {
            heartRateData.push(o._value);
          } else if (o._field === 'spo2') {
            spo2Data.push(o._value);
          }
        },
        error(error) {
          console.error('❌ InfluxDB Query Error:', error);
          setLoadingHistory(false);
        },
        complete() {
          console.log('✅ Query completed:', data.length, 'records');
          
          // Format data untuk chart
          const formattedData = [];
          const grouped = {};
          
          data.forEach(item => {
            const time = new Date(item._time).toLocaleTimeString();
            if (!grouped[time]) {
              grouped[time] = { time };
            }
            if (item._field === 'heartrate') {
              grouped[time].heartRate = item._value;
            } else if (item._field === 'spo2') {
              grouped[time].spo2 = item._value;
            }
          });
          
          Object.values(grouped).forEach(item => formattedData.push(item));
          
          setHistoricalData(formattedData);
          
          // Detect anomaly zones
          const zones = detectAnomalyZones(formattedData);
          setAnomalyZones(zones);
          console.log('🔍 Detected anomaly zones:', zones);
          
          // Hitung statistik
          if (heartRateData.length > 0 && spo2Data.length > 0) {
            setDataStats({
              totalRecords: data.length,
              avgHeartRate: (heartRateData.reduce((a, b) => a + b, 0) / heartRateData.length).toFixed(1),
              avgSpO2: (spo2Data.reduce((a, b) => a + b, 0) / spo2Data.length).toFixed(1),
              minHeartRate: Math.min(...heartRateData).toFixed(1),
              maxHeartRate: Math.max(...heartRateData).toFixed(1),
              minSpO2: Math.min(...spo2Data).toFixed(1),
              maxSpO2: Math.max(...spo2Data).toFixed(1),
              lastSync: new Date().toLocaleString(),
              anomalyCount: zones.length,
              anomalyPeriods: zones
            });
          }
          
          setLoadingHistory(false);
        },
      });
    } catch (error) {
      console.error('❌ Error fetching historical data:', error);
      setLoadingHistory(false);
    }
  };

  // Fungsi untuk export data ke CSV
  const exportToCSV = () => {
    if (historicalData.length === 0) {
      alert('Tidak ada data untuk di-export');
      return;
    }

    const csv = [
      ['Timestamp', 'Heart Rate (BPM)', 'SpO2 (%)'],
      ...historicalData.map(row => [
        row.time,
        row.heartRate || '',
        row.spo2 || ''
      ])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `health_data_${new Date().toISOString()}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  // Load data saat component mount
  useEffect(() => {
    fetchHistoricalData(timeRange);
  }, [timeRange]);

  // --- TAMPILAN UI ASLI ANDA ---
  return (
    <div className="App">
      <header className="header">
        <h1>🏥 Advanced Health Monitoring Dashboard</h1>
        <div className={`status-badge ${connected ? 'connected' : 'disconnected'}`}>
          <span className="status-dot"></span>{status}
        </div>
      </header>

      <div className="main-layout">
        {/* Sidebar Kiri - Alerts */}
        <aside className="sidebar-left">
          <div className="sidebar-section">
            <h3>🚨 Health Alerts</h3>
            <div className="alerts-sidebar">
              {alerts.length === 0 ? (
                <div className="no-alerts">✅ All Good</div>
              ) : (
                alerts.map(alert => (
                  <div key={alert.id} className={`alert-compact alert-${alert.severity}`}>
                    <div className="alert-compact-header">
                      <span className="alert-icon">
                        {alert.severity === 'critical' && '🚨'}
                        {alert.severity === 'high' && '⚠️'}
                        {alert.severity === 'medium' && '⚡'}
                        {alert.severity === 'warning' && '📊'}
                      </span>
                      <span className="alert-time-compact">{alert.timestamp}</span>
                    </div>
                    <div className="alert-message-compact">{alert.message}</div>
                    {alert.recommendation && (
                      <div className="alert-recommendation-compact">💡 {alert.recommendation}</div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Quick Stats */}
          <div className="sidebar-section quick-stats">
            <h3>📊 Quick Stats</h3>
            <div className="quick-stat-item">
              <span className="quick-stat-label">Health Score</span>
              <span className={`quick-stat-value score-${riskLevel.toLowerCase()}`}>
                {healthScore.toFixed(0)}
              </span>
            </div>
            <div className="quick-stat-item">
              <span className="quick-stat-label">Risk Level</span>
              <span className={`quick-stat-value risk-${riskLevel.toLowerCase()}`}>
                {riskLevel}
              </span>
            </div>
            <div className="quick-stat-item">
              <span className="quick-stat-label">HRV</span>
              <span className="quick-stat-value">{heartRateVariability.toFixed(1)} ms</span>
            </div>
          </div>

          {/* Anomaly Timeline */}
          {anomalyZones.length > 0 && (
            <div className="sidebar-section anomaly-timeline">
              <h3>⚠️ Anomaly Timeline</h3>
              <div className="timeline-list">
                {anomalyZones.map((zone, index) => (
                  <div key={index} className={`timeline-item severity-${zone.severity}`}>
                    <div className="timeline-badge">
                      {zone.severity === 'critical' && '🚨'}
                      {zone.severity === 'high' && '⚠️'}
                      {zone.severity === 'medium' && '⚡'}
                      {zone.severity === 'warning' && '📊'}
                    </div>
                    <div className="timeline-content">
                      <div className="timeline-time">
                        {zone.start} - {zone.end}
                      </div>
                      <div className="timeline-reasons">
                        {zone.reasons.map((reason, i) => (
                          <div key={i} className="timeline-reason">{reason}</div>
                        ))}
                      </div>
                      {zone.severity === 'critical' && (
                        <div className="timeline-recommendation">
                          💊 Segera konsultasi dokter
                        </div>
                      )}
                      {zone.severity === 'high' && (
                        <div className="timeline-recommendation">
                          📞 Hubungi dokter jika berlanjut
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* Main Content */}
        <main className="main-content">
          <div className="container">
            {/* Current Vitals */}
            <div className="vitals-row">
              <div className="vital-card heart-rate-card">
                <div className="vital-icon">❤️</div>
                <div className="vital-info">
                  <h3>Heart Rate</h3>
                  <div className="vital-value">{heartRate.toFixed(1)}</div>
                  <div className="vital-unit">BPM</div>
                </div>
              </div>
              <div className="vital-card spo2-card">
                <div className="vital-icon">🫁</div>
                <div className="vital-info">
                  <h3>SpO2</h3>
                  <div className="vital-value">{spo2.toFixed(1)}</div>
                  <div className="vital-unit">%</div>
                </div>
              </div>
              <div className="vital-card anomaly-card">
                <div className="vital-icon">
                  {anomalyDetected ? '⚠️' : '✅'}
                </div>
                <div className="vital-info">
                  <h3>Status</h3>
                  <div className={`vital-status ${anomalyDetected ? 'detected' : 'normal'}`}>
                    {anomalyDetected ? 'Anomaly' : 'Normal'}
                  </div>
                  {lastUpdate && <div className="vital-update">Updated: {lastUpdate}</div>}
                </div>
              </div>
            </div>

            {/* Real-Time Chart */}
            <div className="chart-container-large">
              <div className="chart-header">
                <h2>📡 Real-Time Monitoring</h2>
                <div className="chart-legend-inline">
                  <span className="legend-item">
                    <span className="legend-dot heart"></span> Heart Rate
                  </span>
                  <span className="legend-item">
                    <span className="legend-dot spo2"></span> SpO2
                  </span>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={400}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorHR" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ff6b6b" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#ff6b6b" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorSpO2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4ecdc4" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#4ecdc4" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                  <XAxis dataKey="time" stroke="#fff" />
                  <YAxis stroke="#fff" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #444' }} 
                    labelStyle={{ color: '#fff' }} 
                  />
                  <Area type="monotone" dataKey="heartRate" stroke="#ff6b6b" fill="url(#colorHR)" name="Heart Rate (BPM)" />
                  <Area type="monotone" dataKey="spo2" stroke="#4ecdc4" fill="url(#colorSpO2)" name="SpO2 (%)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Database Stats */}
            <div className="database-stats">
              <div className="stats-header">
                <h3>📊 Database Statistics ({timeRange})</h3>
                <div className="stats-controls">
                  <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)} className="time-range-select">
                    <option value="1h">Last 1 Hour</option>
                    <option value="24h">Last 24 Hours</option>
                    <option value="7d">Last 7 Days</option>
                    <option value="30d">Last 30 Days</option>
                  </select>
                  <button onClick={() => fetchHistoricalData(timeRange)} className="refresh-btn" disabled={loadingHistory}>
                    {loadingHistory ? '⏳ Loading...' : '🔄 Refresh'}
                  </button>
                  <button onClick={exportToCSV} className="export-btn">
                    📥 Export CSV
                  </button>
                </div>
              </div>
              
              <div className="stats-grid">
                <div className="stat-box">
                  <div className="stat-label">Total Records</div>
                  <div className="stat-value">{dataStats.totalRecords}</div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">Anomaly Periods</div>
                  <div className="stat-value anomaly-count">
                    {dataStats.anomalyCount}
                    {dataStats.anomalyCount > 0 && <span className="stat-warning">⚠️</span>}
                  </div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">Avg Heart Rate</div>
                  <div className="stat-value">{dataStats.avgHeartRate} <span className="stat-unit">BPM</span></div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">Avg SpO2</div>
                  <div className="stat-value">{dataStats.avgSpO2} <span className="stat-unit">%</span></div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">HR Range</div>
                  <div className="stat-value-small">{dataStats.minHeartRate} - {dataStats.maxHeartRate}</div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">SpO2 Range</div>
                  <div className="stat-value-small">{dataStats.minSpO2} - {dataStats.maxSpO2}</div>
                </div>
                <div className="stat-box">
                  <div className="stat-label">Last Sync</div>
                  <div className="stat-value-small">{dataStats.lastSync || 'Never'}</div>
                </div>
              </div>
            </div>

            {/* Historical Chart dengan Anomaly Zones */}
            {historicalData.length > 0 && (
              <div className="chart-container-large">
                <div className="chart-header">
                  <h2>📈 Historical Data with Anomaly Detection</h2>
                  <div className="anomaly-legend">
                    <span className="legend-anomaly critical">🚨 Critical</span>
                    <span className="legend-anomaly high">⚠️ High Risk</span>
                    <span className="legend-anomaly medium">⚡ Medium</span>
                    <span className="legend-anomaly normal">✅ Normal</span>
                  </div>
                </div>
                
                {anomalyZones.length > 0 && (
                  <div className="anomaly-summary">
                    <strong>⚠️ {anomalyZones.length} Anomaly Period(s) Detected</strong>
                    {anomalyZones.some(z => z.severity === 'critical') && (
                      <span className="critical-warning">
                        🚨 Critical periods found - Medical consultation recommended
                      </span>
                    )}
                  </div>
                )}
                
                <ResponsiveContainer width="100%" height={400}>
                  <AreaChart data={historicalData}>
                    <defs>
                      <linearGradient id="colorHR2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ff6b6b" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#ff6b6b" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorSpO22" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#4ecdc4" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#4ecdc4" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    
                    {/* Render anomaly zones sebagai background */}
                    {anomalyZones.map((zone, index) => (
                      <rect
                        key={`zone-${index}`}
                        x={0}
                        y={0}
                        width="100%"
                        height="100%"
                        fill="transparent"
                      />
                    ))}
                    
                    <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                    <XAxis dataKey="time" stroke="#fff" />
                    <YAxis stroke="#fff" />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #444' }} 
                      labelStyle={{ color: '#fff' }}
                      content={({ active, payload, label }) => {
                        if (active && payload && payload.length) {
                          const hr = payload[0].value;
                          const sp = payload[1]?.value;
                          const isAnomaly = (hr > 100 || hr < 60) || (sp < 95);
                          
                          return (
                            <div className="custom-tooltip">
                              <p className="label"><strong>{label}</strong></p>
                              <p style={{color: '#ff6b6b'}}>Heart Rate: {hr} BPM</p>
                              <p style={{color: '#4ecdc4'}}>SpO2: {sp}%</p>
                              {isAnomaly && (
                                <p className="anomaly-indicator">⚠️ Anomaly Detected</p>
                              )}
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Legend />
                    <Area type="monotone" dataKey="heartRate" stroke="#ff6b6b" fill="url(#colorHR2)" name="Heart Rate (BPM)" strokeWidth={2} />
                    <Area type="monotone" dataKey="spo2" stroke="#4ecdc4" fill="url(#colorSpO22)" name="SpO2 (%)" strokeWidth={2} />
                    
                    {/* Reference lines untuk threshold */}
                    <line x1="0" y1="100" x2="100%" y2="100" stroke="#ff6b6b" strokeDasharray="5,5" strokeWidth={1} opacity={0.3} />
                    <line x1="0" y1="95" x2="100%" y2="95" stroke="#4ecdc4" strokeDasharray="5,5" strokeWidth={1} opacity={0.3} />
                  </AreaChart>
                </ResponsiveContainer>
                
                {/* Rekomendasi berdasarkan anomaly */}
                {anomalyZones.length > 0 && (
                  <div className="chart-recommendations">
                    <h4>📋 Medical Recommendations:</h4>
                    <ul>
                      {anomalyZones.some(z => z.severity === 'critical') && (
                        <li className="rec-critical">
                          🚨 <strong>URGENT:</strong> Critical vital signs detected. Immediate medical attention required. Call 119 or visit ER.
                        </li>
                      )}
                      {anomalyZones.some(z => z.severity === 'high') && (
                        <li className="rec-high">
                          ⚠️ <strong>High Risk:</strong> Schedule appointment with cardiologist within 24-48 hours.
                        </li>
                      )}
                      {anomalyZones.some(z => z.reasons.includes('Low SpO2')) && (
                        <li className="rec-medium">
                          🫁 <strong>Oxygen Level:</strong> Consider oxygen therapy consultation if SpO2 remains below 95%.
                        </li>
                      )}
                      <li className="rec-general">
                        📊 <strong>Monitoring:</strong> Continue regular monitoring and maintain activity log for doctor review.
                      </li>
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Log Table Section */}
            <div className="log-table-container">
              <div className="log-header">
                <h2>📋 Data Logs</h2>
                <div className="log-controls">
                  <select value={logTimeRange} onChange={(e) => setLogTimeRange(e.target.value)} className="time-range-select">
                    <option value="1h">Last 1 Hour</option>
                    <option value="24h">Last 24 Hours</option>
                    <option value="7d">Last 7 Days</option>
                    <option value="30d">Last 30 Days</option>
                  </select>
                  <button onClick={() => fetchLogData(logTimeRange)} className="refresh-btn" disabled={loadingLogs}>
                    {loadingLogs ? '⏳ Loading...' : '🔄 Load Logs'}
                  </button>
                </div>
              </div>

              {loadingLogs ? (
                <div className="loading-spinner">
                  <div className="spinner"></div>
                  <p>Loading logs...</p>
                </div>
              ) : logData.length > 0 ? (
                <>
                  <div className="log-info">
                    <p>Total Records: <strong>{logData.length}</strong></p>
                    <p>Page {currentPage} of {Math.ceil(logData.length / logsPerPage)}</p>
                  </div>
                  
                  <div className="table-wrapper">
                    <table className="log-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Timestamp</th>
                          <th>Metric</th>
                          <th>Value</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {logData
                          .slice((currentPage - 1) * logsPerPage, currentPage * logsPerPage)
                          .map((log, index) => (
                            <tr key={`${log.timestamp}-${index}`} className={log.status.includes('⚠️') ? 'warning-row' : ''}>
                              <td>{(currentPage - 1) * logsPerPage + index + 1}</td>
                              <td>{log.time}</td>
                              <td>{log.field}</td>
                              <td>{log.value} {log.unit}</td>
                              <td className={log.status.includes('⚠️') ? 'status-warning' : 'status-normal'}>
                                {log.status}
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  <div className="pagination">
                    <button 
                      onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                      disabled={currentPage === 1}
                      className="pagination-btn"
                    >
                      ← Previous
                    </button>
                    <span className="page-info">
                      Page {currentPage} of {Math.ceil(logData.length / logsPerPage)}
                    </span>
                    <button 
                      onClick={() => setCurrentPage(prev => Math.min(prev + 1, Math.ceil(logData.length / logsPerPage)))}
                      disabled={currentPage >= Math.ceil(logData.length / logsPerPage)}
                      className="pagination-btn"
                    >
                      Next →
                    </button>
                  </div>
                </>
              ) : (
                <div className="no-data">
                  <p>No log data available. Click "Load Logs" to fetch data from database.</p>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
      
      <footer className="footer">
        <p>Advanced AI Health System | Data Stored in InfluxDB</p>
      </footer>
    </div>
  );
}

export default App;