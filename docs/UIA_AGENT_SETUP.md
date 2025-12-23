# UIA Agent Setup Guide

This guide explains how to configure the Palo Alto Networks User-ID Agent to accept connections from UIA-App.

> ⚠️ **DISCLAIMER**: This is NOT an official Palo Alto Networks product. Refer to official PANW documentation for production deployments.

---

## Prerequisites

- Windows Server with User-ID Agent installed
- Administrator access to the UIA Agent host
- Certificates from UIA-App (generated or uploaded)

---

## Step 1: Generate or Obtain Certificates

### Option A: Generate from UIA-App

1. Open UIA-App at `http://localhost:8000/settings`
2. Set a password for the server key (remember this!)
3. Click **"🔐 Generate PKI"**
4. Download both files:
   - `rootCA.crt` - Root Certificate Authority
   - `uia-server-bundle.pem` - Server cert with encrypted key

### Option B: Use Enterprise PKI

If your organization has its own PKI:
1. Generate a server certificate for the UIA Agent
2. Generate a client certificate for UIA-App
3. Upload the client cert to UIA-App via Settings

---

## Step 2: Import Root CA to Windows

The Root CA must be trusted by Windows for mTLS to work.

1. Copy `rootCA.crt` to the UIA Agent Windows host
2. Open **MMC** (Run → `mmc`)
3. File → Add/Remove Snap-in → **Certificates** → Add
4. Select **Computer account** → Local computer → Finish → OK
5. Navigate to: **Certificates (Local Computer)** → **Trusted Root Certification Authorities** → **Certificates**
6. Right-click → **All Tasks** → **Import**
7. Browse to `rootCA.crt` and import it

> ⚠️ **IMPORTANT**: Must be imported to **Local Computer** store, NOT Current User!

---

## Step 3: Configure UIA Agent Service

### Open User-ID Agent Configuration

1. On the Windows host, open **User-ID Agent** from Start Menu
2. Or run: `C:\Program Files\Palo Alto Networks\User-ID Agent\UaService.exe`

### Configure Client Certificate Settings

1. Go to **Setup** tab → **Client Certificate** section
2. Click **Browse** for the certificate file
3. Select `uia-server-bundle.pem` (the PEM bundle file)
4. Enter the password you set during generation
5. Check **"Enable Client Certificate Authentication"**

### Configure Listening Port
1. Stop the Service
2. In **Setup** tab, Edit Service, Turn On Enable User-ID XML API on port 5006
3. This is the port UIA-App will connect to 

### Save and Restart service

1. Click **Save** and **Commit** or **Apply**
2. Restart the User-ID Agent service: **Start**
or if CLI only:
   ```cmd
   net stop "User-ID Agent"
   net start "User-ID Agent"
   ```

---

## Step 4: Windows Firewall

Ensure Windows Firewall allows incoming connections on port 5006:

```cmd
netsh advfirewall firewall add rule name="UIA Agent" dir=in action=allow protocol=TCP localport=5006
```

---

## Step 5: Test Connection from UIA-App

1. Open UIA-App at `http://localhost:8000/settings`
2. Enter the UIA Agent URL: `<UIA-IP>:5006` (e.g., `192.168.1.100:5006`)
3. Click **"Test & Save"**
4. Should show ✓ Connected

---

## Troubleshooting

### Connection Refused
- Verify UIA Agent service is running
- Check Windows Firewall rules
- Confirm port 5006 is listening: `netstat -an | findstr 5006`

### SSL/Certificate Errors
- Ensure Root CA is imported to **Local Computer** (not Current User)
- Verify certificate password is correct (Will error on import if pem package is not encrypted or password is wrong)
- Check certificate hasn't expired

### "Client Certificate Required" Error
- UIA Agent requires client cert authentication
- Verify UIA-App has valid client cert in `/app/certs` (If not in gui on a docker)

### Check UIA Agent Logs
Logs are typically at:
```
C:\Program Files(x86)\Palo Alto Networks\User-ID Agent\Logs\
```

---

## Network Diagram

```
┌─────────────────────┐          mTLS (port 5006)          ┌─────────────────────┐
│     UIA-App         │ ◄────────────────────────────────► │   UIA Agent         │
│  (Docker/Local)     │                                    │   (Windows)         │
│                     │                                    │                     │
│  Client Cert:       │                                    │  Server Cert:       │
│  uia-client.crt     │                                    │  uia-server-bundle  │
│  uia-client.key     │                                    │  .pem               │
└─────────────────────┘                                    └─────────────────────┘
         │                                                          │
         │                                                          │
         ▼                                                          ▼
   Both trust rootCA.crt                                 Forwards to Firewall
```

---

## Quick Reference

| Item | Value |
|------|-------|
| Default Port | 5006 |
| Protocol | HTTPS (mTLS) |
| Server Cert | `uia-server-bundle.pem` |
| Client Cert | `uia-client.crt` + `uia-client.key` |
| Root CA | `rootCA.crt` |
| Windows Store | Local Computer → Trusted Root CAs |

---

**Need Help?** Check the [main documentation](../README.md) or open an issue on GitHub.
