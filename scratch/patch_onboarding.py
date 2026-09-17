import os
import io

def patch():
    with open("server/routers/onboarding.py", "r") as f:
        content = f.read()
    
    if "update_xml" in content:
        print("Already patched")
        return
        
    patch_code = """
import hashlib
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def get_ext_id(pem_path: str) -> str:
    with open(pem_path, "rb") as f:
        pem_data = f.read()
    private_key = serialization.load_pem_private_key(pem_data, password=None, backend=default_backend())
    public_key = private_key.public_key()
    der_public_key = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    sha256_hash = hashlib.sha256(der_public_key).hexdigest()
    mapping = {'0':'a','1':'b','2':'c','3':'d','4':'e','5':'f','6':'g','7':'h','8':'i','9':'j','a':'k','b':'l','c':'m','d':'n','e':'o','f':'p'}
    return "".join([mapping[c] for c in sha256_hash[:32]])

@router.get("/api/v1/extension/update.xml", summary="Generate Chrome Extension Update XML")
@router.get("/chromebook/update.xml", summary="Generate Chrome Extension Update XML")
async def get_extension_update_xml(request: Request):
    pem_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "deploy", "certs", "chromebook-sensor.pem"))
    if not os.path.exists(pem_path):
        raise NotFoundException(detail="Extension PEM key not found. Please run scripts/build_extension.sh")
    
    ext_id = get_ext_id(pem_path)
    base_url = str(request.base_url).rstrip("/")
    crx_url = f"{base_url}/chromebook/extension.crx"
    
    xml = f\"\"\"<?xml version='1.0' encoding='UTF-8'?>
<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>
  <app appid='{ext_id}'>
    <updatecheck codebase='{crx_url}' version='1.0.0' />
  </app>
</gupdate>\"\"\"
    return Response(content=xml, media_type="application/xml")

@router.get("/api/v1/extension/extension.crx", summary="Download Packaged Chrome Extension (.crx)")
@router.get("/chromebook/extension.crx", summary="Download Packaged Chrome Extension (.crx)")
async def get_extension_crx():
    from fastapi.responses import FileResponse
    crx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "deploy", "chromebook-sensor.crx"))
    if not os.path.exists(crx_path):
        raise NotFoundException(detail="Packaged CRX not found. Please run scripts/build_extension.sh")
    
    return FileResponse(crx_path, media_type="application/x-chrome-extension", filename="chromebook-sensor.crx")
"""
    
    with open("server/routers/onboarding.py", "w") as f:
        f.write(content + "\n" + patch_code)
    
    print("Patched onboarding.py")

if __name__ == "__main__":
    patch()
