import os
import json

DEFAULT_VAPID = {
    "public_key": "BMVoVqN6x_PGOYs6OTPOmANsJvMrmHTyGMyDXH7uTdfLe6dyJqpgnGzAkKrfsESXYYnsO_aIsUYWw9p5qDZHdWo",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgUT7H2Qw3sy2qdvO6\nLW8y7B3qNV3jKaoK6Mde0H0mYZWhRANCAATFaFajesfzxjmLOjkzzpgDbCbzK5h0\n8hjMg1x+7k3Xy3unciaqYJxswJCq37BEl2GJ7Dv2iLFGFsPaeag2R3Vq\n-----END PRIVATE KEY-----\n",
    "claims_sub": "mailto:nasarmdalam@gmail.com"
}

BASE_DIR = os.path.dirname(__file__)
PEM_PATH = os.path.join(BASE_DIR, "private_key.pem")

def get_or_create_vapid_keys():
    """Retrieve permanent VAPID keys and ensure a valid PEM file exists on disk."""
    keys = DEFAULT_VAPID.copy()
    
    # Write PEM file to disk for pywebpush / py_vapid (avoids from_string ASN.1 parsing bug)
    with open(PEM_PATH, "w") as f:
        f.write(keys["private_key"])
        
    keys["pem_path"] = PEM_PATH
    return keys

if __name__ == "__main__":
    k = get_or_create_vapid_keys()
    print("VAPID Keys loaded successfully. PEM path:", k["pem_path"])
