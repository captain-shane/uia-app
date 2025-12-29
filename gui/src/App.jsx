import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import Header from './components/Header';
import IPMapping from './pages/IPMapping';
import DAGManager from './pages/DAGManager';
import DUGManager from './pages/DUGManager';
import SettingsPage from './pages/SettingsPage';

// Use relative path for API calls to support Docker port mapping
// Vite proxy will handle this in development
const API_BASE = '';

function App() {
  const [status, setStatus] = useState('offline');
  const [uiaUrl, setUiaUrl] = useState('127.0.0.1:5006');
  const [isRunning, setIsRunning] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsUrl, setSettingsUrl] = useState('127.0.0.1:5006');
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await axios.get(`${API_BASE}/status`);
        setStatus('online');
        setIsRunning(res.data.mapping_active);
        if (res.data.config_verified) {
          setUiaUrl(res.data.uia_url);
          setSettingsUrl(res.data.uia_url);
        }
      } catch (e) {
        setStatus('offline');
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleTestConnection = async () => {
    setTesting(true);
    try {
      await axios.post(`${API_BASE}/test-connection`, { uia_url: settingsUrl });
      setUiaUrl(settingsUrl);
      setShowSettings(false);
    } catch (e) {
      alert('Connection failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setTesting(false);
    }
  };

  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh', background: '#0f172a', color: '#f8fafc' }}>
        <Header
          status={status}
          uiaUrl={uiaUrl}
          isRunning={isRunning}
          onStop={() => setIsRunning(false)}
        />

        {/* Settings Modal - Removed, now using dedicated page */}

        <Routes>
          <Route path="/" element={<IPMapping uiaUrl={uiaUrl} />} />
          <Route path="/dag" element={<DAGManager uiaUrl={uiaUrl} />} />
          <Route path="/dug" element={<DUGManager uiaUrl={uiaUrl} />} />
          <Route path="/settings" element={<SettingsPage uiaUrl={uiaUrl} onUrlChange={setUiaUrl} />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
