import os
import json

# Permanent static keypair so Render redeployments never invalidate active phone push tokens
DEFAULT_VAPID = {
    "public_key": "BMVoVqN6x_PGOYs6OTPOmANsJvMrmHTyGMyDXH7uTdfLe6dyJqpgnGzAkKrfsESXYYnsO_aIsUYWw9p5qDZHdWo",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgUT7H2Qw3sy2qdvO6\nLW8y7B3qNV3jKaoK6Mde0H0mYZWhRANCAATFaFajesfzxjmLOjkzzpgDbCbzK5h0\n8hjMg1x+7k3Xy3unciaqYJxswJCq37BEl2GJ7Dv2iLFGFsPaeag2R3Vq\n-----END PRIVATE KEY-----\n",
    "claims_sub": "mailto:admin@cartag.local"
}

VAPID_FILE = os.path.join(os.path.dirname(__file__), "vapid_keys.json")

def get_or_create_vapid_keys():
    """Retrieve permanent VAPID keys for Web Push."""
    if os.environ.get("VAPID_PUBLIC_KEY") and os.environ.get("VAPID_PRIVATE_KEY"):
        return {
            "public_key": os.environ["VAPID_PUBLIC_KEY"],
            "private_key": os.environ["VAPID_PRIVATE_KEY"],
            "claims_sub": os.environ.get("VAPID_CLAIMS_SUB", "mailto:admin@cartag.local")
        }

    if os.path.exists(VAPID_FILE):
        try:
            with open(VAPID_FILE, "r") as f:
                data = json.load(f)
                if "public_key" in data and "private_key" in data:
                    return data
        except Exception:
            pass

    return DEFAULT_VAPID

if __name__ == "__main__":
    keys = get_or_create_vapid_keys()
    print("VAPID Public Key:", keys["public_key"])
