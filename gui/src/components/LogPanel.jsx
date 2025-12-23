import React from 'react';

export default function LogPanel({ logs, progress }) {
    return (
        <div style={{
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '0.5rem',
            padding: '1rem',
            marginTop: '1rem'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <h3 style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#3b82f6' }}>
                    ACTIVITY LOG
                </h3>
                {progress.running && (
                    <span style={{ fontSize: '0.875rem', color: '#22c55e', fontWeight: 'bold' }}>
                        {progress.current} of {progress.total}
                    </span>
                )}
            </div>
            <div style={{
                background: '#020617',
                borderRadius: '0.375rem',
                padding: '0.5rem',
                height: '150px',
                overflowY: 'auto',
                fontFamily: 'monospace',
                fontSize: '0.75rem'
            }}>
                {logs.length === 0 ? (
                    <span style={{ color: '#475569', fontStyle: 'italic' }}>Waiting for activity...</span>
                ) : (
                    logs.slice(0, 15).map((log, i) => (
                        <div key={i} style={{
                            color: log.includes('[ERROR]') ? '#ef4444' : log.includes('SUCCESS') || log.includes('completed') ? '#22c55e' : '#94a3b8',
                            marginBottom: '2px'
                        }}>
                            {log}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
