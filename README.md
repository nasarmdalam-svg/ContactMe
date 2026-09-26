# 🚗 Car SafeTag - 100% Free Anonymous Car QR Sticker System

> **A completely free, privacy-first vehicle QR sticker system.**  
> Anyone who scans a car's sticker can send instant parking alerts with loud alarm sounds and start direct in-browser voice calls with the car owner **without either party ever seeing or sharing their phone number**.

---

## 📌 Project Overview & Philosophy

Commercial vehicle parking tags (like Park+, AutoSticker, etc.) usually rely on expensive SMS gateways, paid telephony providers (Twilio/Exotel), or third-party bots (WhatsApp/Telegram). 

**Car SafeTag was built with strict engineering constraints:**
1. **$0.00 Running Cost**: No paid APIs, no per-minute telecom charges, no monthly subscriptions.
2. **No Third-Party Messaging Apps**: No Telegram, no WhatsApp. Everything runs natively in mobile browsers.
3. **Strict Privacy (Number Masking)**: Neither the bystander nor the car owner ever reveals their phone number, email, or identity.
4. **24/7 Cloud Ready**: Runs completely free in the cloud (e.g. Render / Railway / Fly.io) directly from this GitHub repository. Your local computer does not need to stay on.

---

## 🏗️ Architecture & Technology Stack

```
[Bystander's Smartphone]                            [Car Owner's Device]
 (Scans sticker with camera)                         (PWA / Browser Dashboard)
             │                                                   ▲
             │ 1. Scans QR Code                                  │
             ▼                                                   │
┌─────────────────────────────┐                                  │
│   Mobile Scanner UI (/c/..) │                                  │
│ ─────────────────────────── │                                  │
│ • "Blocking Driveway"       │─── 2. Send Alert / Call ──┐      │
│ • "Lights Left On"          │                           │      │
│ • "Call Owner (Voice)"      │                           ▼      │
└─────────────────────────────┘                 ┌───────────────────┐
             │                                  │   FastAPI Server  │
             │                                  │  (server.py)      │
             │                                  └─────────┬─────────┘
             │                                            │
             │                                3. Dispatches Web Push + WS
             │                                            │
             ▼                                            ▼
┌───────────────────────────────────────────────────────────────────┐
│                 WebRTC Peer-to-Peer Voice Call                    │
│    (Audio streamed directly between browsers via Google STUN)     │
└───────────────────────────────────────────────────────────────────┘
```

- **Backend**: Python 3.11 + FastAPI + Uvicorn (Asynchronous HTTP + native WebSockets).
- **Database**: SQLite (`cartag.db`) - simple, zero-configuration local database.
- **Real-Time Signaling**: WebSockets (`/ws/{tag_id}/{role}`).
- **Voice Calling**: WebRTC Peer-to-Peer Audio with Google's free public STUN servers (`stun:stun.l.google.com:19302`).
- **Sound Alerts**: Web Audio API oscillator synthesis (urgent car horn alarms and phone ringtones generated client-side with zero audio file dependencies).
- **Push Notifications**: W3C Web Push API (VAPID) supported natively by Android Chrome and iOS Safari (PWA).
- **Sticker Generation**: Python `qrcode` + `Pillow` generating high-DPI printable PNG stickers.

---

## 📂 Project Directory Structure

```text
Contact_Me/
├── server.py              # Main FastAPI app: HTTP endpoints, WebSockets, Web Push dispatch
├── database.py            # SQLite operations: tags, activations, alerts, subscriptions, stats
├── vapid_manager.py       # Auto-generates and persists VAPID keypair for Web Push
├── generate_stickers.py   # CLI tool to batch-generate high-res printable QR code stickers
├── render.yaml            # Render.com Infrastructure-as-Code for 1-click free cloud hosting
├── Procfile               # Cloud process launcher for uvicorn
├── requirements.txt       # Python package dependencies
├── .gitignore             # Git ignore file for local db, venv, and cache
├── static/
│   ├── css/
│   │   └── style.css      # Dark-mode, mobile-first responsive layout
│   ├── js/
│   │   ├── sound.js       # Web Audio API synthesizer (urgent horn siren & telephone ringtone)
│   │   └── webrtc.js      # WebRTC VoiceCallClient class handling peer connections & signaling
│   ├── icons/             # PWA app icons (192x192, 512x512, badge)
│   ├── sw.js              # Service Worker for background Web Push alerts & wake-up
│   └── manifest.json      # PWA manifest for "Add to Home Screen"
├── templates/
│   ├── scan.html          # Public page for bystanders scanning the sticker
│   ├── owner.html         # Car Owner Dashboard & PWA (alarms, sound controls, call answer)
│   ├── activate.html      # First-scan sticker activation page
│   └── admin.html         # Admin Dashboard (stats, registered cars list, batch generator)
└── stickers_output/       # Directory where generated printable PNG stickers are saved
```

---

## 🔌 API & WebSocket Specifications

### HTTP Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | System landing page. |
| `GET` | `/c/{tag_id}` | Public scanner entrypoint. If unactivated, redirects to `/activate/{tag_id}`; otherwise renders `scan.html`. |
| `GET` | `/activate/{tag_id}` | Shows sticker activation form (`activate.html`). |
| `POST` | `/api/activate/{tag_id}` | Activates sticker with `vehicle_name` and `custom_note`. Returns `owner_token`. |
| `GET` | `/owner/{tag_id}` | Owner dashboard (`owner.html`) to receive alerts and live voice calls. |
| `POST` | `/api/subscribe/{tag_id}`| Registers a Web Push subscription (endpoint, p256dh, auth). |
| `POST` | `/api/alert/{tag_id}` | Triggers an alert (e.g. `blocking`, `lights`, `alarm`, `custom`). Dispatches Web Push and WebSocket notifications. |
| `GET` | `/api/qr/{tag_id}` | Returns a dynamically generated PNG QR code image for this tag. |
| `GET` | `/api/sticker/{tag_id}` | Downloads a full, printable high-res card sticker PNG. |
| `GET` | `/admin` | Admin dashboard (`admin.html`) showing registered cars, alerts, and sticker batches. |
| `POST` | `/api/admin/generate-batch` | Generates a new batch of unassigned stickers on the fly. |

### WebSocket Signaling Protocol (`/ws/{tag_id}/{role}`)

The WebSocket handles real-time signaling between `caller` (bystander) and `owner`:

- `{"type": "alert_received", "alert_type": "blocking", "message": "..."}`: Real-time alert dispatched to owner.
- `{"type": "call_request"}`: Caller requests voice call. Owner's device triggers `incoming_call` and plays ringtone.
- `{"type": "call_accepted"}`: Owner accepts call. Caller initiates WebRTC offer.
- `{"type": "call_rejected"}`: Owner declines call.
- `{"type": "call_ended"}`: Either party hangs up.
- `{"type": "webrtc_offer", "sdp": ...}`: WebRTC SDP offer.
- `{"type": "webrtc_answer", "sdp": ...}`: WebRTC SDP answer.
- `{"type": "ice_candidate", "candidate": ...}`: ICE candidate exchange for NAT traversal.

---

## 🤖 Instructions for AI Agents & Developers Making Modifications

If you are an AI assistant or software engineer instructed to update this codebase, follow these guidelines:

### 1. Modifying the Alert Sound or Ringtone
- All sounds are generated procedurally in [`static/js/sound.js`](file:///Users/nasarmdalam/Desktop/Contact_Me/static/js/sound.js).
- `playAlertSound(repeatCount)`: Synthesizes urgent dual-tone car horn pulses using sawtooth oscillators.
- `startRingtone()`: Synthesizes standard 440Hz/480Hz telephone ringing cycles.
- *Tip for AI:* Do NOT replace this with external audio file URLs unless you bundle the MP3 directly in `static/sounds/` to prevent external CDN/network failures.

### 2. Modifying the Sticker Template & Dimensions
- Open [`generate_stickers.py`](file:///Users/nasarmdalam/Desktop/Contact_Me/generate_stickers.py).
- The function `create_sticker_image(tag_id, base_url)` controls sticker canvas size (default `600x760`), colors, typography, and QR code placement.
- You can add your company logo, sponsor banner, or change dimensions for specific sticker paper sheets.

### 3. Securing the `/admin` Route
- Currently, `/admin` is open for convenience.
- To protect it: Add an environment variable `ADMIN_PASSWORD` in `server.py` and verify it via HTTP Basic Auth or session cookie before rendering `admin.html`.

### 4. Swapping SQLite for PostgreSQL (e.g. Supabase / Neon / Render Postgres)
- All database queries are isolated in [`database.py`](file:///Users/nasarmdalam/Desktop/Contact_Me/database.py).
- To switch to PostgreSQL: Replace `sqlite3` with `psycopg2` or `asyncpg` and adjust the connection string using `os.environ.get("DATABASE_URL")`. Table schemas are standard SQL and fully compatible.

### 5. Adding Multi-Language Support
- In `templates/scan.html`, you can add a language selector (e.g., English, Hindi, Spanish, Arabic) and toggle the text on the alert buttons dynamically via a JSON dictionary.

---

## 🚀 Local Development Setup

```bash
# 1. Clone your repository
git clone https://github.com/nasarmdalam-svg/ContactMe.git
cd ContactMe

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start local development server
uvicorn server:app --reload --port 8000
```

- Open **[http://localhost:8000/admin](http://localhost:8000/admin)** for the Admin Panel.
- Open **[http://localhost:8000/activate/CAR-SAMPLE](http://localhost:8000/activate/CAR-SAMPLE)** to test activating a tag.
- Open **[http://localhost:8000/c/CAR-SAMPLE](http://localhost:8000/c/CAR-SAMPLE)** to test the public scanner page.

---

## ☁️ 24/7 Free Cloud Deployment (Render.com)

1. Push your changes to GitHub:
   ```bash
   git add .
   git commit -m "Your update"
   git push origin main
   ```
2. Log in to [render.com](https://render.com) and create a **New Web Service** pointing to your repository.
3. Render automatically picks up `render.yaml` and deploys your service.
4. Your application runs 24/7/365 online for **$0.00**.
