# UIA-App Docker Guide

## Version 1.0.1

> ⚠️ **DISCLAIMER**: This is NOT an official Palo Alto Networks product. This is an independent, community-developed testing tool. Use at your own risk.

This guide covers running UIA-App in Docker for testing Palo Alto Networks User-ID Agent functionality.

## Quick Start

```bash
# Pull the image
docker pull captainshane/uia-app:latest

# Run with certificate volume
docker run -d \
  --name uia-app \
  -p 8000:8000 \
  -v uia-certs:/app/certs \
  captainshane/uia-app:latest
```

Open http://localhost:8000 in your browser.

## Features

- **IP-User Mapping**: Single and bulk (up to 100K entries) with progress tracking
- **Dynamic Address Groups (DAG)**: Register/unregister IP tags
- **Dynamic User Groups (DUG)**: Register/unregister user tags
- **mTLS Certificate Setup**:
  - Generate certs for testing environments
  - Upload custom enterprise certificates
  - Secure communication between this app and UIA Agent

## mTLS Certificate Setup

### Option A: Generate Certs (Recommended for Testing)

1. Open http://localhost:8000/settings
2. Set a password for the server key
3. Click **"🔐 Generate PKI"**
4. Download:
   - `rootCA.crt` → Import into Windows Trusted Root store on UIA Agent host
   - `uia-server-bundle.pem` → Configure in UIA Agent service

### Option B: Use Existing Enterprise PKI

1. Open http://localhost:8000/settings
2. In "Upload Custom Certificates" section, upload:
   - Client Certificate (.crt)
   - Client Private Key (.key)
   - Root CA (.crt)
3. Click **"Upload Certificates"**

## Volume Mounts

| Mount | Purpose |
|-------|---------|
| `/app/certs` | Stores generated/uploaded certificates |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CERT_DIR` | `certs` | Directory for certificate storage |

## Docker Compose

```yaml
version: '3.8'
services:
  uia-app:
    image: captainshane/uia-app:latest
    container_name: uia-app
    ports:
      - "8000:8000"
    volumes:
      - uia-certs:/app/certs
    restart: unless-stopped

volumes:
  uia-certs:
```

## Building Locally

```bash
# Build the image
docker build -t uia-app:latest .

# Run it
docker run -p 8000:8000 -v uia-certs:/app/certs uia-app:latest
```

## UIA Agent Configuration

After generating or uploading certificates:

1. **On UIA Agent Windows Host:**
   - Import `rootCA.crt` into Local Computer → Trusted Root Certification Authorities
   - Configure UIA Agent service with `uia-server-bundle.pem`
   - Password is the one you set during PKI generation

2. **In UIA-App:**
   - Go to Settings
   - Enter UIA Agent URL (e.g., `192.168.1.100:5006`)
   - Click "Test & Save"

## Related Documentation

- [**UIA Agent Setup Guide**](docs/UIA_AGENT_SETUP.md) - Step-by-step Windows UIA Agent configuration
- [**Walkthrough & Demo**](docs/WALKTHROUGH.md) - Feature demonstration with video
- [**Main README**](README.md) - Project overview and API reference

## Changelog

### v1.0.1
- **Fixed:** TLS compatibility for legacy UIA Agents (TLS 1.0/1.1 support)
- **Fixed:** PKI generation error 500 (attribute naming bug)
- **Improved:** SSL context with `OP_LEGACY_SERVER_CONNECT` for broader compatibility

### v1.0.0
- Initial release
- IP-User mapping (single + bulk)
- DAG/DUG management
- Certificate generation (PEM bundle format)
- Rate limiting (2s pause per 1000 entries)
- Progress tracking with stop capability
