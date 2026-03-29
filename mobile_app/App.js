import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, Alert, SafeAreaView } from 'react-native';
import * as Location from 'expo-location';
import axios from 'axios';

// LOCAL SERVER IP
const API_URL = 'http://10.186.17.1:8000';
// We simulate the agent ID. In a real app, this comes from Login.
const AGENT_ID = 2; 

// Add Localtunnel bypass headers globally
axios.defaults.headers.common['Bypass-Tunnel-Reminder'] = 'true';
axios.defaults.headers.common['User-Agent'] = 'NightwatchApp/1.0';

export default function App() {
  const [isTracking, setIsTracking] = useState(false);
  const [location, setLocation] = useState(null);
  const [agentStatus, setAgentStatus] = useState('offline');

  // Request permissions on mount
  useEffect(() => {
    (async () => {
      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission to access location was denied');
        return;
      }
    })();
  }, []);

  // Tracking loop
  useEffect(() => {
    let interval;
    if (isTracking) {
      interval = setInterval(async () => {
        try {
          let loc = await Location.getCurrentPositionAsync({
            accuracy: Location.Accuracy.High,
          });
          setLocation(loc);

          // Ping server
          await axios.put(`${API_URL}/agents/${AGENT_ID}/location`, {
            lat: loc.coords.latitude,
            lon: loc.coords.longitude
          });
          
          console.log("Pinged location: ", loc.coords.latitude, loc.coords.longitude);

          // Get my status from server
          const agentsRes = await axios.get(`${API_URL}/agents/`);
          const me = agentsRes.data.find(a => a.id === AGENT_ID);
          if (me) {
            setAgentStatus(me.status);
            // If the server changed me to busy, I have a dispatch!
            if (me.status === 'busy') {
              // Could trigger local notification here
            }
          }

        } catch (error) {
          console.error("Error pinging API", error.message);
        }
      }, 5000); // Ping every 5 seconds
    } else {
      clearInterval(interval);
    }
    return () => clearInterval(interval);
  }, [isTracking]);

  const toggleTracking = async () => {
    if (!isTracking) {
      // Starting shift
      try {
        await axios.put(`${API_URL}/agents/${AGENT_ID}/status`, { status: 'available' });
        setAgentStatus('available');
        setIsTracking(true);
      } catch (e) {
        Alert.alert("Error connecting to server", e.message);
      }
    } else {
      // Ending shift
      try {
        await axios.put(`${API_URL}/agents/${AGENT_ID}/status`, { status: 'offline' });
        setAgentStatus('offline');
        setIsTracking(false);
      } catch (e) {
        Alert.alert("Error connecting to server", e.message);
      }
    }
  };

  const getStatusColor = () => {
    if (agentStatus === 'available') return '#10b981';
    if (agentStatus === 'busy') return '#ef4444';
    return '#64748b';
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerText}>🚓 NIGHTWATCH AGENT</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.agentName}>Agent ID: {AGENT_ID}</Text>
        <Text style={styles.statusText}>
          Status: <Text style={{ color: getStatusColor(), fontWeight: 'bold' }}>{agentStatus.toUpperCase()}</Text>
        </Text>
        {location && (
          <Text style={styles.locationText}>
            Lat: {location.coords.latitude.toFixed(5)} {"\n"}
            Lon: {location.coords.longitude.toFixed(5)}
          </Text>
        )}
      </View>

      {agentStatus === 'busy' && (
        <View style={styles.alertCard}>
          <Text style={styles.alertText}>🚨 DISPATCH ASSIGNED 🚨</Text>
          <Text style={styles.alertSub}>Head to destination immediately.</Text>
        </View>
      )}

      <TouchableOpacity 
        style={[styles.button, isTracking ? styles.buttonStop : styles.buttonStart]}
        onPress={toggleTracking}
      >
        <Text style={styles.buttonText}>{isTracking ? "END SHIFT" : "START SHIFT"}</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 20, justifyContent: 'center' },
  header: { alignItems: 'center', marginBottom: 40 },
  headerText: { fontSize: 24, fontWeight: 'bold', color: '#60a5fa' },
  card: { backgroundColor: '#1e293b', padding: 20, borderRadius: 10, marginBottom: 20, borderWidth: 1, borderColor: '#334155' },
  agentName: { fontSize: 18, color: '#f8fafc', marginBottom: 10 },
  statusText: { fontSize: 16, color: '#94a3b8', marginBottom: 10 },
  locationText: { fontSize: 14, color: '#64748b', fontStyle: 'italic' },
  alertCard: { backgroundColor: '#7f1d1d', padding: 20, borderRadius: 10, marginBottom: 20, alignItems: 'center' },
  alertText: { fontSize: 18, fontWeight: 'bold', color: '#fca5a5' },
  alertSub: { fontSize: 14, color: '#fecaca', marginTop: 5 },
  button: { padding: 20, borderRadius: 10, alignItems: 'center' },
  buttonStart: { backgroundColor: '#10b981' },
  buttonStop: { backgroundColor: '#ef4444' },
  buttonText: { color: 'white', fontSize: 18, fontWeight: 'bold' }
});