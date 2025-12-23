# UIA-App Docker Guide

## Version 1.0.0

> ⚠️ **DISCLAIMER**: This is NOT an official Palo Alto Networks product. This is an independent, community-developed testing tool. Use at your own risk.

This guide covers running UIA-App in Docker for testing Palo Alto Networks User-ID Agent functionality.

## Quick Start

```bash
# Pull the image
docker pull your-repo/uia-app:1.0.0

# Run with certificate volume
docker run -d \
  --name uia-app \
  -p 8000:8000 \
  -v uia-certs:/app/certs \
  your-repo/uia-app:1.0.0
```

Open http://localhost:8000 in your browser.

## Features in v1.0.0

- **IP-User Mapping**: Single and bulk (up to 100K entries) with progress tracking
- **Dynamic Address Groups (DAG)**: Register/unregister IP tags
- **Dynamic User Groups (DUG)**: Register/unregister user tags
- **Certificate Management**:
  - Generate fresh PKI (Root CA, Server Cert, Client Cert)
  - Upload custom enterprise certificates
  - Download certs for UIA Agent configuration

## Certificate Setup

### Option A: Generate Fresh PKI (Recommended for Testing)

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
    image: your-repo/uia-app:1.0.0
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
docker build -t uia-app:1.0.0 .

# Run it
docker run -p 8000:8000 -v uia-certs:/app/certs uia-app:1.0.0
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

## Changelog

### v1.0.0
- Initial release
- IP-User mapping (single + bulk)
- DAG/DUG management
- Certificate generation (PEM bundle format)
- Rate limiting (2s pause per 1000 entries)
- Progress tracking with stop capability
