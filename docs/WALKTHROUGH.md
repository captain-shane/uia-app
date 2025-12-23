# UIA-App Walkthrough

> ⚠️ **DISCLAIMER**: This is NOT an official Palo Alto Networks product. This is an independent, community-developed testing tool.

## Demo Video

![UIA-App Demo](demo.webp)

*Demo showing IP mapping, DAG/DUG operations, and mTLS certificate setup*

---

## Features Demonstrated

### 1. IP-User Mapping
- **Single Mapping**: Quick login/logout for individual IPs
- **Bulk Mapping**: Send thousands of entries with progress tracking
- **Rate Limited**: 2-second pause per 1,000 entries for UIA Agent stability

### 2. Dynamic Address Groups (DAG)
- Register IPs to tag-based firewall groups
- Unregister IPs from groups
- Bulk operations supported

### 3. Dynamic User Groups (DUG)
- Register users to tag-based groups
- Unregister users from groups
- Bulk operations supported

### 4. mTLS Certificate Setup
Certificates for secure App-to-UIA-Agent communication:
- **Generate Certs**: Create certs for testing environments
- **Upload Custom**: Use existing enterprise certificates
- **Download**: Get server cert bundle for UIA Agent configuration

---

## Quick Start

```bash
# Docker (recommended)
docker run -p 8000:8000 captainshane/uia-app:latest

# Open browser
# http://localhost:8000
```

## mTLS Certificate Setup Flow

1. Go to **Settings** page
2. Either:
   - **Generate Certs**: Click "Generate PKI", download server bundle
   - **Upload Custom**: Upload your enterprise certs for this app to use
3. On Windows UIA Agent host:
   - Import `rootCA.crt` to Trusted Root store
   - Configure UIA Agent with `uia-server-bundle.pem`
4. Enter UIA Agent URL and click "Test & Save"

## Rate Limiting

Bulk operations intentionally pause every 1,000 entries to:
- Allow UIA Agent to process requests
- Give users time to click STOP if needed
- Prevent overwhelming the firewall

---

**Repository**: https://github.com/captain-shane/uia-app  
**Docker Hub**: https://hub.docker.com/r/captainshane/uia-app
