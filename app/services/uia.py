import os
import ssl
import logging
import asyncio
import httpx
import xml.etree.ElementTree as ET
from typing import List, Optional
from xml.dom import minidom

logger = logging.getLogger("UIA-Backend")

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

def get_legacy_ssl_context(cert_file: str, key_file: str, ca_file: str):
    """Create SSL context with broader TLS support for older UIA Agents"""
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
    return context

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
        # Create SSL context using legacy settings
        ssl_context = get_legacy_ssl_context(cert_file, key_file, ca_file)

        # Use httpx for async HTTP requests
        # Note: UIA Agent expects XML in body, usually POST to root
        async with httpx.AsyncClient(verify=ssl_context, timeout=10.0) as client:
            # We construct the URL manually. httpx handles https:// correctly.
            # UIA uses a custom XML protocol over HTTPS port (default 5006)
            url = f"https://{uia_url}"
            headers = {'Content-Type': 'application/xml'}

            try:
                response = await client.post(url, content=xml_str, headers=headers)
                data = response.text

                # Check XML for internal agent errors
                try:
                    root = ET.fromstring(data)
                    status_attr = root.get('status')
                    if status_attr == 'error':
                        error_msg = data
                        result_node = root.find('.//result')
                        if result_node is not None:
                             error_msg = result_node.text
                        return {"error": f"UIA Agent Error: {error_msg}"}
                except ET.ParseError:
                    pass # Not XML or invalid, ignore parsing error

                if response.status_code >= 400:
                     return {"error": f"HTTP {response.status_code}: {response.reason_phrase}"}

                return {"status": response.status_code, "reason": response.reason_phrase, "body": data}

            except httpx.RequestError as exc:
                logger.error(f"An error occurred while requesting {exc.request.url!r}: {exc}")
                return {"error": f"Connection Error: {str(exc)}"}

    except ssl.SSLError as e:
        logger.error(f"SSL handshake failed for {uia_url}: {e}")
        return {"error": f"SSL Error (Check UIA Server Cert/Root CA): {e.reason if hasattr(e, 'reason') else e}"}
    except Exception as e:
        error_str = str(e)
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
