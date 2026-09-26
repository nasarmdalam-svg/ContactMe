import os
import json
from py_vapid import Vapid

VAPID_FILE = os.path.join(os.path.dirname(__file__), "vapid_keys.json")

def get_or_create_vapid_keys():
    """Retrieve existing VAPID keys or generate new ones for Web Push."""
    if os.path.exists(VAPID_FILE):
        try:
            with open(VAPID_FILE, "r") as f:
                data = json.load(f)
                if "public_key" in data and "private_key" in data:
                    return data
        except Exception as e:
            print(f"Error reading VAPID file: {e}")

    vapid = Vapid()
    vapid.generate_keys()
    
    # Export raw uncompressed public key (URL safe base64)
    public_key = vapid.public_key
    # The application server key for browser is raw bytes base64url encoded
    raw_pub = vapid.public_key.public_numbers().x.to_bytes(32, 'big') + vapid.public_key.public_numbers().y.to_bytes(32, 'big')
    raw_pub_bytes = b"\x04" + raw_pub
    
    import base64
    b64_pub = base64.urlsafe_b64encode(raw_pub_bytes).decode('utf-8').rstrip('=')
    
    # Private key in PEM format
    private_pem = vapid.private_pem().decode('utf-8')
    
    keys = {
        "public_key": b64_pub,
        "private_key": private_pem,
        "claims_sub": "mailto:admin@cartag.local"
    }
    
    with open(VAPID_FILE, "w") as f:
        json.dump(keys, f, indent=2)
        
    return keys

if __name__ == "__main__":
    keys = get_or_create_vapid_keys()
    print("VAPID Keys generated successfully:")
    print("Public Key:", keys["public_key"])
