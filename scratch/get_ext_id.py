import sys, hashlib
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def get_ext_id(pem_path):
    with open(pem_path, "rb") as f:
        pem_data = f.read()
    
    private_key = serialization.load_pem_private_key(pem_data, password=None, backend=default_backend())
    public_key = private_key.public_key()
    der_public_key = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    sha256_hash = hashlib.sha256(der_public_key).hexdigest()
    first_32 = sha256_hash[:32]
    # hex mapping to 'a'-'p'
    mapping = {'0':'a','1':'b','2':'c','3':'d','4':'e','5':'f','6':'g','7':'h','8':'i','9':'j','a':'k','b':'l','c':'m','d':'n','e':'o','f':'p'}
    ext_id = "".join([mapping[c] for c in first_32])
    return ext_id

print(get_ext_id("server/deploy/certs/chromebook-sensor.pem"))
