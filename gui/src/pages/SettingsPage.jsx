import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, Shield, Upload, Download, CheckCircle, XCircle } from 'lucide-react';
import LogPanel from '../components/LogPanel';

const API_BASE = '';

export default function SettingsPage({ uiaUrl, onUrlChange }) {
    const [logs, setLogs] = useState([]);
    const [certStatus, setCertStatus] = useState({ has_certs: false });
    const [loading, setLoading] = useState(false);
    const [password, setPassword] = useState('changeme');
    const [settingsUrl, setSettingsUrl] = useState(uiaUrl);
    const [testResult, setTestResult] = useState(null);

    // File upload refs
    const [clientCrt, setClientCrt] = useState(null);
    const [clientKey, setClientKey] = useState(null);
    const [rootCa, setRootCa] = useState(null);

    useEffect(() => {
        checkCertStatus();
        const interval = setInterval(async () => {
            try {
                const logRes = await axios.get(`${API_BASE}/get-logs`);
                setLogs(logRes.data.logs?.reverse() || []);
            } catch { }
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    const checkCertStatus = async () => {
        try {
            const res = await axios.get(`${API_BASE}/cert-status`);
            setCertStatus(res.data);
        } catch { }
    };

    const handleGeneratePKI = async () => {
        setLoading(true);
        try {
            await axios.post(`${API_BASE}/generate-pki`, { password });
            await checkCertStatus();
            alert(`PKI Generated!\n\nPassword: ${password}\n\nDownload rootCA.crt and uia-server-bundle.pem below.`);
        } catch (e) {
            alert('Error: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const handleUploadCerts = async () => {
        if (!clientCrt || !clientKey || !rootCa) {
            alert('Please select all 3 files');
            return;
        }
        setLoading(true);
        try {
            const formData = new FormData();
            formData.append('client_crt', clientCrt);
            formData.append('client_key', clientKey);
            formData.append('root_ca', rootCa);
            await axios.post(`${API_BASE}/upload-certs`, formData);
            await checkCertStatus();
            alert('Certificates uploaded successfully!');
        } catch (e) {
            alert('Error: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const handleTestConnection = async () => {
        setLoading(true);
        setTestResult(null);
        try {
            await axios.post(`${API_BASE}/test-connection`, { uia_url: settingsUrl });
            setTestResult('success');
            if (onUrlChange) onUrlChange(settingsUrl);
        } catch (e) {
            setTestResult('error');
            alert('Connection failed: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: '2rem', maxWidth: '900px', margin: '0 auto' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Settings size={24} /> Settings & Certificates
            </h2>

            {/* Certificate Status */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Shield size={18} /> Certificate Status
                </h3>
                <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
                    <StatusBadge label="Client Cert" ok={certStatus.has_client} />
                    <StatusBadge label="Root CA" ok={certStatus.has_ca} />
                    <StatusBadge label="Server Cert" ok={certStatus.has_server} />
                </div>
            </section>

            {/* Connection Settings */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem', color: '#f8fafc' }}>UIA Agent Connection</h3>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end' }}>
                    <div style={{ flex: 1 }}>
                        <label style={labelStyle}>UIA URL (host:port)</label>
                        <input
                            style={inputStyle}
                            value={settingsUrl}
                            onChange={e => setSettingsUrl(e.target.value)}
                            placeholder="127.0.0.1:5006"
                        />
                    </div>
                    <button
                        style={{ ...btnBlue, opacity: loading ? 0.7 : 1 }}
                        onClick={handleTestConnection}
                        disabled={loading}
                    >
                        {testResult === 'success' ? '✓ Connected' : testResult === 'error' ? '✗ Failed' : 'Test & Save'}
                    </button>
                </div>
            </section>

            {/* Generate PKI */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '0.5rem', color: '#f8fafc' }}>Option A: Generate Fresh PKI</h3>
                <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '1rem' }}>
                    Creates Root CA, Server Cert (for UIA Agent), and Client Cert (for this app)
                </p>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', marginBottom: '1rem' }}>
                    <div style={{ flex: 1 }}>
                        <label style={labelStyle}>Password (for UIA Server Key)</label>
                        <input
                            style={inputStyle}
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            placeholder="changeme"
                        />
                    </div>
                    <button
                        style={{ ...btnGreen, opacity: loading ? 0.7 : 1 }}
                        onClick={handleGeneratePKI}
                        disabled={loading}
                    >
                        {loading ? 'Generating...' : '🔐 Generate PKI'}
                    </button>
                </div>
                {certStatus.has_server && (
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <a href={`${API_BASE}/download-cert/rootCA.crt`} download style={downloadLink}>
                            <Download size={14} /> rootCA.crt
                        </a>
                        <a href={`${API_BASE}/download-cert/uia-server-bundle.pem`} download style={downloadLink}>
                            <Download size={14} /> uia-server-bundle.pem
                        </a>
                    </div>
                )}
            </section>

            {/* Upload Custom Certs */}
            <section style={{ background: '#1e293b', padding: '1.5rem', borderRadius: '0.5rem', marginBottom: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '0.5rem', color: '#f8fafc' }}>Option B: Upload Custom Certificates</h3>
                <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '1rem' }}>
                    For enterprise PKI - upload your own client cert to connect to existing UIA Agent
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                    <FileInput label="Client Cert (.crt)" onChange={setClientCrt} file={clientCrt} />
                    <FileInput label="Client Key (.key)" onChange={setClientKey} file={clientKey} />
                    <FileInput label="Root CA (.crt)" onChange={setRootCa} file={rootCa} />
                </div>
                <button
                    style={{ ...btnBlue, opacity: loading ? 0.7 : 1 }}
                    onClick={handleUploadCerts}
                    disabled={loading}
                >
                    <Upload size={14} style={{ marginRight: '0.5rem' }} />
                    {loading ? 'Uploading...' : 'Upload Certificates'}
                </button>
            </section>

            <LogPanel logs={logs} progress={{ current: 0, total: 0, running: false }} />
        </div>
    );
}

function StatusBadge({ label, ok }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {ok ? <CheckCircle size={16} color="#22c55e" /> : <XCircle size={16} color="#ef4444" />}
            <span style={{ color: ok ? '#22c55e' : '#ef4444', fontSize: '0.875rem' }}>{label}</span>
        </div>
    );
}

function FileInput({ label, onChange, file }) {
    return (
        <div>
            <label style={labelStyle}>{label}</label>
            <input
                type="file"
                onChange={e => onChange(e.target.files[0])}
                style={{ ...inputStyle, padding: '0.4rem', fontSize: '0.75rem' }}
            />
            {file && <span style={{ fontSize: '0.7rem', color: '#22c55e' }}>✓ {file.name}</span>}
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
    padding: '0.75rem 1.5rem',
    background: '#16a34a',
    color: 'white',
    border: 'none',
    borderRadius: '0.375rem',
    fontWeight: 'bold',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center'
};
const btnBlue = {
    padding: '0.75rem 1.5rem',
    background: '#3b82f6',
    color: 'white',
    border: 'none',
    borderRadius: '0.375rem',
    fontWeight: 'bold',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center'
};
const downloadLink = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.25rem',
    padding: '0.5rem 1rem',
    background: '#334155',
    color: '#f8fafc',
    borderRadius: '0.375rem',
    textDecoration: 'none',
    fontSize: '0.875rem'
};
