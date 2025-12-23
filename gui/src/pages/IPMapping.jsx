import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Network } from 'lucide-react';
import LogPanel from '../components/LogPanel';

const API_BASE = 'http://localhost:8000';
const STORAGE_KEY = 'uia_ipmapping_form';

export default function IPMapping({ uiaUrl }) {
    const [logs, setLogs] = useState([]);
    const [progress, setProgress] = useState({ current: 0, total: 0, running: false });

    // Load from localStorage on mount
    const loadSaved = () => {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) return JSON.parse(saved);
        } catch { }
        return null;
    };

    const saved = loadSaved();

    // Single mapping form
    const [singleForm, setSingleForm] = useState(saved?.single || {
        ip: '192.168.1.1',
        username: 'domain\\testuser',
        timeout: 3600
    });

    // Bulk mapping form - merge saved with defaults for migration
    const bulkDefaults = { count: 100, userPrefix: 'domain\\\\user', baseIp: '10.0.0.1', timeout: 3600 };
    const [bulkForm, setBulkForm] = useState({ ...bulkDefaults, ...(saved?.bulk || {}) });

    // Save to localStorage when forms change
    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ single: singleForm, bulk: bulkForm }));
    }, [singleForm, bulkForm]);

    // Poll progress and logs
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const [logRes, progressRes] = await Promise.all([
                    axios.get(`${API_BASE}/get-logs`),
                    axios.get(`${API_BASE}/progress`)
                ]);
                setLogs(logRes.data.logs?.reverse() || []);
                setProgress(progressRes.data);
            } catch (e) { }
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    const handleSingleMapping = async (operation) => {
        try {
            await axios.post(`${API_BASE}/single-mapping`, {
                ip: singleForm.ip,
                username: singleForm.username,
                timeout: singleForm.timeout,
                operation,
                uia_url: uiaUrl
            });
        } catch (e) {
            console.error(e);
        }
    };

    const handleBulkMapping = async (operation) => {
        // Immediately set running state before API call
        setProgress(prev => ({ ...prev, running: true, total: bulkForm.count, current: 0 }));
        try {
            await axios.post(`${API_BASE}/bulk-mapping`, {
                count: bulkForm.count,
                user_prefix: bulkForm.userPrefix,
                base_ip: bulkForm.baseIp,
                timeout: bulkForm.timeout,
                operation,
                uia_url: uiaUrl
            });
        } catch (e) {
            console.error(e);
            // Reset running state on error
            setProgress(prev => ({ ...prev, running: false }));
        }
    };

    const handleStop = async () => {
        try {
            await axios.post(`${API_BASE}/stop-mapping`);
        } catch (e) { }
    };

    return (
        <div style={{ padding: '2rem', maxWidth: '900px', margin: '0 auto' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Network size={24} /> IP-User Mapping
            </h2>

            {/* Single Mapping */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: '#f8fafc' }}>Single Mapping</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 100px', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                        <label style={labelStyle}>IP Address</label>
                        <input
                            style={inputStyle}
                            value={singleForm.ip}
                            onChange={e => setSingleForm({ ...singleForm, ip: e.target.value })}
                        />
                    </div>
                    <div>
                        <label style={labelStyle}>Username</label>
                        <input
                            style={inputStyle}
                            value={singleForm.username}
                            onChange={e => setSingleForm({ ...singleForm, username: e.target.value })}
                        />
                    </div>
                    <div>
                        <label style={labelStyle}>Timeout</label>
                        <input
                            type="number"
                            style={inputStyle}
                            value={singleForm.timeout}
                            onChange={e => setSingleForm({ ...singleForm, timeout: parseInt(e.target.value) })}
                        />
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnGreen} onClick={() => handleSingleMapping('login')}>LOGIN</button>
                    <button style={btnRed} onClick={() => handleSingleMapping('logout')}>LOGOUT</button>
                </div>
            </section>

            {/* Bulk Mapping */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: '#f8fafc' }}>Bulk Mapping</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                        <label style={labelStyle}>Total Count</label>
                        <input
                            type="number"
                            style={inputStyle}
                            value={bulkForm.count}
                            onChange={e => setBulkForm({ ...bulkForm, count: parseInt(e.target.value) || 0 })}
                        />
                    </div>
                    <div>
                        <label style={labelStyle}>User Prefix</label>
                        <input
                            style={inputStyle}
                            value={bulkForm.userPrefix}
                            onChange={e => setBulkForm({ ...bulkForm, userPrefix: e.target.value })}
                        />
                    </div>
                    <div>
                        <label style={labelStyle}>Starting IP</label>
                        <input
                            style={inputStyle}
                            value={bulkForm.baseIp}
                            onChange={e => setBulkForm({ ...bulkForm, baseIp: e.target.value })}
                        />
                    </div>
                    <div>
                        <label style={labelStyle}>Timeout (sec)</label>
                        <input
                            type="number"
                            style={inputStyle}
                            value={bulkForm.timeout}
                            onChange={e => setBulkForm({ ...bulkForm, timeout: parseInt(e.target.value) || 3600 })}
                        />
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                        style={{ ...btnGreen, opacity: progress.running ? 0.7 : 1 }}
                        onClick={() => handleBulkMapping('login')}
                        disabled={progress.running}
                    >
                        {progress.running ? `RUNNING... ${progress.current}/${progress.total}` : 'START LOGIN'}
                    </button>
                    <button
                        style={{
                            ...btnOrange,
                            opacity: progress.running ? 1 : 0.5,
                            cursor: progress.running ? 'pointer' : 'not-allowed'
                        }}
                        onClick={handleStop}
                        disabled={!progress.running}
                    >
                        ⏹ STOP
                    </button>
                    <button
                        style={{ ...btnRed, opacity: progress.running ? 0.7 : 1 }}
                        onClick={() => handleBulkMapping('logout')}
                        disabled={progress.running}
                    >
                        LOGOUT ALL
                    </button>
                </div>
            </section>

            <LogPanel logs={logs} progress={progress} />
        </div>
    );
}

const labelStyle = { display: 'block', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' };
const inputStyle = {
    width: '100%',
    padding: '0.5rem',
    background: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '0.375rem',
    color: '#f8fafc',
    fontSize: '0.875rem'
};
const btnGreen = {
    flex: 1,
    padding: '0.75rem',
    background: '#16a34a',
    color: 'white',
    border: 'none',
    borderRadius: '0.375rem',
    fontWeight: 'bold',
    cursor: 'pointer'
};
const btnRed = {
    flex: 1,
    padding: '0.75rem',
    background: '#7f1d1d',
    color: '#fca5a5',
    border: '1px solid #991b1b',
    borderRadius: '0.375rem',
    fontWeight: 'bold',
    cursor: 'pointer'
};
const btnOrange = {
    padding: '0.75rem 1.5rem',
    background: '#ea580c',
    color: 'white',
    border: 'none',
    borderRadius: '0.375rem',
    fontWeight: 'bold'
};
