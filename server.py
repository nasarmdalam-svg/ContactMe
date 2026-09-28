import os
import json
import io
import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import qrcode
from pywebpush import webpush, WebPushException

import database
import vapid_manager
import generate_stickers
import fcm_manager

app = FastAPI(title="ParkingBuzz System")

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

manager = ConnectionManager()

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
    if not tag or not tag["activated"]:
        # If tag doesn't exist or isn't claimed yet, prompt activation
        return RedirectResponse(url=f"/activate/{tag_id}")

    return templates.TemplateResponse(
        request=request,
        name="scan.html",
        context={"tag": tag}
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
    owner_token = database.activate_tag(tag_id, data.vehicle_name, data.custom_note or "")
    if data.owner_name:
        database.update_tag_profile(tag_id, data.vehicle_name, data.owner_name, data.custom_note or "")
    return {"status": "ok", "tag_id": tag_id, "owner_token": owner_token}

@app.post("/api/activate/{tag_id}")
def api_activate(tag_id: str, data: ActivateRequest):

    owner_token = database.activate_tag(tag_id, data.vehicle_name, data.custom_note)
    return {"status": "ok", "tag_id": tag_id, "owner_token": owner_token}

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
    if not tag or not tag["activated"]:
        return RedirectResponse(url=f"/activate/{tag_id}")

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

# Admin Dashboard
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    stats = database.get_admin_stats()
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"stats": stats}
    )

@app.post("/api/admin/generate-batch")
def admin_generate_batch(request: Request, count: int = Form(5), format: str = Form("admin")):
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

# Send Alert endpoint (Called by bystander)
@app.post("/api/alert/{tag_id}")
async def send_alert(tag_id: str, alert: AlertRequest):
    tag = database.get_tag(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if tag.get("is_active", 1) == 0:
        return {"status": "snoozed", "message": "Vehicle owner is currently disconnected / away (Do Not Disturb). Alert was snoozed."}

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
        "subscribers_notified": len(subs),
        "fcm_notified": len(fcm_tokens) if fcm_tokens else 0,
        "fcm_result": fcm_result
    }

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

# Printable sticker download endpoint — composites a real scannable QR onto the metallic card template
@app.get("/api/sticker/{tag_id}")
def get_sticker(tag_id: str, request: Request):
    from PIL import Image, ImageDraw, ImageFont
    import qrcode as _qrcode

    base_url = str(request.base_url).rstrip("/")
    scan_url = f"{base_url}/c/{tag_id}"

    metallic_path = os.path.join(os.path.dirname(__file__), "static/images/parking_card_dual_store.jpg")
    logo_path = os.path.join(os.path.dirname(__file__), "ParkBuzz_No_Disc_Transparent.png")

    # Embed real scannable QR seamlessly into the brushed metallic card
    if os.path.exists(metallic_path):
        import numpy as np

        card = Image.open(metallic_path).convert("RGB")
        arr = np.array(card)

        # 1. Cleanly erase the old template QR zone (x: 178..718, y: 254..776)
        y1, y2 = 254, 776
        x1, x2 = 178, 718
        c_left = arr[y1:y2, x1:x1+1, :].astype(float)
        c_right = arr[y1:y2, x2:x2+1, :].astype(float)
        alphas = np.linspace(0, 1, x2 - x1).reshape(1, -1, 1)
        arr[y1:y2, x1:x2, :] = ((1.0 - alphas) * c_left + alphas * c_right).astype(np.uint8)

        card = Image.fromarray(arr).convert("RGBA")

        # 2. Inpaint static template ID CAR-D3AEED inside the white card
        draw_card = ImageDraw.Draw(card)
        bg_card_tint = (235, 237, 240, 255)
        draw_card.rectangle([240, 892, 685, 946], fill=bg_card_tint)

        # 3. Generate high error-correction QR code (size = 480 px)
        qr_size = 480
        qr = _qrcode.QRCode(
            error_correction=_qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=1
        )
        qr.add_data(scan_url)
        qr.make(fit=True)

        qr_raw = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        arr_qr = np.array(qr_raw)
        is_white = (arr_qr[:, :, 0] > 180) & (arr_qr[:, :, 1] > 180) & (arr_qr[:, :, 2] > 180)
        arr_qr[is_white, 3] = 0
        arr_qr[~is_white, 0] = 20
        arr_qr[~is_white, 1] = 25
        arr_qr[~is_white, 2] = 35

        qr_transparent = Image.fromarray(arr_qr).resize((qr_size, qr_size), Image.Resampling.NEAREST)

        # 4. Embed Elevated 3D Chrome Emblem in center of QR
        badge_path = os.path.join(os.path.dirname(__file__), "static/images/official_chrome_p_badge.png")
        badge_size = 142
        if os.path.exists(badge_path):
            badge = Image.open(badge_path).convert("RGBA")
            badge = badge.resize((badge_size, badge_size), Image.LANCZOS)
            b_pos = ((qr_size - badge_size) // 2, (qr_size - badge_size) // 2)
            qr_transparent.paste(badge, b_pos, badge)

        paste_x = (896 - qr_size) // 2
        paste_y = 270
        card.paste(qr_transparent, (paste_x, paste_y), qr_transparent)

        # 5. Draw clean Vehicle ID in the white box
        card = card.convert("RGB")
        draw = ImageDraw.Draw(card)
        font_path = os.path.join(os.path.dirname(__file__), "static/fonts/Arial-Bold.ttf")
        font_bold = None
        if os.path.exists(font_path):
            try:
                font_bold = ImageFont.truetype(font_path, 33)
            except Exception:
                font_bold = None
        if not font_bold:
            for sys_font in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
                if os.path.exists(sys_font):
                    try:
                        font_bold = ImageFont.truetype(sys_font, 33)
                        break
                    except Exception:
                        pass
        if not font_bold:
            font_bold = ImageFont.load_default()

        if tag_id:
            text = f"Vehicle ID: {tag_id}"
            bbox = draw.textbbox((0, 0), text, font=font_bold)
            tw = bbox[2] - bbox[0]
            draw.text(((896 - tw) // 2, 903), text, fill=(20, 24, 33), font=font_bold)

        buf = io.BytesIO()
        card.save(buf, format="JPEG", quality=95)
        return Response(
            content=buf.getvalue(),
            media_type="image/jpeg",
            headers={"Content-Disposition": f'inline; filename="ParkingBuzz_Sticker_{tag_id}.jpg"'}
        )

    # Fallback: plain generated sticker if metallic card missing
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
