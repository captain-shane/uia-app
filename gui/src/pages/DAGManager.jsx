import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Tags } from 'lucide-react';
import LogPanel from '../components/LogPanel';

const API_BASE = 'http://localhost:8000';

export default function DAGManager({ uiaUrl }) {
    const [logs, setLogs] = useState([]);
    const [progress, setProgress] = useState({ current: 0, total: 0, running: false });

    // Single entry
    const [singleIp, setSingleIp] = useState('192.168.1.1');
    const [singleTag, setSingleTag] = useState('Quarantine');

    // Bulk entries
    const [bulkIps, setBulkIps] = useState('');
    const [bulkTag, setBulkTag] = useState('Quarantine');

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

    const handleSingle = async (action) => {
        try {
            await axios.post(`${API_BASE}/update-ip-tags`, {
                items: [{ ip: singleIp, tag: singleTag }],
                action,
                uia_url: uiaUrl
            });
        } catch (e) {
            console.error(e);
        }
    };

    const handleBulk = async (action) => {
        const ips = bulkIps.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
        if (!ips.length) return;
        try {
            await axios.post(`${API_BASE}/update-ip-tags`, {
                items: ips.map(ip => ({ ip, tag: bulkTag })),
                action,
                uia_url: uiaUrl
            });
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div style={{ padding: '2rem', maxWidth: '900px', margin: '0 auto' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Tags size={24} /> Dynamic Address Groups (DAG)
            </h2>

            {/* Single Entry */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: '#f8fafc' }}>Single IP Tag</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                        <label style={labelStyle}>IP Address</label>
                        <input style={inputStyle} value={singleIp} onChange={e => setSingleIp(e.target.value)} />
                    </div>
                    <div>
                        <label style={labelStyle}>Tag Name</label>
                        <input style={inputStyle} value={singleTag} onChange={e => setSingleTag(e.target.value)} />
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnGreen} onClick={() => handleSingle('register')}>REGISTER</button>
                    <button style={btnRed} onClick={() => handleSingle('unregister')}>UNREGISTER</button>
                </div>
            </section>

            {/* Bulk Entry */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: '#f8fafc' }}>Bulk IP Tags</h3>
                <div style={{ marginBottom: '1rem' }}>
                    <label style={labelStyle}>Tag Name</label>
                    <input style={{ ...inputStyle, marginBottom: '0.5rem' }} value={bulkTag} onChange={e => setBulkTag(e.target.value)} />
                </div>
                <div style={{ marginBottom: '1rem' }}>
                    <label style={labelStyle}>IP Addresses (one per line or comma-separated)</label>
                    <textarea
                        style={{ ...inputStyle, height: '100px', resize: 'vertical' }}
                        value={bulkIps}
                        onChange={e => setBulkIps(e.target.value)}
                        placeholder="192.168.1.10&#10;192.168.1.11&#10;192.168.1.12"
                    />
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnGreen} onClick={() => handleBulk('register')}>REGISTER ALL</button>
                    <button style={btnRed} onClick={() => handleBulk('unregister')}>UNREGISTER ALL</button>
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
