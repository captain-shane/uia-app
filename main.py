import os
import ssl
import logging
import asyncio
import http.client
import ipaddress
import collections
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from xml.dom import minidom

# Thread-safe log buffer for GUI
log_buffer = collections.deque(maxlen=50) # Reduced from 200
buffer_lock = threading.Lock()

class LogBufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        with buffer_lock:
            log_buffer.append(log_entry)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UIA-Backend")

# Add buffer handler to capture records for the frontend
buffer_handler = LogBufferHandler()
buffer_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(buffer_handler)
logging.getLogger().addHandler(buffer_handler) # Catch logs from other modules too

app = FastAPI(title="UIA Integration API")

# Global state
stop_event = asyncio.Event()
mapping_in_progress = False
configured_uia_url = "127.0.0.1:5006"
config_verified = False
active_mapping_task = None  # Track active background task

# Progress tracking
progress_current = 0
progress_total = 0

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class MappingRequest(BaseModel):
    subnet: str
    user_prefix: str = "domain\\user"
    timeout: int = 3600
    batch_size: int = 500
    uia_url: str  # e.g., "10.254.254.127:5006"
    cert_path: str = "certs/uia-client-bundle.pem"
    operation: str = "login" # "login" or "logout"

class TagRequest(BaseModel):
    items: List[dict] # [{"user": "...", "tag": "..."}]
    action: str # "register-user" or "unregister-user"
    uia_url: str
    cert_path: str = "certs/uia-client-bundle.pem"

class IpTagRequest(BaseModel):
    items: List[dict] # [{"ip": "...", "tag": "..."}]
    action: str # "register" or "unregister"
    uia_url: str
    cert_path: str = "certs/uia-client-bundle.pem"

class SingleMappingRequest(BaseModel):
    ip: str
    username: str
    timeout: int = 3600
    operation: str = "login"  # "login" or "logout"
    uia_url: str

class BulkMappingRequest(BaseModel):
    count: int  # Total number of entries
    user_prefix: str = "domain\\user"
    base_ip: str = "10.0.0.1"  # Starting IP
    timeout: int = 3600
    operation: str = "login"
    uia_url: str

INTERNAL_BATCH_SIZE = 500  # Fixed internal batch size

# UIA Communication Logic
def create_uid_message(entries: List[dict], event_type: str = 'login'):
    uid_message = ET.Element('uid-message')
    ET.SubElement(uid_message, 'version').text = '1.0'
    ET.SubElement(uid_message, 'type').text = 'update'
    payload = ET.SubElement(uid_message, 'payload')
    event = ET.SubElement(payload, event_type)
    
    for entry_data in entries:
        ET.SubElement(event, 'entry', name=entry_data['name'], ip=entry_data['ip'], timeout=str(entry_data['timeout']))
        
    return uid_message

def create_tag_message(entries: List[dict], action: str = 'register-user'):
    uid_message = ET.Element('uid-message')
    ET.SubElement(uid_message, 'version').text = '1.0'
    ET.SubElement(uid_message, 'type').text = 'update'
    payload = ET.SubElement(uid_message, 'payload')
    tag_action = ET.SubElement(payload, action)
    
    for entry_data in entries:
        entry = ET.SubElement(tag_action, 'entry', user=entry_data['user'])
        tag = ET.SubElement(entry, 'tag')
        ET.SubElement(tag, 'member').text = entry_data['tag']
        
    return uid_message

def create_ip_tag_message(entries: List[dict], action: str = 'register'):
    uid_message = ET.Element('uid-message')
    ET.SubElement(uid_message, 'version').text = '1.0'
    ET.SubElement(uid_message, 'type').text = 'update'
    payload = ET.SubElement(uid_message, 'payload')
    tag_action = ET.SubElement(payload, action)
    
    for entry_data in entries:
        entry = ET.SubElement(tag_action, 'entry', ip=entry_data['ip'])
        tag = ET.SubElement(entry, 'tag')
        ET.SubElement(tag, 'member').text = entry_data['tag']
        
    return uid_message

def sync_send_payload(xml_str, cert_file, key_file, ca_file, hostname, port):
    # Create SSL context with broader TLS support for older UIA Agents
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    
    # Allow older TLS versions for compatibility with legacy UIA Agents
    context.minimum_version = ssl.TLSVersion.TLSv1
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    
    # Disable strict security checks for legacy compatibility
    context.options &= ~ssl.OP_NO_SSLv3  # Clear any default restrictions
    if hasattr(ssl, 'OP_LEGACY_SERVER_CONNECT'):
        context.options |= ssl.OP_LEGACY_SERVER_CONNECT
    
    context.load_verify_locations(cafile=ca_file)
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    
    conn = http.client.HTTPSConnection(hostname, port=int(port), context=context, timeout=10)
    try:
        headers = {'Content-Type': 'application/xml'}
        conn.request('POST', '', body=xml_str, headers=headers)
        response = conn.getresponse()
        data = response.read().decode()
        return {"status": response.status, "reason": response.reason, "body": data}
    finally:
        conn.close()

async def send_payload_async(xml_str: str, cert_path: str, uia_url: str):
    try:
        if ':' not in uia_url:
            return {"error": f"Invalid URL format: {uia_url}. Use host:port"}
        hostname, port = uia_url.split(':')
    except Exception as e:
        return {"error": f"URL Parse Error: {e}"}

    ca_file = os.path.abspath("certs/rootCA.crt")
    cert_file = os.path.abspath("certs/uia-client.crt")
    key_file = os.path.abspath("certs/uia-client.key")
    
    if not all(os.path.exists(f) for f in [ca_file, cert_file, key_file]):
        missing = [f for f in [ca_file, cert_file, key_file] if not os.path.exists(f)]
        return {"error": f"Missing cert files: {missing}"}

    try:
        # Run blocking HTTP call in a thread to keep the event loop alive
        result = await asyncio.to_thread(sync_send_payload, xml_str, cert_file, key_file, ca_file, hostname, port)
        
        # Check XML for internal agent errors
        if "body" in result:
            try:
                root = ET.fromstring(result["body"])
                status_attr = root.get('status')
                if status_attr == 'error':
                    error_msg = result["body"]
                    result_node = root.find('.//result')
                    if result_node is not None:
                         error_msg = result_node.text
                    return {"error": f"UIA Agent Error: {error_msg}"}
            except:
                pass 
                
        if result.get("status", 0) >= 400:
             return {"error": f"HTTP {result['status']}: {result['reason']}"}
             
        return result
    except ssl.SSLError as e:
        logger.error(f"SSL handshake failed for {uia_url}: {e}")
        return {"error": f"SSL Error (Check UIA Server Cert/Root CA): {e.reason if hasattr(e, 'reason') else e}"}
    except (ConnectionRefusedError, ConnectionResetError) as e:
        logger.error(f"Network connection failed for {uia_url}: {e}")
        return {"error": f"Connection Error: Ensure the UIA Service is RUNNING on {hostname}:{port}"}
    except Exception as e:
        error_str = str(e)
        # Ignore if this is actually a valid response (false positive)
        if "<uid-response" in error_str or "uid-response" in error_str:
            return {"status": 200, "body": error_str}  # It's actually a success
        logger.error(f"Error during payload delivery to {uia_url}: {e}")
        return {"error": f"Delivery Error: {error_str}"}

async def test_uia_connection(uia_url: str):
    """3-Stage verification: TCP -> mTLS Handshake -> XML Version Check"""
    try:
        hostname, port_str = uia_url.split(':')
        port = int(port_str)
    except Exception:
        return {"error": "Invalid format. Use host:port", "stage": "Format"}

    # Stage 1: TCP Socket
    try:
        logger.info(f"Stage 1: Testing TCP connectivity to {hostname}:{port}")
        reader, writer = await asyncio.wait_for(asyncio.open_connection(hostname, port), timeout=4.0)
        writer.close()
        await writer.wait_closed()
        logger.info("Stage 1 SUCCESS: Port is open.")
    except Exception as e:
        return {"error": f"Network Error: Port {port} is not reachable. Check firewall/service.", "stage": "TCP"}

    # Stage 2: SSL/XML
    logger.info("Stage 2: Testing mTLS and API response...")
    xml_ver_req = '<uid-message><version>1.0</version><type>op</type><payload><show><version /></show></payload></uid-message>'
    result = await send_payload_async(xml_ver_req, "", uia_url)
    
    if "error" in result:
        return {"error": result['error'], "stage": "mTLS/API"}

    logger.info("Stage 2 SUCCESS: Agent responded correctly.")
    return {"message": "Verification Successful"}

# Batching Engine Implementation
async def process_mass_mapping(request: MappingRequest):
    global mapping_in_progress, active_mapping_task
    stop_event.clear()
    try:
        network = ipaddress.ip_network(request.subnet)
        total_ips = network.num_addresses
        logger.info(f"Starting mass mapping for {total_ips} addresses in {request.subnet}")
        
        batch = []
        count = 0
        total_batches = (total_ips // request.batch_size) + 1
        
        for i, ip in enumerate(network.hosts()):
            batch.append({
                "name": f"{request.user_prefix}{i+1}",
                "ip": str(ip),
                "timeout": request.timeout
            })
            
            if len(batch) == 1:
                 logger.info(f"Batching started. Current Batch Size Target: {request.batch_size}")

            # Check for cancellation - raise immediately to break the loop
            if stop_event.is_set():
                logger.warning("Stop event detected - cancelling operation")
                raise asyncio.CancelledError()

            if len(batch) >= request.batch_size:
                logger.info(f"Sending batch of {len(batch)} IPs...")
                uid_msg = create_uid_message(batch, request.operation)
                xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
                
                # Add cancellation check before network call
                if stop_event.is_set():
                    logger.warning("Stop event detected before network call")
                    raise asyncio.CancelledError()
                    
                await send_payload_async(xml_str, request.cert_path, request.uia_url)
                batch = []
                count += 1
                if count % 10 == 0:
                    logger.info(f"Processed {count}/{total_batches} batches...")
                # Tiny sleep to avoid slamming the UIA if needed
                await asyncio.sleep(0.01)

        # Send remaining
        if batch:
            uid_msg = create_uid_message(batch, request.operation)
            xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
            await send_payload_async(xml_str, request.cert_path, request.uia_url)
            
        logger.info(f"Mass mapping ({request.operation}) completed successfully.")
    except asyncio.CancelledError:
        logger.warning("Mass mapping was cancelled by user.")
        raise
    except Exception as e:
        logger.error(f"Error in mass mapping: {e}")
    finally:
        mapping_in_progress = False
        active_mapping_task = None

async def process_bulk_mapping(request: BulkMappingRequest):
    """Process bulk mapping with count-based entries (not subnet-based)"""
    global mapping_in_progress, active_mapping_task, progress_current, progress_total
    stop_event.clear()
    progress_current = 0
    progress_total = request.count
    
    try:
        # Parse base IP
        base_ip = ipaddress.ip_address(request.base_ip)
        logger.info(f"Starting bulk mapping: {request.count} entries from {base_ip}")
        
        batch = []
        for i in range(request.count):
            # Check for cancellation
            if stop_event.is_set():
                logger.warning("Bulk mapping cancelled by user")
                raise asyncio.CancelledError()
            
            current_ip = base_ip + i
            batch.append({
                "name": f"{request.user_prefix}{i+1}",
                "ip": str(current_ip),
                "timeout": request.timeout
            })
            
            if len(batch) >= INTERNAL_BATCH_SIZE:
                # Check again before network call
                if stop_event.is_set():
                    raise asyncio.CancelledError()
                
                logger.info(f"Sending batch... ({progress_current + len(batch)} of {progress_total})")
                uid_msg = create_uid_message(batch, request.operation)
                xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
                await send_payload_async(xml_str, "", request.uia_url)
                
                progress_current += len(batch)
                batch = []
                
                # Rate limiting: pause every 1000 entries to avoid overwhelming UIA
                if progress_current % 1000 == 0:
                    logger.info(f"Rate limit pause at {progress_current} entries...")
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(0.01)  # Small yield
        
        # Send remaining
        if batch:
            if stop_event.is_set():
                raise asyncio.CancelledError()
            uid_msg = create_uid_message(batch, request.operation)
            xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
            await send_payload_async(xml_str, "", request.uia_url)
            progress_current += len(batch)
        
        logger.info(f"Bulk mapping completed: {progress_current} entries sent")
    except asyncio.CancelledError:
        logger.warning("Bulk mapping cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in bulk mapping: {e}")
    finally:
        mapping_in_progress = False
        active_mapping_task = None

# Endpoints
@app.post("/single-mapping")
async def single_mapping(request: SingleMappingRequest):
    """Send a single IP-User mapping"""
    entry = [{
        "name": request.username,
        "ip": request.ip,
        "timeout": request.timeout
    }]
    uid_msg = create_uid_message(entry, request.operation)
    xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
    logger.info(f"Sending single mapping: {request.ip} -> {request.username} ({request.operation})")
    result = await send_payload_async(xml_str, "", request.uia_url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {"message": f"Single {request.operation} sent for {request.ip}", "result": result}

@app.post("/bulk-mapping")
async def bulk_mapping(request: BulkMappingRequest):
    """Start bulk mapping with count-based entries"""
    global active_mapping_task, mapping_in_progress
    if mapping_in_progress:
        raise HTTPException(status_code=400, detail="A mapping task is already in progress.")
    mapping_in_progress = True
    active_mapping_task = asyncio.create_task(process_bulk_mapping(request))
    return {"message": f"Started bulk mapping for {request.count} entries."}

@app.get("/progress")
async def get_progress():
    """Get current progress of bulk operation"""
    return {
        "current": progress_current,
        "total": progress_total,
        "running": mapping_in_progress
    }

@app.post("/map-subnet")
async def map_subnet(request: MappingRequest):
    global active_mapping_task, mapping_in_progress
    if mapping_in_progress:
        raise HTTPException(status_code=400, detail="A mapping task is already in progress.")
    mapping_in_progress = True
    active_mapping_task = asyncio.create_task(process_mass_mapping(request))
    return {"message": "Started mass mapping. Tracking progress on dashboard."}

@app.post("/stop-mapping")
async def stop_mapping():
    global active_mapping_task
    stop_event.set()
    if active_mapping_task and not active_mapping_task.done():
        active_mapping_task.cancel()
        logger.warning("Cancelling active mapping task...")
    return {"message": "Stop signal sent and task cancelled."}

@app.post("/emergency-stop")
async def emergency_stop():
    """Force stop all operations and reset state"""
    global mapping_in_progress, config_verified, active_mapping_task
    stop_event.set()
    if active_mapping_task and not active_mapping_task.done():
        active_mapping_task.cancel()
        logger.warning("Force cancelling active task...")
        try:
            await asyncio.wait_for(active_mapping_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    mapping_in_progress = False
    active_mapping_task = None
    logger.warning("EMERGENCY STOP: All operations halted.")
    return {"message": "All operations halted. State reset."}

@app.get("/status")
async def get_system_status():
    return {
        "status": "online",
        "mapping_active": mapping_in_progress,
        "config_verified": config_verified,
        "uia_url": configured_uia_url
    }

class ConnectionTestRequest(BaseModel):
    uia_url: str
    force: bool = False

@app.post("/test-connection")
async def test_connection(request: ConnectionTestRequest):
    global configured_uia_url, config_verified
    logger.info(f"Connection test requested: {request.uia_url} (Force={request.force})")
    
    if request.force:
        logger.warning(f"Bypassing verification as requested by user for {request.uia_url}")
        configured_uia_url = request.uia_url
        config_verified = True
        return {"message": "Configuration saved (Verification bypassed)."}

    result = await test_uia_connection(request.uia_url)
    
    if "error" in result:
        config_verified = False
        err_detail = f"[{result.get('stage', 'Unknown')}] {result['error']}"
        logger.error(f"Verification failed: {err_detail}")
        raise HTTPException(status_code=500, detail=err_detail)
    
    configured_uia_url = request.uia_url
    config_verified = True
    return {"message": "Configuration verified and saved."}

@app.get("/get-logs")
async def get_logs():
    with buffer_lock:
        return {"logs": list(log_buffer)}

@app.post("/update-tags")
async def update_tags(request: TagRequest):
    logger.info(f"DUG update: {len(request.items)} users, action={request.action}")
    uid_msg = create_tag_message(request.items, request.action)
    xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
    logger.info(f"Sending DUG XML to {request.uia_url}")
    result = await send_payload_async(xml_str, request.cert_path, request.uia_url)
    if "error" in result:
        logger.error(f"DUG error: {result['error']}")
        raise HTTPException(status_code=500, detail=result["error"])
    logger.info("DUG update complete")
    return result

@app.post("/update-ip-tags")
async def update_ip_tags(request: IpTagRequest):
    logger.info(f"DAG update: {len(request.items)} IPs, action={request.action}")
    uid_msg = create_ip_tag_message(request.items, request.action)
    xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
    logger.info(f"Sending DAG XML to {request.uia_url}")
    result = await send_payload_async(xml_str, request.cert_path, request.uia_url)
    if "error" in result:
        logger.error(f"DAG error: {result['error']}")
        raise HTTPException(status_code=500, detail=result["error"])
    logger.info("DAG update complete")
    return result

# Certificate Management
import shutil
import datetime as dt
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12

CERT_DIR = os.environ.get("CERT_DIR", "certs")

def generate_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)

@app.get("/cert-status")
async def cert_status():
    """Check if certificates exist"""
    has_client = os.path.exists(os.path.join(CERT_DIR, "uia-client.crt"))
    has_ca = os.path.exists(os.path.join(CERT_DIR, "rootCA.crt"))
    has_server = os.path.exists(os.path.join(CERT_DIR, "uia-server-bundle.pem"))
    return {
        "has_certs": has_client and has_ca,
        "has_client": has_client,
        "has_ca": has_ca,
        "has_server": has_server,
        "cert_dir": CERT_DIR
    }

class GeneratePKIRequest(BaseModel):
    password: str = "changeme"

@app.post("/generate-pki")
async def generate_pki(request: GeneratePKIRequest):
    """Generate full PKI: Root CA, Server Cert, Client Cert"""
    logger.info("Generating fresh PKI...")
    os.makedirs(CERT_DIR, exist_ok=True)
    
    # Root CA
    ca_key = generate_key()
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "UIA-App"),
        x509.NameAttribute(NameOID.COMMON_NAME, "UIA-App Root CA"),
    ])
    ca_cert = x509.CertificateBuilder().subject_name(ca_subject).issuer_name(ca_subject).public_key(
        ca_key.public_key()
    ).serial_number(x509.random_serial_number()).not_valid_before(
        dt.datetime.utcnow()
    ).not_valid_after(
        dt.datetime.utcnow() + dt.timedelta(days=3650)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    ).sign(ca_key, hashes.SHA256())
    
    # Save Root CA
    with open(os.path.join(CERT_DIR, "rootCA.key"), "wb") as f:
        f.write(ca_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    with open(os.path.join(CERT_DIR, "rootCA.crt"), "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    
    # Server Cert (for UIA Agent)
    srv_key = generate_key()
    srv_subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "UIA-App"),
        x509.NameAttribute(NameOID.COMMON_NAME, "uia-server"),
    ])
    srv_cert = x509.CertificateBuilder().subject_name(srv_subject).issuer_name(ca_cert.subject).public_key(
        srv_key.public_key()
    ).serial_number(x509.random_serial_number()).not_valid_before(
        dt.datetime.utcnow()
    ).not_valid_after(
        dt.datetime.utcnow() + dt.timedelta(days=365)
    ).add_extension(
        x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
    ).sign(ca_key, hashes.SHA256())
    
    # Save Server Cert as encrypted PEM bundle (key + cert + CA in one file)
    with open(os.path.join(CERT_DIR, "uia-server-bundle.pem"), "wb") as f:
        # Encrypted private key
        f.write(srv_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(request.password.encode())
        ))
        # Server cert
        f.write(srv_cert.public_bytes(serialization.Encoding.PEM))
        # Include CA in bundle
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    
    # Client Cert (for this app) - unencrypted for internal use
    cli_key = generate_key()
    cli_subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "UIA-App"),
        x509.NameAttribute(NameOID.COMMON_NAME, "uia-client"),
    ])
    cli_cert = x509.CertificateBuilder().subject_name(cli_subject).issuer_name(ca_cert.subject).public_key(
        cli_key.public_key()
    ).serial_number(x509.random_serial_number()).not_valid_before(
        dt.datetime.utcnow()
    ).not_valid_after(
        dt.datetime.utcnow() + dt.timedelta(days=365)
    ).add_extension(
        x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False
    ).sign(ca_key, hashes.SHA256())
    
    # Save Client Cert (unencrypted for internal app use)
    with open(os.path.join(CERT_DIR, "uia-client.key"), "wb") as f:
        f.write(cli_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    with open(os.path.join(CERT_DIR, "uia-client.crt"), "wb") as f:
        f.write(cli_cert.public_bytes(serialization.Encoding.PEM))
    
    logger.info("PKI generation complete")
    return {"message": "PKI generated successfully", "password": request.password}

@app.post("/upload-certs")
async def upload_certs(
    client_crt: UploadFile = File(...),
    client_key: UploadFile = File(...),
    root_ca: UploadFile = File(...)
):
    """Upload custom certificates for enterprise PKI environments"""
    logger.info("Uploading custom certificates...")
    os.makedirs(CERT_DIR, exist_ok=True)
    
    # Save uploaded files
    with open(os.path.join(CERT_DIR, "uia-client.crt"), "wb") as f:
        f.write(await client_crt.read())
    with open(os.path.join(CERT_DIR, "uia-client.key"), "wb") as f:
        f.write(await client_key.read())
    with open(os.path.join(CERT_DIR, "rootCA.crt"), "wb") as f:
        f.write(await root_ca.read())
    
    logger.info("Custom certificates uploaded successfully")
    return {"message": "Certificates uploaded successfully"}

@app.get("/download-cert/{filename}")
async def download_cert(filename: str):
    """Download generated certificates"""
    allowed = ["rootCA.crt", "uia-server-bundle.pem"]
    if filename not in allowed:
        raise HTTPException(status_code=403, detail="File not available for download")
    
    filepath = os.path.join(CERT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found. Generate PKI first.")
    
    return FileResponse(filepath, filename=filename)

@app.get("/health")
async def health():
    return {"status": "ok"}

# Serve static files from the React app with SPA fallback
# Must mount assets BEFORE the catch-all
if os.path.exists("gui/dist/assets"):
    app.mount("/assets", StaticFiles(directory="gui/dist/assets"), name="assets")

# SPA fallback - must be LAST after all other routes
from starlette.responses import HTMLResponse

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve index.html for all unmatched routes (SPA support)"""
    index_path = os.path.join("gui/dist", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return HTMLResponse(content=f.read())
    return {"error": "Frontend not built. Run 'npm run build' in gui/"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
