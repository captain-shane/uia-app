from typing import List, Optional
from pydantic import BaseModel

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

class ConnectionTestRequest(BaseModel):
    uia_url: str
    force: bool = False

class GeneratePKIRequest(BaseModel):
    password: str = "changeme"
