import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ShieldCheck } from 'lucide-react';
import LogPanel from '../components/LogPanel';

const API_BASE = 'http://localhost:8000';

export default function DUGManager({ uiaUrl }) {
    const [logs, setLogs] = useState([]);
    const [progress, setProgress] = useState({ current: 0, total: 0, running: false });

    // Single entry
    const [singleUser, setSingleUser] = useState('domain\\testuser');
    const [singleTag, setSingleTag] = useState('Finance');

    // Bulk entries
    const [bulkUsers, setBulkUsers] = useState('');
    const [bulkTag, setBulkTag] = useState('Finance');

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
            await axios.post(`${API_BASE}/update-tags`, {
                items: [{ user: singleUser, tag: singleTag }],
                action,
                uia_url: uiaUrl
            });
        } catch (e) {
            console.error(e);
        }
    };

    const handleBulk = async (action) => {
        const users = bulkUsers.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
        if (!users.length) return;
        try {
            await axios.post(`${API_BASE}/update-tags`, {
                items: users.map(user => ({ user, tag: bulkTag })),
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
                <ShieldCheck size={24} /> Dynamic User Groups (DUG)
            </h2>

            {/* Single Entry */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: '#f8fafc' }}>Single User Tag</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                    <div>
                        <label style={labelStyle}>Username</label>
                        <input style={inputStyle} value={singleUser} onChange={e => setSingleUser(e.target.value)} />
                    </div>
                    <div>
                        <label style={labelStyle}>Tag Name</label>
                        <input style={inputStyle} value={singleTag} onChange={e => setSingleTag(e.target.value)} />
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnGreen} onClick={() => handleSingle('register-user')}>REGISTER</button>
                    <button style={btnRed} onClick={() => handleSingle('unregister-user')}>UNREGISTER</button>
                </div>
            </section>

            {/* Bulk Entry */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: '#f8fafc' }}>Bulk User Tags</h3>
                <div style={{ marginBottom: '1rem' }}>
                    <label style={labelStyle}>Tag Name</label>
                    <input style={{ ...inputStyle, marginBottom: '0.5rem' }} value={bulkTag} onChange={e => setBulkTag(e.target.value)} />
                </div>
                <div style={{ marginBottom: '1rem' }}>
                    <label style={labelStyle}>Usernames (one per line or comma-separated)</label>
                    <textarea
                        style={{ ...inputStyle, height: '100px', resize: 'vertical' }}
                        value={bulkUsers}
                        onChange={e => setBulkUsers(e.target.value)}
                        placeholder="domain\alice&#10;domain\bob&#10;domain\charlie"
                    />
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button style={btnGreen} onClick={() => handleBulk('register-user')}>REGISTER ALL</button>
                    <button style={btnRed} onClick={() => handleBulk('unregister-user')}>UNREGISTER ALL</button>
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
