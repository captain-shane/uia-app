import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

export default function Header({ status, uiaUrl, isRunning, onStop }) {
    const location = useLocation();

    const handleEmergencyStop = async () => {
        try {
            await axios.post(`${API_BASE}/emergency-stop`);
            if (onStop) onStop();
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <header style={{
            background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
            borderBottom: '1px solid #334155',
            padding: '1rem 2rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            position: 'sticky',
            top: 0,
            zIndex: 100
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
                <h1 style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#f8fafc' }}>UIA TOOL</h1>
                <nav style={{ display: 'flex', gap: '0.5rem' }}>
                    <Link to="/" style={navStyle(location.pathname === '/')}>IP Mapping</Link>
                    <Link to="/dag" style={navStyle(location.pathname === '/dag')}>DAG</Link>
                    <Link to="/dug" style={navStyle(location.pathname === '/dug')}>DUG</Link>
                    <Link to="/settings" style={navStyle(location.pathname === '/settings')}>⚙ Settings</Link>
                </nav>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <button
                    onClick={handleEmergencyStop}
                    disabled={!isRunning}
                    style={{
                        background: isRunning ? '#dc2626' : '#4b5563',
                        color: 'white',
                        padding: '0.5rem 1rem',
                        borderRadius: '0.375rem',
                        fontWeight: 'bold',
                        border: 'none',
                        cursor: isRunning ? 'pointer' : 'not-allowed',
                        opacity: isRunning ? 1 : 0.5
                    }}
                >
                    🛑 STOP ALL
                </button>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        background: status === 'online' ? '#22c55e' : '#ef4444'
                    }}></div>
                    <span style={{ fontSize: '0.875rem', color: '#94a3b8' }}>{uiaUrl}</span>
                </div>
                <span style={{ fontSize: '0.65rem', color: '#64748b' }}>Not an official PANW product</span>
            </div>
        </header>
    );
}

function navStyle(active) {
    return {
        padding: '0.5rem 1rem',
        borderRadius: '0.375rem',
        background: active ? '#3b82f6' : 'transparent',
        color: active ? 'white' : '#94a3b8',
        textDecoration: 'none',
        fontWeight: '500',
        fontSize: '0.875rem'
    };
}
