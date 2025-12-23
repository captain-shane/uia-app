import os
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12

def generate_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

def save_key(key, filename, password=None):
    encryption_algorithm = serialization.BestAvailableEncryption(password.encode()) if password else serialization.NoEncryption()
    with open(filename, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=encryption_algorithm,
        ))

def save_cert(cert, filename):
    with open(filename, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

def generate_ca():
    print("Generating Root CA...")
    key = generate_key()
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Santa Clara"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"UIA-App Internal"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"UIA-App Root CA"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    ).sign(key, hashes.SHA256())
    
    return key, cert

def generate_signed_cert(ca_key, ca_cert, common_name, is_server=True):
    print(f"Generating {'Server' if is_server else 'Client'} Cert: {common_name}...")
    key = generate_key()
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"UIA-App Internal"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    
    builder = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    )
    
    if is_server:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ), critical=True
        ).add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False
        )
    else:
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False
        )

    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert

def main():
    cert_dir = "certs"
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)
        
    pfx_password = input("Enter a password for the Windows PFX file: ").strip()
    if not pfx_password:
        pfx_password = "password123"
        print(f"No password entered, using default: {pfx_password}")

    # 1. Root CA
    ca_key, ca_cert = generate_ca()
    save_key(ca_key, os.path.join(cert_dir, "rootCA.key"))
    save_cert(ca_cert, os.path.join(cert_dir, "rootCA.crt"))

    # 2. UIA Server Cert (for Windows)
    uia_key, uia_cert = generate_signed_cert(ca_key, ca_cert, u"uia-server", is_server=True)
    save_key(uia_key, os.path.join(cert_dir, "uia-server.key"))
    save_cert(uia_cert, os.path.join(cert_dir, "uia-server.crt"))
    
    # Export to PFX for Windows (Legacy support)
    pfx_data = pkcs12.serialize_key_and_certificates(
        b"uia-server",
        uia_key,
        uia_cert,
        [ca_cert],
        serialization.BestAvailableEncryption(pfx_password.encode())
    )
    with open(os.path.join(cert_dir, "uia-server.pfx"), "wb") as f:
        f.write(pfx_data)

    # Export to PEM Bundle with Encrypted Key (New requirement)
    # The UIA Agent often expects a single PEM file with the ENC private key and the cert.
    with open(os.path.join(cert_dir, "uia-server-bundle.pem"), "wb") as f:
        f.write(uia_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8, # Using PKCS8 for modern compatibility
            encryption_algorithm=serialization.BestAvailableEncryption(pfx_password.encode()),
        ))
        f.write(uia_cert.public_bytes(serialization.Encoding.PEM))
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM)) # Include CA in bundle

    # 3. App Client Cert (for Python/Docker)
    app_key, app_cert = generate_signed_cert(ca_key, ca_cert, u"uia-client-app", is_server=False)
    save_key(app_key, os.path.join(cert_dir, "uia-client.key"))
    save_cert(app_cert, os.path.join(cert_dir, "uia-client.crt"))
    
    # Create combined pem for convenience
    with open(os.path.join(cert_dir, "uia-client-bundle.pem"), "wb") as f:
        f.write(app_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        f.write(app_cert.public_bytes(serialization.Encoding.PEM))

    print(f"\nSuccess! All certificates generated in the '{cert_dir}' directory.")
    print(f"Windows PFX password: {pfx_password}")

if __name__ == "__main__":
    main()
