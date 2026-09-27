import os
import json
import firebase_admin
from firebase_admin import credentials, messaging
from typing import List, Dict, Any

_firebase_initialized = False

def init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return True

    # 1. Try env var FIREBASE_SERVICE_ACCOUNT_JSON (for Render / cloud deployments)
    env_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if env_json:
        try:
            cred_dict = json.loads(env_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("Firebase Admin initialized from FIREBASE_SERVICE_ACCOUNT_JSON env var")
            return True
        except Exception as e:
            print(f"Failed to init Firebase from env var: {e}")

    # 2. Try local file firebase_service_account.json
    local_path = os.path.join(os.path.dirname(__file__), "firebase_service_account.json")
    if os.path.exists(local_path):
        try:
            cred = credentials.Certificate(local_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("Firebase Admin initialized from local firebase_service_account.json")
            return True
        except Exception as e:
            print(f"Failed to init Firebase from local file: {e}")

    print("Warning: Firebase credentials not found. FCM notifications will be skipped.")
    return False

def send_fcm_alert(fcm_tokens: List[str], tag_id: str, alert_type: str, message: str, car_name: str = "") -> Dict[str, Any]:
    if not init_firebase():
        return {"success": False, "error": "Firebase not initialized"}

    if not fcm_tokens:
        return {"success": False, "sent_count": 0, "detail": "No tokens provided"}

    title = f"🚨 ParkingBuzz: {alert_type.upper()} ALERT"
    body = message if message else f"Someone is alerting your vehicle ({car_name or tag_id})"

    # High priority Android notification payload
    # When sending pure DATA messages (without a top-level notification object),
    # Android ALWAYS delivers the message directly to onMessageReceived() in ParkBuzzFirebaseMessagingService,
    # waking up the app and executing our custom heads-up chime and screen wakeup logic!
    android_config = messaging.AndroidConfig(
        priority="high",
        ttl=3600,
        notification=messaging.AndroidNotification(
            title=title,
            body=body,
            icon="ic_stat_parkbuzz",
            color="#38BDF8",
            channel_id="parkbuzz_alert_horn_v10",
            priority="max",
            sound="chime",
            default_vibrate_timings=True,
            visibility="public",
            image="https://contactme-go9v.onrender.com/static/images/p_logo.png"
        )
    )

    multicast_message = messaging.MulticastMessage(
        tokens=fcm_tokens,
        notification=messaging.Notification(
            title=title,
            body=body,
            image="https://contactme-go9v.onrender.com/static/images/p_logo.png"
        ),
        data={
            "tag_id": tag_id,
            "alert_type": alert_type,
            "message": body,
            "title": title
        },
        android=android_config
    )

    try:
        response = messaging.send_each_for_multicast(multicast_message)
        print(f"FCM batch result: {response.success_count} success, {response.failure_count} failures")
        
        # Collect invalid tokens to delete
        invalid_tokens = []
        for idx, resp in enumerate(response.responses):
            if not resp.success:
                err = resp.exception
                print(f"Token {fcm_tokens[idx]} failed: {err}")
                if hasattr(err, "code") and err.code in ["NOT_FOUND", "INVALID_ARGUMENT", "UNREGISTERED"]:
                    invalid_tokens.append(fcm_tokens[idx])

        return {
            "success": True,
            "sent_count": response.success_count,
            "fail_count": response.failure_count,
            "invalid_tokens": invalid_tokens
        }
    except Exception as e:
        print(f"Exception during FCM send: {e}")
        return {"success": False, "error": str(e)}
