import os
import json
import io
import time
import asyncio
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import qrcode
from pywebpush import webpush, WebPushException
import hmac
import hashlib
import secrets

import database
import vapid_manager
import generate_stickers
import fcm_manager

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ParkingBuzz@2026")
ACTIVE_ADMIN_SESSIONS = set()

def is_authenticated_admin(request: Request) -> bool:
    token = request.cookies.get("pb_admin_token")
    return bool(token and token in ACTIVE_ADMIN_SESSIONS)

app = FastAPI(title="ParkingBuzz System")

@app.get("/ping")
def ping():
    return {"status": "ok", "app": "ParkingBuzz", "time": time.time()}

@app.on_event("startup")
async def start_keepalive():
    async def keep_alive_loop():
        # Wait 45 seconds after startup before initiating self-pings
        await asyncio.sleep(45)
        while True:
            try:
                import urllib.request
                req = urllib.request.Request(
                    "https://contactme-go9v.onrender.com/ping",
                    headers={"User-Agent": "ParkingBuzz-KeepAlive/1.0"}
                )
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=12))
                print("Keep-alive self-ping sent to maintain Render instance warm.")
            except Exception as e:
                print(f"Keep-alive ping notice: {e}")
            # Ping every 5 minutes (300 seconds) so Render 15-minute sleep timer never fires
            await asyncio.sleep(300)

    asyncio.create_task(keep_alive_loop())

SCAN_SESSION_SECRET = os.environ.get("SESSION_SECRET", "parkingbuzz_secure_session_key_2026")

def generate_scan_token(tag_id: str, timestamp: int) -> str:
    msg = f"{tag_id}:{timestamp}".encode()
    sig = hmac.new(SCAN_SESSION_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:16]
    return f"{timestamp}:{sig}"

def verify_scan_token(tag_id: str, scan_token: str, max_age_seconds: int = 900) -> bool:
    if not scan_token or ":" not in scan_token:
        return False
    try:
        ts_str, sig = scan_token.split(":", 1)
        ts = int(ts_str)
        now = int(time.time())
        if (now - ts) > max_age_seconds:
            return False
        clean_id = tag_id.replace("BUZZ-", "").strip().upper()
        buzz_id = f"BUZZ-{clean_id}"
        for t in [tag_id, clean_id, buzz_id]:
            expected = hmac.new(SCAN_SESSION_SECRET.encode(), f"{t}:{ts}".encode(), hashlib.sha256).hexdigest()[:16]
            if hmac.compare_digest(sig, expected):
                return True
        return False
    except Exception:
        return False

BASE_DIR = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/sw.js")
def service_worker():
    sw_path = os.path.join(BASE_DIR, "static", "sw.js")
    return FileResponse(
        sw_path,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"}
    )

@app.api_route("/privacy", methods=["GET", "HEAD"])
def privacy_policy():
    privacy_path = os.path.join(BASE_DIR, "templates", "privacy.html")
    return FileResponse(privacy_path, media_type="text/html")




vapid_keys = vapid_manager.get_or_create_vapid_keys()

# WebSocket Connection Manager for WebRTC Signaling & Instant In-App Alerts
class ConnectionManager:
    def __init__(self):
        # tag_id -> {'owner': [ws, ...], 'caller': [ws, ...]}
        self.rooms: Dict[str, Dict[str, List[WebSocket]]] = {}

    async def connect(self, tag_id: str, role: str, websocket: WebSocket):
        await websocket.accept()
        if tag_id not in self.rooms:
            self.rooms[tag_id] = {"owner": [], "caller": []}
        self.rooms[tag_id][role].append(websocket)

    def disconnect(self, tag_id: str, role: str, websocket: WebSocket):
        if tag_id in self.rooms and role in self.rooms[tag_id]:
            if websocket in self.rooms[tag_id][role]:
                self.rooms[tag_id][role].remove(websocket)

    async def broadcast_to_peer(self, tag_id: str, sender_role: str, message: dict):
        if tag_id not in self.rooms:
            return
        target_role = "owner" if sender_role == "caller" else "caller"
        targets = self.rooms[tag_id].get(target_role, [])
        for ws in targets:
            try:
                await ws.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending ws message: {e}")

    async def notify_owner(self, tag_id: str, message: dict):
        if tag_id not in self.rooms:
            return
        for ws in self.rooms[tag_id].get("owner", []):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                pass

    async def notify_bystanders(self, tag_id: str, message: dict):
        if tag_id not in self.rooms:
            return
        for ws in self.rooms[tag_id].get("caller", []):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                pass

manager = ConnectionManager()

# --- Anti-Spam & Owner Response State ---
ALERT_TIMESTAMPS: Dict[str, List[float]] = {}
OWNER_SNOOZE: Dict[str, float] = {}
LATEST_OWNER_RESPONSES: Dict[str, dict] = {}

# --- Schemas ---
class RegisterVehicleRequest(BaseModel):
    vehicle_name: str
    owner_name: Optional[str] = ""
    custom_note: Optional[str] = ""

class ActivateRequest(BaseModel):
    vehicle_name: str
    custom_note: Optional[str] = ""


class UpdateProfileRequest(BaseModel):
    vehicle_name: str
    owner_name: Optional[str] = ""
    custom_note: Optional[str] = ""

class AlertRequest(BaseModel):
    alert_type: str
    message: Optional[str] = ""
    location: Optional[str] = ""
    session_token: Optional[str] = ""

class EmergencyProfileRequest(BaseModel):
    blood_group: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    emergency_phone: Optional[str] = ""
    backup_phone: Optional[str] = ""
    dnd_enabled: Optional[int] = 0
    dnd_start: Optional[str] = "23:00"
    dnd_end: Optional[str] = "07:00"

class SubscriptionModel(BaseModel):
    endpoint: str
    keys: Dict[str, str]

class FcmRegisterModel(BaseModel):
    fcm_token: str
    device_type: Optional[str] = "android"

class OwnerResponseRequest(BaseModel):
    message: str
    token: Optional[str] = ""

class SnoozeRequest(BaseModel):
    duration_minutes: Optional[int] = 60
    token: Optional[str] = ""

# --- Helper: Send Web Push ---
def send_push_notification(subscription_info: dict, payload: dict):
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=vapid_keys["pem_path"],
            vapid_claims={"sub": vapid_keys.get("claims_sub", "mailto:nasarmdalam@gmail.com")},
            ttl=86400
        )
    except WebPushException as ex:
        print(f"WebPush failed: {ex}")
    except Exception as e:
        print(f"Unexpected push error: {e}")

# Diagnostic endpoint to test direct push delivery
@app.get("/api/test-push/{tag_id}")
def test_push_endpoint(tag_id: str):
    subs = database.get_subscriptions(tag_id)
    if not subs:
        return {"status": "no_subscribers", "detail": "No subscriptions registered in DB for this tag"}
    results = []
    payload = {
        "title": "🚨 Car SafeTag Alert",
        "body": "Your car has a new alert!",
        "url": f"/owner/{tag_id}",
        "actionType": "test"
    }
    for sub in subs:
        sub_info = {
            "endpoint": sub["endpoint"],
            "keys": {
                "p256dh": sub["p256dh"],
                "auth": sub["auth"]
            }
        }
        try:
            res = webpush(
                subscription_info=sub_info,
                data=json.dumps(payload),
                vapid_private_key=vapid_keys["pem_path"],
                vapid_claims={"sub": vapid_keys.get("claims_sub", "mailto:nasarmdalam@gmail.com")},
                ttl=86400
            )
            results.append({"status": "success", "status_code": res.status_code if res else 200})
        except WebPushException as ex:
            err_body = ex.response.text if hasattr(ex, 'response') and ex.response else str(ex)
            results.append({"status": "fcm_error", "message": str(ex), "fcm_body": err_body})
        except Exception as e:
            results.append({"status": "error", "message": str(e)})
    return {"subscribers_count": len(subs), "results": results}

# --- Routes ---
@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return RedirectResponse(url="/register", status_code=302)

# Scan entrypoint for QR code: /c/{tag_id}
@app.get("/c/{tag_id}", response_class=HTMLResponse)
def scan_qr(tag_id: str, request: Request):
    tag = database.get_tag(tag_id)
    if not tag:
        canonical_id = tag_id.strip().upper()
        if not canonical_id.startswith("BUZZ-") and not canonical_id.startswith("CAR-"):
            canonical_id = f"BUZZ-{canonical_id}"
        database.create_tag(canonical_id)
        tag = database.get_tag(canonical_id)

    if tag and tag.get("is_blocked"):
        return HTMLResponse(
            """<!DOCTYPE html>
            <html lang="en">
            <head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Sticker Suspended - ParkingBuzz</title><link rel="stylesheet" href="/static/css/style.css"></head>
            <body style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#080c14;color:#f8fafc;font-family:sans-serif;padding:16px;">
              <div style="max-width:400px;text-align:center;background:#111827;border:1px solid rgba(239,68,68,0.35);border-radius:20px;padding:32px 20px;box-shadow:0 10px 40px rgba(0,0,0,0.7);">
                <div style="font-size:48px;margin-bottom:12px;">🛑</div>
                <h2 style="color:#f87171;margin-bottom:8px;font-size:20px;">Sticker Suspended</h2>
                <p style="color:#94a3b8;font-size:14px;line-height:1.5;margin-bottom:20px;">
                  This ParkingBuzz vehicle sticker has been temporarily suspended by system administration. Notifications and calls are disabled.
                </p>
                <div style="font-size:12px;color:#64748b;">
                  Need assistance? Contact admin at <a href="mailto:parkingbuzzplus@gmail.com" style="color:#38bdf8;font-weight:700;">parkingbuzzplus@gmail.com</a>
                </div>
              </div>
            </body>
            </html>""",
            status_code=403
        )

    if tag and tag.get("approval_status") == "pending":
        return HTMLResponse(
            """<!DOCTYPE html>
            <html lang="en">
            <head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Activation Pending - ParkingBuzz</title><link rel="stylesheet" href="/static/css/style.css"></head>
            <body style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#080c14;color:#f8fafc;font-family:sans-serif;padding:16px;">
              <div style="max-width:400px;text-align:center;background:#111827;border:1px solid rgba(245,158,11,0.35);border-radius:20px;padding:32px 20px;box-shadow:0 10px 40px rgba(0,0,0,0.7);">
                <div style="font-size:48px;margin-bottom:12px;">⏳</div>
                <h2 style="color:#fbbf24;margin-bottom:8px;font-size:20px;">Activation Pending</h2>
                <p style="color:#94a3b8;font-size:14px;line-height:1.5;margin-bottom:20px;">
                  This vehicle sticker has been registered and is currently awaiting administrator verification.
                </p>
                <div style="font-size:12px;color:#64748b;">
                  For priority activation, contact admin at <a href="mailto:parkingbuzzplus@gmail.com" style="color:#38bdf8;font-weight:700;">parkingbuzzplus@gmail.com</a>
                </div>
              </div>
            </body>
            </html>""",
            status_code=403
        )

    now_ts = int(time.time())
    canonical_tag_id = tag["tag_id"] if tag else tag_id
    session_token = generate_scan_token(canonical_tag_id, now_ts)
    expires_at = now_ts + 900  # 15 minutes = 900 seconds

    now_f = time.time()
    recent_alerts = [t for t in ALERT_TIMESTAMPS.get(canonical_tag_id, []) if now_f - t < 120.0]
    initial_sent_count = len(recent_alerts)
    initial_remaining = max(0, 3 - initial_sent_count)
    initial_wait_secs = max(1, int(120 - (now_f - recent_alerts[0]))) if initial_sent_count >= 3 else 0

    return templates.TemplateResponse(
        request=request,
        name="scan.html",
        context={
            "tag": tag,
            "session_token": session_token,
            "session_expires_at": expires_at,
            "session_duration_secs": 900,
            "initial_sent_count": initial_sent_count,
            "initial_remaining": initial_remaining,
            "initial_wait_secs": initial_wait_secs
        }
    )

# Activation page
@app.get("/activate/{tag_id}", response_class=HTMLResponse)
def activate_page(tag_id: str, request: Request):
    return templates.TemplateResponse(
        request=request,
        name="activate.html",
        context={"tag_id": tag_id}
    )

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")

@app.post("/api/register-vehicle")
def api_register_vehicle(data: RegisterVehicleRequest):
    import random
    while True:
        tag_id = f"BUZZ-{random.randint(100000, 999999)}"
        if not database.get_tag(tag_id):
            break
    owner_token = database.activate_tag(tag_id, data.vehicle_name, data.custom_note or "", allow_create=True)
    if data.owner_name:
        database.update_tag_profile(tag_id, data.vehicle_name, data.owner_name, data.custom_note or "")
    return {"status": "ok", "tag_id": tag_id, "owner_token": owner_token}

@app.post("/api/activate/{tag_id}")
def api_activate(tag_id: str, data: ActivateRequest):
    tag = database.get_tag(tag_id)
    if not tag:
        raise HTTPException(
            status_code=404,
            detail="Sticker ID not found. Only pre-registered or official printed stickers can be linked."
        )
    canonical_id = tag["tag_id"]
    owner_token = database.activate_tag(canonical_id, data.vehicle_name, data.custom_note, allow_create=False)
    return {"status": "ok", "tag_id": canonical_id, "owner_token": owner_token}

@app.post("/api/tag/{tag_id}/update")
def api_update_tag(tag_id: str, data: UpdateProfileRequest):
    database.update_tag_profile(
        tag_id=tag_id,
        vehicle_name=data.vehicle_name,
        owner_name=data.owner_name or "",
        custom_note=data.custom_note or ""
    )
    return {"status": "ok", "vehicle_name": data.vehicle_name, "owner_name": data.owner_name, "custom_note": data.custom_note}

@app.post("/api/tag/{tag_id}/emergency-profile")
def api_update_emergency_profile(tag_id: str, data: EmergencyProfileRequest):
    database.update_emergency_profile(
        tag_id=tag_id,
        blood_group=data.blood_group or "",
        emergency_contact=data.emergency_contact or "",
        emergency_phone=data.emergency_phone or "",
        backup_phone=data.backup_phone or "",
        dnd_enabled=data.dnd_enabled or 0,
        dnd_start=data.dnd_start or "23:00",
        dnd_end=data.dnd_end or "07:00"
    )
    return {"status": "ok", "message": "Emergency profile updated successfully"}

@app.post("/api/tag/{tag_id}/toggle-active")
def api_toggle_active(tag_id: str):
    new_state = database.toggle_tag_active(tag_id)
    return {"status": "ok", "is_active": new_state}

@app.post("/api/tag/{tag_id}/clear-alerts")
def api_clear_alerts(tag_id: str):
    database.clear_alerts(tag_id)
    return {"status": "ok"}

# Owner dashboard
@app.get("/owner/{tag_id}", response_class=HTMLResponse)
def owner_dashboard(tag_id: str, request: Request, token: Optional[str] = None):
    tag = database.get_tag(tag_id)
    if not tag:
        canonical_id = tag_id.strip().upper()
        if not canonical_id.startswith("BUZZ-") and not canonical_id.startswith("CAR-"):
            canonical_id = f"BUZZ-{canonical_id}"
        database.create_tag(canonical_id)
        database.activate_tag(canonical_id, vehicle_name="My Vehicle", allow_create=True)
        tag = database.get_tag(canonical_id)
    elif not tag.get("activated", 0):
        database.activate_tag(tag["tag_id"], vehicle_name=tag.get("vehicle_name") or "My Vehicle", allow_create=True)
        tag = database.get_tag(tag["tag_id"])

    recent_alerts = database.get_recent_alerts(tag_id)
    return templates.TemplateResponse(
        request=request,
        name="owner.html",
        context={
            "tag": tag,
            "recent_alerts": recent_alerts,
            "vapid_public_key": vapid_keys["public_key"]
        }
    )

# Admin Authentication & Dashboard
@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request, error: Optional[str] = None):
    if is_authenticated_admin(request):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={"error": error}
    )

@app.post("/admin/login")
def admin_login_submit(request: Request, password: str = Form(...)):
    entered_hash = hashlib.sha256(password.encode()).hexdigest()
    expected_hash = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
    if secrets.compare_digest(entered_hash, expected_hash):
        session_token = secrets.token_hex(32)
        ACTIVE_ADMIN_SESSIONS.add(session_token)
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(
            key="pb_admin_token",
            value=session_token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 7
        )
        return response
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={"error": "Invalid master administrator key. Access denied."}
    )

@app.get("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(key="pb_admin_token")
    return response

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    stats = database.get_admin_stats()
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"stats": stats}
    )

@app.post("/api/admin/toggle-auto-activation")
def admin_toggle_auto_activation(request: Request):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    current = database.is_auto_activation_enabled()
    database.set_admin_setting("auto_activation", "0" if current else "1")
    return RedirectResponse(url="/admin", status_code=303)

@app.api_route("/api/admin/user/{tag_id}/approve", methods=["GET", "POST"])
def admin_approve_user(tag_id: str, request: Request):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    try:
        database.set_user_approval(tag_id, "approved")
    except Exception as e:
        print(f"Database set_user_approval error: {e}")
    try:
        tag = database.get_tag(tag_id)
        v_name = tag.get("vehicle_name", "Vehicle") if tag else "Vehicle"
        fcm_manager.send_vehicle_alert(
            tag_id=tag_id,
            alert_type="APPROVED",
            vehicle_name=v_name,
            custom_message="🎉 Your ParkingBuzz sticker has been approved! Your QR code and vehicle safety buzz are now active."
        )
    except Exception as e:
        print(f"FCM approve notification error: {e}")
    try:
        database.log_alert(tag_id, "SYSTEM_APPROVED", "Vehicle approved and activated by administrator.")
    except Exception as e:
        print(f"Log alert error: {e}")
    return RedirectResponse(url="/admin", status_code=303)

@app.api_route("/api/admin/user/{tag_id}/block", methods=["GET", "POST"])
async def admin_block_user(tag_id: str, request: Request):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    is_blocked = 1
    if request.method == "POST":
        try:
            form = await request.form()
            is_blocked = int(form.get("is_blocked", 1))
        except Exception:
            is_blocked = 1
    database.set_user_blocked(tag_id, is_blocked)
    return RedirectResponse(url="/admin", status_code=303)

@app.api_route("/api/admin/user/{tag_id}/snooze", methods=["GET", "POST"])
async def admin_snooze_user(tag_id: str, request: Request):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    minutes = 60
    if request.method == "POST":
        try:
            form = await request.form()
            minutes = int(form.get("minutes", 60))
        except Exception:
            minutes = 60
    database.set_user_snooze(tag_id, minutes)
    return RedirectResponse(url="/admin", status_code=303)

@app.api_route("/api/admin/user/{tag_id}/delete", methods=["GET", "POST"])
def admin_delete_user(tag_id: str, request: Request):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    try:
        database.delete_user(tag_id)
    except Exception as e:
        print(f"Delete user error: {e}")
    return RedirectResponse(url="/admin", status_code=303)

class AdminMessageModel(BaseModel):
    message: str

@app.post("/api/admin/user/{tag_id}/message")
def admin_message_user(tag_id: str, data: AdminMessageModel, request: Request):
    if not is_authenticated_admin(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    tag = database.get_tag(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    v_name = tag.get("vehicle_name", "Vehicle")
    try:
        fcm_manager.send_vehicle_alert(
            tag_id=tag_id,
            alert_type="ADMIN_NOTICE",
            vehicle_name=v_name,
            custom_message=f"📢 Notice from Administrator: {data.message}"
        )
    except Exception as e:
        print(f"FCM admin message error: {e}")
    try:
        database.log_alert(tag_id, "ADMIN_NOTICE", data.message)
    except Exception as e:
        print(f"Log alert error: {e}")
    return {"status": "ok", "message": "Notice sent to vehicle owner"}

@app.get("/api/admin/sample-csv")
def admin_sample_csv():
    sample_content = "Vehicle_Plate,Owner_Name,Custom_Note\nDL01AB1234,Rahul Sharma,Flat 402 - Tower A\nHR26CD5678,Priya Patel,Tower B-110\nMH02EF9012,Amit Verma,Villa 14\n"
    return Response(
        content=sample_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="parkingbuzz_sample_vehicles.csv"'}
    )

@app.post("/api/admin/upload-csv")
async def admin_upload_csv(request: Request, file: UploadFile = File(...)):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    import csv
    import random
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    auto_active = database.is_auto_activation_enabled()
    approval = "approved" if auto_active else "pending"
    for row in reader:
        plate = row.get("Vehicle_Plate") or row.get("vehicle_plate") or row.get("Plate") or row.get("plate")
        if not plate or not plate.strip():
            continue
        owner = row.get("Owner_Name") or row.get("owner_name") or row.get("Name") or ""
        note = row.get("Custom_Note") or row.get("custom_note") or row.get("Note") or ""
        while True:
            t_id = f"BUZZ-{random.randint(100000, 999999)}"
            if not database.get_tag(t_id):
                break
        database.activate_tag(t_id, plate.strip(), note.strip(), allow_create=True, approval_status=approval)
        if owner.strip():
            database.update_tag_profile(t_id, plate.strip(), owner.strip(), note.strip())
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/api/admin/generate-batch")
def admin_generate_batch(request: Request, count: int = Form(5), format: str = Form("admin")):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    base_url = str(request.base_url).rstrip("/")
    tag_ids, pdf_path = generate_stickers.generate_batch(count=min(count, 200), base_url=base_url)
    if format == "pdf":
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="ParkingBuzz_Batch_{count}_Printable_Sheet.pdf"'}
        )
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/api/admin/download-batch-pdf")
def admin_download_batch_pdf(request: Request, count: int = 50):
    if not is_authenticated_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    base_url = str(request.base_url).rstrip("/")
    tag_ids, pdf_path = generate_stickers.generate_batch(count=min(count, 200), base_url=base_url)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ParkingBuzz_{count}_Stickers_Sheet.pdf"'}
    )

# Push subscription endpoint (Web browsers)
@app.post("/api/subscribe/{tag_id}")
def subscribe_push(tag_id: str, sub: SubscriptionModel):
    database.save_subscription(
        tag_id=tag_id,
        endpoint=sub.endpoint,
        p256dh=sub.keys.get("p256dh", ""),
        auth=sub.keys.get("auth", "")
    )
    return {"status": "subscribed"}

@app.post("/api/unsubscribe/{tag_id}")
def unsubscribe_push(tag_id: str, sub: Dict[str, Any]):
    endpoint = sub.get("endpoint", "")
    if endpoint:
        database.delete_subscription(endpoint)
    return {"status": "unsubscribed", "tag_id": tag_id}

# FCM registration endpoint (Android / iOS native apps)
@app.post("/api/fcm/register/{tag_id}")
def register_fcm_token(tag_id: str, reg: FcmRegisterModel):
    database.save_fcm_token(
        tag_id=tag_id,
        fcm_token=reg.fcm_token,
        device_type=reg.device_type or "android"
    )
    print(f"FCM token saved for tag: {tag_id}")
    return {"status": "fcm_registered", "tag_id": tag_id}

# FCM unregister endpoint on owner logout
@app.post("/api/fcm/unregister/{tag_id}")
def unregister_fcm_token(tag_id: str, reg: FcmRegisterModel):
    database.delete_fcm_token(reg.fcm_token, tag_id)
    print(f"FCM token unregistered for tag: {tag_id}")
    return {"status": "fcm_unregistered", "tag_id": tag_id}

# Send Alert endpoint (Called by bystander)
@app.post("/api/alert/{tag_id}")
async def send_alert(tag_id: str, alert: AlertRequest):
    tag = database.get_tag(tag_id)
    if not tag:
        canonical_id = tag_id.strip().upper()
        if not canonical_id.startswith("BUZZ-") and not canonical_id.startswith("CAR-"):
            canonical_id = f"BUZZ-{canonical_id}"
        database.create_tag(canonical_id)
        tag = database.get_tag(canonical_id) or {"tag_id": canonical_id, "is_active": 1}
    if tag.get("is_active", 1) == 0:
        return {"status": "snoozed", "message": "Vehicle owner is currently disconnected / away (Do Not Disturb). Alert was snoozed."}

    if tag.get("is_blocked"):
        return {"status": "blocked", "message": "This vehicle sticker is temporarily suspended by system administrator."}

    if tag.get("approval_status") == "pending":
        return {"status": "pending", "message": "This vehicle sticker is currently awaiting administrator approval."}

    now = time.time()

    # Check Database / Admin Snooze
    db_snooze = tag.get("snooze_until")
    if db_snooze:
        try:
            if float(db_snooze) > now:
                mins_left = max(1, int((float(db_snooze) - now) / 60))
                return {
                    "status": "snoozed",
                    "message": f"Owner has temporarily snoozed alerts ({mins_left} min remaining). For urgent matters, please use Voice Call."
                }
        except Exception:
            pass

    # 15-minute Session Check: Requires fresh QR scan after 15 mins
    if alert.session_token:
        if not verify_scan_token(tag_id, alert.session_token, max_age_seconds=900):
            return {
                "status": "session_expired",
                "message": "Scan session expired (15-minute limit). Please scan the vehicle's QR code again to notify the owner."
            }

    # Check Temporary Snooze
    snooze_until = OWNER_SNOOZE.get(tag_id, 0)
    if snooze_until > now:
        mins_left = max(1, int((snooze_until - now) / 60))
        return {
            "status": "snoozed",
            "message": f"Owner has temporarily snoozed alerts ({mins_left} min remaining). For urgent matters, please use Voice Call."
        }

    # Anti-Spam Rate Limiting: Maximum 3 alerts in 2 minutes (120s)
    recent_alerts = [t for t in ALERT_TIMESTAMPS.get(tag_id, []) if now - t < 120.0]
    if len(recent_alerts) >= 3:
        wait_secs = max(1, int(120 - (now - recent_alerts[0])))
        return {
            "status": "rate_limited",
            "wait_seconds": wait_secs,
            "alerts_sent_count": len(recent_alerts),
            "alerts_remaining": 0,
            "message": f"You have already sent 3 notifications. Please wait {wait_secs}s before sending another alert, or use Voice Call for urgent matters."
        }

    recent_alerts.append(now)
    ALERT_TIMESTAMPS[tag_id] = recent_alerts

    # 1. Log alert in DB
    alert_title = f"🚨 {alert.alert_type.capitalize()} Alert"
    alert_body = alert.message if alert.message else f"Alert regarding your vehicle ({tag.get('vehicle_name', tag_id)})"
    if alert.location:
        alert_body += f" | 📍 Location: {alert.location}"
    database.log_alert(tag_id, alert.alert_type, alert_body)

    # 2. Notify active WebSocket owner connection immediately (if app is open)
    await manager.notify_owner(tag_id, {
        "type": "alert_received",
        "alert_type": alert.alert_type,
        "message": alert_body
    })

    # 3. Trigger Native Google FCM Push Notification (Wakes up app even when 100% closed, on ANY phone)
    fcm_tokens = database.get_fcm_tokens(tag_id)
    fcm_result = None
    if fcm_tokens:
        loop = asyncio.get_event_loop()
        fcm_result = await loop.run_in_executor(
            None,
            fcm_manager.send_fcm_alert,
            fcm_tokens,
            tag_id,
            alert.alert_type,
            alert_body,
            tag.get("vehicle_name", "")
        )
        # Clean up any stale tokens
        if fcm_result and fcm_result.get("invalid_tokens"):
            for bad_tok in fcm_result["invalid_tokens"]:
                database.delete_invalid_fcm_token(bad_tok)

    # 4. Trigger Web Push to all registered browsers for this owner
    subs = database.get_subscriptions(tag_id)
    payload = {
        "title": alert_title,
        "body": alert_body,
        "url": f"/owner/{tag_id}?token={tag.get('owner_token', '')}",
        "actionType": alert.alert_type
    }

    loop = asyncio.get_event_loop()
    for sub in subs:
        sub_info = {
            "endpoint": sub["endpoint"],
            "keys": {
                "p256dh": sub["p256dh"],
                "auth": sub["auth"]
            }
        }
        loop.run_in_executor(None, send_push_notification, sub_info, payload)

    return {
        "status": "alert_sent",
        "alerts_sent_count": len(recent_alerts),
        "alerts_remaining": max(0, 3 - len(recent_alerts)),
        "wait_seconds": max(1, int(120 - (now - recent_alerts[0]))) if len(recent_alerts) >= 3 else 10,
        "subscribers_notified": len(subs),
        "fcm_notified": len(fcm_tokens) if fcm_tokens else 0,
        "fcm_result": fcm_result
    }

# Owner Quick Response Endpoint (e.g. 'On my way! (2 mins)')
@app.post("/api/owner/respond/{tag_id}")
async def owner_respond(tag_id: str, req: OwnerResponseRequest):
    tag = database.get_tag(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    clean_id = tag_id.replace("BUZZ-", "")
    buzz_id = f"BUZZ-{clean_id}"
    now = time.time()
    resp_data = {
        "message": req.message,
        "timestamp": now
    }
    LATEST_OWNER_RESPONSES[tag_id] = resp_data
    LATEST_OWNER_RESPONSES[clean_id] = resp_data
    LATEST_OWNER_RESPONSES[buzz_id] = resp_data
    
    # Notify bystanders on all variations of the tag ID
    for tid in set([tag_id, clean_id, buzz_id]):
        await manager.notify_bystanders(tid, {
            "type": "owner_response",
            "message": req.message,
            "tag_id": tid
        })
    
    return {"status": "ok", "message": req.message}

@app.get("/api/owner/response/{tag_id}")
def get_owner_response(tag_id: str):
    clean_id = tag_id.replace("BUZZ-", "")
    buzz_id = f"BUZZ-{clean_id}"
    resp = LATEST_OWNER_RESPONSES.get(tag_id) or LATEST_OWNER_RESPONSES.get(clean_id) or LATEST_OWNER_RESPONSES.get(buzz_id)
    if not resp:
        return {"has_response": False}
    # Expire after 10 minutes
    if time.time() - resp["timestamp"] > 600:
        return {"has_response": False}
    return {
        "has_response": True,
        "message": resp["message"],
        "seconds_ago": int(time.time() - resp["timestamp"])
    }

# Owner Quick Snooze (1-Hour or Custom DND)
@app.post("/api/owner/snooze/{tag_id}")
def snooze_owner_alerts(tag_id: str, req: Optional[SnoozeRequest] = None):
    tag = database.get_tag(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    clean_id = tag_id.replace("BUZZ-", "")
    buzz_id = f"BUZZ-{clean_id}"
    duration = (req.duration_minutes if req and req.duration_minutes else 60)
    until = time.time() + (duration * 60)
    OWNER_SNOOZE[tag_id] = until
    OWNER_SNOOZE[clean_id] = until
    OWNER_SNOOZE[buzz_id] = until
    return {"status": "snoozed", "duration_minutes": duration, "snooze_until": until}

@app.post("/api/owner/unsnooze/{tag_id}")
def unsnooze_owner_alerts(tag_id: str):
    clean_id = tag_id.replace("BUZZ-", "")
    buzz_id = f"BUZZ-{clean_id}"
    for tid in [tag_id, clean_id, buzz_id]:
        if tid in OWNER_SNOOZE:
            del OWNER_SNOOZE[tid]
    return {"status": "active"}

@app.get("/api/owner/snooze-status/{tag_id}")
def get_snooze_status(tag_id: str):
    clean_id = tag_id.replace("BUZZ-", "")
    buzz_id = f"BUZZ-{clean_id}"
    now = time.time()
    snooze_until = OWNER_SNOOZE.get(tag_id) or OWNER_SNOOZE.get(clean_id) or OWNER_SNOOZE.get(buzz_id) or 0
    is_snoozed = snooze_until > now
    mins_left = max(0, int((snooze_until - now) / 60)) if is_snoozed else 0
    return {"is_snoozed": is_snoozed, "minutes_left": mins_left}

# Dynamic QR code generation endpoint
@app.get("/api/qr/{tag_id}")
def get_qr_image(tag_id: str, request: Request):
    base_url = str(request.base_url).rstrip("/")
    scan_url = f"{base_url}/c/{tag_id}"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

# Printable sticker download endpoint — returns the official 76mm x 96mm luxury brushed aluminum card
@app.get("/api/sticker/{tag_id}")
def get_sticker(tag_id: str, request: Request):
    base_url = str(request.base_url).rstrip("/")
    try:
        card = generate_stickers.generate_metallic_sticker_card(tag_id, base_url)
        buf = io.BytesIO()
        card.save(buf, format="JPEG", quality=98)
        return Response(
            content=buf.getvalue(),
            media_type="image/jpeg",
            headers={"Content-Disposition": f'inline; filename="ParkingBuzz_Sticker_{tag_id}.jpg"'}
        )
    except Exception as e:
        sticker_path = generate_stickers.create_sticker_image(tag_id, base_url)
        with open(sticker_path, "rb") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="image/png",
            headers={"Content-Disposition": f'inline; filename="ParkingBuzz_Sticker_{tag_id}.png"'}
        )



# PDF sticker download endpoint (single sticker on A4)
@app.get("/api/sticker-pdf/{tag_id}")
def get_sticker_pdf(tag_id: str, request: Request):
    base_url = str(request.base_url).rstrip("/")
    pdf_path = generate_stickers.generate_single_sticker_a4_pdf(tag_id, base_url)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="sticker_{tag_id}.pdf"'}
    )

# Universal smart app download redirect (auto-detects iPhone vs Android)
@app.get("/app")
@app.get("/download")
def redirect_app_download(request: Request):
    user_agent = request.headers.get("user-agent", "").lower()
    # iPhone / iPad -> Apple App Store
    if "iphone" in user_agent or "ipad" in user_agent or "ipod" in user_agent:
        apple_store_url = "https://apps.apple.com/app/parkingbuzz/id6470000000"
        return RedirectResponse(url=apple_store_url, status_code=302)
    # Android -> Google Play Store
    elif "android" in user_agent:
        play_store_url = "https://play.google.com/store/apps/details?id=com.example.carsafetag"
        return RedirectResponse(url=play_store_url, status_code=302)
    # Desktop / Other -> Landing page
    return RedirectResponse(url="/", status_code=302)

# WebSocket endpoint for real-time WebRTC signaling
# WebSocket endpoint for real-time WebRTC signaling
@app.websocket("/ws/{tag_id}/{role}")
async def websocket_signaling(websocket: WebSocket, tag_id: str, role: str):
    await manager.connect(tag_id, role, websocket)
    if role == "caller":
        try:
            database.increment_call_count(tag_id)
        except Exception:
            pass
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                await manager.broadcast_to_peer(tag_id, role, msg)
            except Exception as e:
                print(f"Error handling message: {e}")
    except WebSocketDisconnect:
        manager.disconnect(tag_id, role, websocket)
        await manager.broadcast_to_peer(tag_id, role, {"type": "call_ended"})
