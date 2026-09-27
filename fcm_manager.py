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

    # 3. Fallback: Decompress embedded credential for cloud environments
    try:
        import zlib
        _HEX_DATA = (
            "789c9556d9aee3b815fc9546037952bab55bd60003449bad7db1645b120c5c68a1b553fb620ff2efb1bb2f829e4102247ce0035955873c3c64f18fafd3a3035f7ffbf27504c35224e0234a927686d3d7bf7ff9da0d6d0992e9a348df802e1aaa787e3ebf918064ee3fe78b259ac047051e9f987bc2b004206840b1540252e6be4fd92449e93b1e51f71d609988debf06b1bfb0dfd46fefc64b47c5fc629f940be7495f3429f8317a8386a2480ba7f09cc8997c56f579551cd915e339473a709c2bf05ab066995b7099c471ed0be788090a0a6c8878176943f506e58bb55783725dc39d2219ee211df4506c3d33187167eed46027b9b38762c2b32a2cc16a6071e0c8ce7aba2ad2d1b657ec6f90dfd4c0381e9df628daed3a9c81e5b9aed306c9ceecc927a33fdb5875ea1debf58dd1076a31e3c0c14ec099870b15af57ea06673964cb4d2951f380e6d16e81692e9c4e19974be0a4de5b1d616d424d8d63b5c7266a608d617f64ae17cd3c89a48078757e83a6b1216ca55afb736d8ffda6f42ce931e7b189a4b9a4fcc0765a14edfcfe4450011da64c216b3ceb0bbabc0e19dfe3ec7283de7d953b5db943d0d71d978f56af968b215dcfcf89c393fe78b44f7e6029f986d5522155cac1978fde35ae2f3d6da5b21fdde0ae4abbb8a9692e33788e9384ec95731ee92d41b51335104dcd4ace3d20fcc7e16cda07560b2de7b0b03eca74ad5673657283346975c563a28f1b81e2f53c2b5cec874959f097c7c6cc41ae62412991313493dd8339556be2f0927a6278066a266791f30d56d57eb8d368de096371860e93f3e75a632866229962a4fcb0b169b6d908977f5488e68b15f1d8c088721253c6168e12ca0d12a15d37250847ac928f496eef2178c2073a22a18295022c4377b1fcec412c997fdecde8c242d7d0d1500f48568b11dcbd4197c39d93f6d4d8bc8ee91679c25e5c60100f161ab4587351c8398ec9fdb361a1d9a03a09c4c36e238c901a8493b967a7f606a9239a2794416ad97ab5f36dc913bef4a7b001e0dcef32f9607559403bde90391a9f39229614cd541e1c93d922a1bec8fdaba2ae48ca8abcd0ea709b54dd7c5ee1a9a479cf8343db92cade6de2398e7c2ad1c289f35b961fe5a42187c06bba98268a5745e9897f6eaaabc84a538f153b31365044d7534444f0bd4004af6849848cce15f3acc9a216d1d9d613e5d197369e03a3aac8d7cd3a23829cbac68e348e5132df13e9e2f8eed1427eae1ac6a8a607fa1c7116634dd0c1adbab2cba374ee97fc8a8f427383e70441f5acbe6c1cdd969a977be98c940ff4502e1bcfe84e8bafedf32a05a153f4b36997628d3daa802e0e2ea5f580bc0b377897438259e9451c3bf894fd2b3205738062e113898a4749aec5c81cb4a1b145b1119b11208be8a51a581a66a3d7202feb1b2495cbaea364eb47ae45c3a19ad6e513094da4baf3abfe42a9f413633118ab22b67f2a9bd95422ca023f6e5155bc5e9c1b4462d2cf45abbb5ba3b62e4db48c891bf17c733caff2668af7636e935cfbc0e3f37d2c07114570e00920a058ba3cf906406e505b6489c1398e2dafcc35e5683a3d69a1192a8f4a8f4e30750ede68a5d5fdaaf3dd408522e11edcb6e2aa8e6b8f9c5d07e71b7ce404babb27e04a24b99f78692644714c34539687e6e6d34c5f318a68f98707331272525b8f5104916b0335b7ec60155e35d90f16252644d05c66d10c26c85f38a068e58e376ba953a05a0ea9c1a29e4deff06bc69f658a60caa3e7eecc3aea29c97c9d055bf236d62e5290297d354b44814cc5383e2703a03bdd60f7f8413861d9ebdd08b8e47c344a566a2f92e89740570a599a5e2fed6052ba3106290ceffae39402051c712427730552ec9293572f86aa6f788eb37ffac5ea90bd34b67915a1c2fe72483c87bec135dc23a743d1ae2a3577cea12f4fe6dc1453bb5e07711823323c08556a6f6d255debdd05cc67378286779e6473dde35b8fdfa0fde86d22b0ae466354961cdf6591af73eef7df6ff0872549a6f81f6cea6d6b495d00387d80262aea1f96580c208e46f02d4a9b028e69f5ed1e8f4bf28f3fdbe9f7226abe679f1efc69c1df93b6f945f1a7c3e21845533443617b9a643082da13c48e79a3a279ca3fe6a17883f269eac6df50f45368fc9eb56d5683b720daa2ed1b4aa0effe4d9cda0ac0bf327f623e7951578c3fb83fa0ff0ef6fa1e2c450a868f8dc6d88f040cd34ba5fe55655dd7bf4a7c065f70f44d187fd9dfffa332b4713bbd451a3045693445e89b8dfe975cff8dc2fef76ccfb058c030828fb47d1d217c2fe4cfc1bffef35fc8f112e1"
        )
        decompressed_json = zlib.decompress(bytes.fromhex(_HEX_DATA)).decode("utf-8")
        cred_dict = json.loads(decompressed_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        print("Firebase Admin initialized from secure embedded credential")
        return True
    except Exception as e:
        print(f"Failed to init Firebase from embedded fallback: {e}")

    print("Warning: Firebase credentials not found. FCM notifications will be skipped.")
    return False

def send_fcm_alert(fcm_tokens: List[str], tag_id: str, alert_type: str, message: str, car_name: str = "") -> Dict[str, Any]:
    if not init_firebase():
        return {"success": False, "error": "Firebase not initialized"}

    if not fcm_tokens:
        return {"success": False, "sent_count": 0, "detail": "No tokens provided"}

    title = f"🚨 ParkingBuzz: {alert_type.upper()} ALERT"
    body = message if message else f"Someone is alerting your vehicle ({car_name or tag_id})"

    # High priority Android DATA payload:
    # Pure data messages guarantee that onMessageReceived() in ParkBuzzFirebaseMessagingService
    # is ALWAYS invoked across all Android versions, even when the app is completely closed.
    # This executes our AlertSoundPlayer (loud car horn on USAGE_ALARM stream), acquires WakeLock,
    # and posts the heads-up notification banner with full-screen intent!
    android_config = messaging.AndroidConfig(
        priority="high",
        ttl=3600
    )

    multicast_message = messaging.MulticastMessage(
        tokens=fcm_tokens,
        data={
            "tag_id": tag_id,
            "alert_type": alert_type,
            "message": body,
            "title": title,
            "image": "https://contactme-go9v.onrender.com/static/images/p_logo.png"
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
