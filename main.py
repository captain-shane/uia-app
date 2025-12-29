import os
import logging
import asyncio
import ipaddress
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.responses import HTMLResponse

# Import refactored modules
from app.models import (
    MappingRequest, TagRequest, IpTagRequest, SingleMappingRequest,
    BulkMappingRequest, ConnectionTestRequest, GeneratePKIRequest
)
from app.state import (
    log_buffer, buffer_lock, LogBufferHandler,
    stop_event, mapping_in_progress, configured_uia_url, config_verified, active_mapping_task,
    progress_current, progress_total, get_logs, reset_state
)
import app.state as state # Allow direct modification of state variables
from app.services import uia, certs

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("UIA-Backend")

# Add buffer handler to capture records for the frontend
buffer_handler = LogBufferHandler()
buffer_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(buffer_handler)
logging.getLogger().addHandler(buffer_handler) # Catch logs from other modules too

app = FastAPI(title="UIA Integration API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INTERNAL_BATCH_SIZE = 500  # Fixed internal batch size

# Batching Engine Implementation
async def process_mass_mapping(request: MappingRequest):
    state.mapping_in_progress = True
    state.stop_event.clear()
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
            if state.stop_event.is_set():
                logger.warning("Stop event detected - cancelling operation")
                raise asyncio.CancelledError()

            if len(batch) >= request.batch_size:
                logger.info(f"Sending batch of {len(batch)} IPs...")
                uid_msg = uia.create_uid_message(batch, request.operation)
                xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
                
                # Add cancellation check before network call
                if state.stop_event.is_set():
                    logger.warning("Stop event detected before network call")
                    raise asyncio.CancelledError()
                    
                await uia.send_payload_async(xml_str, request.cert_path, request.uia_url)
                batch = []
                count += 1
                if count % 10 == 0:
                    logger.info(f"Processed {count}/{total_batches} batches...")
                # Tiny sleep to avoid slamming the UIA if needed
                await asyncio.sleep(0.01)

        # Send remaining
        if batch:
            uid_msg = uia.create_uid_message(batch, request.operation)
            xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
            await uia.send_payload_async(xml_str, request.cert_path, request.uia_url)
            
        logger.info(f"Mass mapping ({request.operation}) completed successfully.")
    except asyncio.CancelledError:
        logger.warning("Mass mapping was cancelled by user.")
        raise
    except Exception as e:
        logger.error(f"Error in mass mapping: {e}")
    finally:
        state.mapping_in_progress = False
        state.active_mapping_task = None

async def process_bulk_mapping(request: BulkMappingRequest):
    """Process bulk mapping with count-based entries (not subnet-based)"""
    state.mapping_in_progress = True
    state.stop_event.clear()
    state.progress_current = 0
    state.progress_total = request.count
    
    try:
        # Parse base IP
        base_ip = ipaddress.ip_address(request.base_ip)
        logger.info(f"Starting bulk mapping: {request.count} entries from {base_ip}")
        
        batch = []
        for i in range(request.count):
            # Check for cancellation
            if state.stop_event.is_set():
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
                if state.stop_event.is_set():
                    raise asyncio.CancelledError()
                
                logger.info(f"Sending batch... ({state.progress_current + len(batch)} of {state.progress_total})")
                uid_msg = uia.create_uid_message(batch, request.operation)
                xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
                await uia.send_payload_async(xml_str, "", request.uia_url)
                
                state.progress_current += len(batch)
                batch = []
                
                # Rate limiting: pause every 1000 entries to avoid overwhelming UIA
                if state.progress_current % 1000 == 0:
                    logger.info(f"Rate limit pause at {state.progress_current} entries...")
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(0.01)  # Small yield
        
        # Send remaining
        if batch:
            if state.stop_event.is_set():
                raise asyncio.CancelledError()
            uid_msg = uia.create_uid_message(batch, request.operation)
            xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
            await uia.send_payload_async(xml_str, "", request.uia_url)
            state.progress_current += len(batch)
        
        logger.info(f"Bulk mapping completed: {state.progress_current} entries sent")
    except asyncio.CancelledError:
        logger.warning("Bulk mapping cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in bulk mapping: {e}")
    finally:
        state.mapping_in_progress = False
        state.active_mapping_task = None

# Endpoints
@app.post("/single-mapping")
async def single_mapping(request: SingleMappingRequest):
    """Send a single IP-User mapping"""
    entry = [{
        "name": request.username,
        "ip": request.ip,
        "timeout": request.timeout
    }]
    uid_msg = uia.create_uid_message(entry, request.operation)
    xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
    logger.info(f"Sending single mapping: {request.ip} -> {request.username} ({request.operation})")
    result = await uia.send_payload_async(xml_str, "", request.uia_url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {"message": f"Single {request.operation} sent for {request.ip}", "result": result}

@app.post("/bulk-mapping")
async def bulk_mapping(request: BulkMappingRequest):
    """Start bulk mapping with count-based entries"""
    if state.mapping_in_progress:
        raise HTTPException(status_code=400, detail="A mapping task is already in progress.")
    state.active_mapping_task = asyncio.create_task(process_bulk_mapping(request))
    return {"message": f"Started bulk mapping for {request.count} entries."}

@app.get("/progress")
async def get_progress():
    """Get current progress of bulk operation"""
    return {
        "current": state.progress_current,
        "total": state.progress_total,
        "running": state.mapping_in_progress
    }

@app.post("/map-subnet")
async def map_subnet(request: MappingRequest):
    if state.mapping_in_progress:
        raise HTTPException(status_code=400, detail="A mapping task is already in progress.")
    state.active_mapping_task = asyncio.create_task(process_mass_mapping(request))
    return {"message": "Started mass mapping. Tracking progress on dashboard."}

@app.post("/stop-mapping")
async def stop_mapping():
    state.stop_event.set()
    if state.active_mapping_task and not state.active_mapping_task.done():
        state.active_mapping_task.cancel()
        logger.warning("Cancelling active mapping task...")
    return {"message": "Stop signal sent and task cancelled."}

@app.post("/emergency-stop")
async def emergency_stop():
    """Force stop all operations and reset state"""
    state.stop_event.set()
    if state.active_mapping_task and not state.active_mapping_task.done():
        state.active_mapping_task.cancel()
        logger.warning("Force cancelling active task...")
        try:
            await asyncio.wait_for(state.active_mapping_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    reset_state()
    logger.warning("EMERGENCY STOP: All operations halted.")
    return {"message": "All operations halted. State reset."}

@app.get("/status")
async def get_system_status():
    return {
        "status": "online",
        "mapping_active": state.mapping_in_progress,
        "config_verified": state.config_verified,
        "uia_url": state.configured_uia_url
    }

@app.post("/test-connection")
async def test_connection(request: ConnectionTestRequest):
    logger.info(f"Connection test requested: {request.uia_url} (Force={request.force})")
    
    if request.force:
        logger.warning(f"Bypassing verification as requested by user for {request.uia_url}")
        state.configured_uia_url = request.uia_url
        state.config_verified = True
        return {"message": "Configuration saved (Verification bypassed)."}

    result = await uia.test_uia_connection(request.uia_url)
    
    if "error" in result:
        state.config_verified = False
        err_detail = f"[{result.get('stage', 'Unknown')}] {result['error']}"
        logger.error(f"Verification failed: {err_detail}")
        raise HTTPException(status_code=500, detail=err_detail)
    
    state.configured_uia_url = request.uia_url
    state.config_verified = True
    return {"message": "Configuration verified and saved."}

@app.get("/get-logs")
async def api_get_logs():
    return {"logs": get_logs()}

@app.post("/update-tags")
async def update_tags(request: TagRequest):
    logger.info(f"DUG update: {len(request.items)} users, action={request.action}")
    uid_msg = uia.create_tag_message(request.items, request.action)
    xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
    logger.info(f"Sending DUG XML to {request.uia_url}")
    result = await uia.send_payload_async(xml_str, request.cert_path, request.uia_url)
    if "error" in result:
        logger.error(f"DUG error: {result['error']}")
        raise HTTPException(status_code=500, detail=result["error"])
    logger.info("DUG update complete")
    return result

@app.post("/update-ip-tags")
async def update_ip_tags(request: IpTagRequest):
    logger.info(f"DAG update: {len(request.items)} IPs, action={request.action}")
    uid_msg = uia.create_ip_tag_message(request.items, request.action)
    xml_str = ET.tostring(uid_msg, encoding='utf-8', method='xml').decode()
    logger.info(f"Sending DAG XML to {request.uia_url}")
    result = await uia.send_payload_async(xml_str, request.cert_path, request.uia_url)
    if "error" in result:
        logger.error(f"DAG error: {result['error']}")
        raise HTTPException(status_code=500, detail=result["error"])
    logger.info("DAG update complete")
    return result

# Certificate Management Routes
@app.get("/cert-status")
async def cert_status():
    return certs.check_cert_status()

@app.post("/generate-pki")
async def generate_pki(request: GeneratePKIRequest):
    return certs.generate_pki_certs(request.password)

@app.post("/upload-certs")
async def upload_certs(
    client_crt: UploadFile = File(...),
    client_key: UploadFile = File(...),
    root_ca: UploadFile = File(...)
):
    """Upload custom certificates for enterprise PKI environments"""
    logger.info("Uploading custom certificates...")
    await certs.save_custom_certs(
        await client_crt.read(),
        await client_key.read(),
        await root_ca.read()
    )
    logger.info("Custom certificates uploaded successfully")
    return {"message": "Certificates uploaded successfully"}

@app.get("/download-cert/{filename}")
async def download_cert(filename: str):
    """Download generated certificates"""
    allowed = ["rootCA.crt", "uia-server-bundle.pem"]
    if filename not in allowed:
        raise HTTPException(status_code=403, detail="File not available for download")
    
    filepath = os.path.join(certs.CERT_DIR, filename)
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
