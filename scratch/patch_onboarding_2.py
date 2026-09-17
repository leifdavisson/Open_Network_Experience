import os

def patch():
    with open("server/routers/onboarding.py", "r") as f:
        content = f.read()
    
    # Let's cleanly replace the previously added code
    start_idx = content.find("import hashlib\nfrom cryptography")
    if start_idx != -1:
        content = content[:start_idx]
        
    patch_code = """
@router.get("/api/v1/extension/update.xml", summary="Generate Chrome Extension Update XML")
@router.get("/chromebook/update.xml", summary="Generate Chrome Extension Update XML")
async def get_extension_update_xml(request: Request):
    id_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "deploy", "chromebook-sensor.id"))
    if not os.path.exists(id_path):
        raise NotFoundException(detail="Extension ID file not found. Please run scripts/build_extension.sh")
    
    with open(id_path, "r") as f:
        ext_id = f.read().strip()
        
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
    
    print("Patched onboarding.py again")

if __name__ == "__main__":
    patch()
