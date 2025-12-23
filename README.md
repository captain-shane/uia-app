# UIA-App - User-ID Agent Testing Tool

> ⚠️ **DISCLAIMER**: This is NOT an official Palo Alto Networks product. This is an independent, community-developed testing tool. Use at your own risk. No support or warranty is provided.

A GUI application for testing Palo Alto Networks User-ID Agent functionality, allowing network engineers to send IP-User mappings and manage Dynamic Address/User Groups.

## Features

### IP-User Mapping
- **Single Mapping**: Login/logout individual IP-to-user mappings with configurable timeout
- **Bulk Mapping**: Send up to 100,000+ entries with count-based generation
- **Progress Tracking**: Real-time "X of Y" counter during bulk operations
- **Stop Control**: Interrupt long-running operations at any time

### Dynamic Address Groups (DAG)
- Register/unregister IPs to tag-based groups
- Single or bulk IP tagging

### Dynamic User Groups (DUG)
- Register/unregister users to tag-based groups
- Single or bulk user tagging

### Certificate Management
- **Generate Fresh PKI**: Create Root CA, Server Cert (for UIA Agent), and Client Cert
- **Upload Custom Certs**: Use existing enterprise PKI certificates
- **Download Certs**: Get `rootCA.crt` and `uia-server-bundle.pem` for UIA Agent setup

## Quick Start

### Using Docker (Recommended)

```bash
docker pull your-repo/uia-app:1.0.0
docker run -p 8000:8000 -v ./certs:/app/certs your-repo/uia-app:1.0.0
```

Open http://localhost:8000 in your browser.

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

### Local Development

```bash
# Install Python dependencies
pip install -r requirements.txt

# Build frontend
cd gui && npm install && npm run build && cd ..

# Run server
python main.py
```

Open http://localhost:8000 in your browser.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser (GUI)                     │
│   React SPA with IP Mapping, DAG, DUG, Settings     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP API
┌──────────────────────▼──────────────────────────────┐
│                FastAPI Backend                      │
│  - Certificate Management                           │
│  - Bulk Mapping Engine (rate-limited)              │
│  - UIA Agent Communication (mTLS)                  │
└──────────────────────┬──────────────────────────────┘
                       │ mTLS (HTTPS)
┌──────────────────────▼──────────────────────────────┐
│              Palo Alto UIA Agent                    │
│         (Windows Service, port 5006)               │
└─────────────────────────────────────────────────────┘
```

## Rate Limiting

Bulk operations are intentionally rate-limited with a **2-second pause every 1,000 entries**. This:
- Gives the UIA Agent time to process and forward data to the firewall
- Allows users time to click the **STOP** button to interrupt if needed
- Prevents overwhelming the UIA Agent with rapid requests

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/single-mapping` | POST | Single IP-user login/logout |
| `/bulk-mapping` | POST | Count-based bulk mapping |
| `/update-ip-tags` | POST | DAG register/unregister |
| `/update-tags` | POST | DUG register/unregister |
| `/stop-mapping` | POST | Graceful stop of bulk operations |
| `/generate-pki` | POST | Generate fresh PKI certificates |
| `/upload-certs` | POST | Upload custom certificates |
| `/download-cert/{file}` | GET | Download generated certs |

## Requirements

- Python 3.11+
- Node.js 18+ (for building frontend)
- Palo Alto Networks User-ID Agent (target for testing)

## License

MIT License - See [LICENSE](LICENSE) for details.

---

**Disclaimer**: This project is not affiliated with, endorsed by, or supported by Palo Alto Networks. "Palo Alto Networks" and "User-ID Agent" are trademarks of Palo Alto Networks, Inc.
