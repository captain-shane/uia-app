import os
import datetime as dt
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import logging

logger = logging.getLogger("UIA-Backend")

CERT_DIR = os.environ.get("CERT_DIR", "certs")

def generate_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)

def check_cert_status():
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

def generate_pki_certs(password: str):
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
            serialization.BestAvailableEncryption(password.encode())
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
    return {"message": "PKI generated successfully", "password": password}

async def save_custom_certs(client_crt: bytes, client_key: bytes, root_ca: bytes):
    """Save uploaded custom certificates"""
    os.makedirs(CERT_DIR, exist_ok=True)

    with open(os.path.join(CERT_DIR, "uia-client.crt"), "wb") as f:
        f.write(client_crt)
    with open(os.path.join(CERT_DIR, "uia-client.key"), "wb") as f:
        f.write(client_key)
    with open(os.path.join(CERT_DIR, "rootCA.crt"), "wb") as f:
        f.write(root_ca)
