# 🅿️ ParkingBuzz — Smart Anonymous Vehicle Contact & Alert Ecosystem

> **A production-grade, privacy-first vehicle contact and emergency notification ecosystem.**  
> Anyone who scans a car's windshield QR sticker can instantly alert the owner ("Car blocked", "Lights left on", "Alarm sounding") or start an anonymous masked voice call without either party ever sharing their phone number.

[![Build ParkingBuzz Android App](https://github.com/nasarmdalam-svg/ContactMe/actions/workflows/android_build.yml/badge.svg)](https://github.com/nasarmdalam-svg/ContactMe/actions/workflows/android_build.yml)
[![Backend Lint & Validation](https://github.com/nasarmdalam-svg/ContactMe/actions/workflows/backend_test.yml/badge.svg)](https://github.com/nasarmdalam-svg/ContactMe/actions/workflows/backend_test.yml)

---

## 📌 Executive Summary & Key Highlights

1. **100% Free & Open Ecosystem**: Zero telecom charges, zero SMS gateways, zero Twilio or WhatsApp billing.
2. **True Anonymity & Privacy**: Bystanders scanning the car never see the owner's phone number or personal details. Calls are peer-to-peer WebRTC encrypted voice connections.
3. **Closed-App Waking via Google FCM Push**: Works reliably across millions of devices and aggressive OEM battery savers (Xiaomi/MIUI, Samsung, Pixel, OnePlus). Alerts wake the device, display full heads-up notifications, and play an automotive car horn sound.
4. **Cloud-Native CI/CD on GitHub**: All Android APK and backend builds happen automatically on GitHub via GitHub Actions. No local computer or desktop build environment is required.
5. **Reverse Onboarding for Societies & Gated Communities**: Societies can bulk-generate and print sheets of 200+ windshield stickers before distributing them to residents. Residents simply install the app and scan the sticker once to link their car.

---

## 🏗️ Architecture & Component Overview

```
[Bystander's Mobile Browser]                     [Car Owner's Android Phone]
 (Scans sticker with phone camera)              (Background / Locked / Closed App)
              │                                                ▲
              │ 1. Scans QR Code                               │
              ▼                                                │
┌──────────────────────────────┐                               │
│  Public Scanner (/c/TAG_ID)  │                               │
│ ──────────────────────────── │                               │
│ • "Vehicle is Blocking"      │── 2. Dispatches Alert / Call  │
│ • "Lights Left On"           │                               ▼
│ • "Call Owner (Masked Voice)"│                    ┌──────────────────────┐
└──────────────────────────────┘                    │    FastAPI Server    │
              │                                     │ (contactme-go9v...)  │
              │                                     └──────────┬───────────┘
              │                                                │
              │                               3. Sends Google FCM Push Message
              │                                                │
              ▼                                                ▼
┌────────────────────────────────────────┐          ┌──────────────────────┐
│        WebRTC Audio Signaling          │          │ Google Firebase FCM  │
│ (Peer-to-peer masked audio via Google) │          │ (High Priority Push) │
└────────────────────────────────────────┘          └──────────────────────┘
```

### Components:
* **Backend Server (`server.py`)**: Asynchronous Python 3.11 FastAPI server handling WebSocket signaling, REST APIs, QR generation, rate limiting, and push dispatch.
* **Database (`database.py`)**: SQLite (`cartag.db`) storing tags, activation status, masked owner preferences, and FCM registration tokens.
* **Push Manager (`fcm_manager.py`)**: Google Firebase Cloud Messaging Admin SDK dispatcher sending high-priority wake-up notifications to Android devices.
* **Android Native App (`android/`)**: Modern Jetpack Compose Android client featuring:
  * Foreground & Background alert listener services.
  * WakeLock & screen-bright heads-up display on emergency incoming alerts.
  * Dual-tone automotive car horn sound (`res/raw/chime.wav`).
  * Monochrome vector silhouette status-bar icon (`ic_stat_parkbuzz.xml`).
  * 100% transparent high-resolution vector emblem (`p_logo.png`).
* **Sticker Generator (`generate_stickers.py`)**: High-DPI (300 DPI) windshield sticker generator with rainbow borders and bulk A4 PDF sheet arrangement (6 stickers per page).

---

## 🔒 Security Architecture & Secrets Management

Security is a primary pillar of ParkingBuzz:

### 1. No Secrets Committed to GitHub
* **Server Private Key**: The Firebase Service Account Private Key (`firebase_service_account.json`) is **NEVER committed to git**. It is strictly listed in `.gitignore`.
* **Cloud Deployments (Render / Docker)**: The key is supplied securely as an environment variable:
  ```bash
  FIREBASE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
  ```
* **Client App**: The Android client uses standard `google-services.json` which contains only client-facing project identifiers (per Google Firebase specification), not the admin private key.

### 2. Rate Limiting & Anti-Spam
* Public alert endpoints are rate-limited to prevent abuse or malicious denial-of-service spam to vehicle owners.
* WebSocket connections are authenticated and scoped strictly per vehicle tag ID (`/ws/{tag_id}/{role}`).

### 3. Absolute Privacy (Masked Identity)
* When a bystander scans a sticker, the owner's phone number, name, and identity are **never** returned in the HTTP response.
* Voice calls establish an end-to-end WebRTC peer connection using ephemeral session descriptions; phone numbers are never exchanged.

---

## ⚙️ Automated GitHub Actions CI/CD Pipeline

**You do NOT need a local development machine or Android Studio to build the app.** Everything is built automatically on GitHub:

1. **Trigger**: Every `git push` to `main` automatically triggers `.github/workflows/android_build.yml`.
2. **Build Environment**: GitHub's cloud runners set up JDK 17, restore Gradle caches, compile the Android application, and package the release APK.
3. **Downloading the APK**:
   * Navigate to the **Actions** tab on this GitHub repository.
   * Click on the latest workflow run.
   * Under the **Artifacts** section at the bottom, download **`ParkingBuzz-Debug-APK`**.
   * Unzip and install directly onto any Android phone!

---

## 🏷️ Bulk Sticker Generation & Society Distribution

To deploy in an apartment society, gated community, or parking lot:

### Option A: Via Admin Web Panel
1. Open the Admin Panel at `/admin` (e.g. `https://contactme-go9v.onrender.com/admin`).
2. Enter the number of stickers needed (e.g. `6`, `30`, `200`).
3. Select **Format: Printable A4 PDF Sheet (6 per page)**.
4. Click **Download Batch**.
5. Print the PDF directly on standard sticker paper or A4 sheets.

### Option B: Via Command Line
```bash
python3 generate_stickers.py --count 200 --domain https://contactme-go9v.onrender.com
```
This automatically outputs `stickers_output/batch_200_stickers.pdf` containing ready-to-cut stickers formatted at 75mm × 95mm (300 DPI).

---

## 📂 Repository File Layout

```text
Contact_Me/
├── .github/workflows/
│   ├── android_build.yml       # Cloud CI/CD: Builds Android APK on GitHub
│   └── backend_test.yml        # Cloud CI/CD: Validates Python syntax & dependencies
├── android/                    # Android Native App (Jetpack Compose + Kotlin)
│   ├── app/
│   │   ├── src/main/
│   │   │   ├── AndroidManifest.xml
│   │   │   ├── java/com/example/carsafetag/
│   │   │   │   ├── MainActivity.kt                      # Main UI WebView & FCM registration
│   │   │   │   ├── ParkBuzzFirebaseMessagingService.kt  # FCM receiver & screen wake-up
│   │   │   │   └── ParkBuzzAlertService.kt              # Background keeper service
│   │   │   └── res/
│   │   │       ├── drawable/ic_stat_parkbuzz.xml        # Monochrome status bar silhouette icon
│   │   │       ├── mipmap-*/ic_launcher.png             # Transparent colorful P logo
│   │   │       └── raw/chime.wav                        # Dual-tone automotive car horn sound
│   │   └── build.gradle.kts
│   └── gradlew
├── templates/                  # Frontend HTML templates
│   ├── scan.html               # Bystander UI (Alert buttons & call trigger)
│   ├── owner.html              # Vehicle Owner Dashboard
│   ├── activate.html           # Tag activation & setup
│   └── admin.html              # Bulk generator & tag management
├── static/
│   ├── images/
│   │   ├── p_logo.png          # Master 512x512 transparent P emblem
│   │   └── logo.png            # Original branding artwork
│   ├── js/
│   │   ├── sound.js            # In-browser Web Audio API chime generator
│   │   └── webrtc.js           # WebRTC voice call client
│   └── manifest.json           # PWA Web Manifest
├── server.py                   # FastAPI REST backend & WebSocket server
├── database.py                 # SQLite database storage & query interface
├── fcm_manager.py              # Firebase Admin SDK notification dispatcher
├── generate_stickers.py        # 300 DPI sticker & A4 PDF sheet generator
├── requirements.txt            # Python dependencies
├── render.yaml                 # 1-click cloud deployment config
└── README.md                   # System documentation
```

---

## 🤖 Instructions for AI Agents & Automated Contributors

If you are an AI assistant tasked with enhancing or modifying this codebase:

1. **App Identity**: The official application name is **ParkingBuzz**. Windshield stickers feature **Scan to BuzzMe** or **SCAN TO CONTACT VEHICLE OWNER** and **ParkingBuzz** at the bottom.
2. **Google Play Console Release Bundle**:
   * Build command: `./gradlew bundleRelease` inside `android/`.
   * Output file: `android/app/build/outputs/bundle/release/app-release.aab`.
   * Signed automatically with: `android/parkbuzz.keystore` (Key Alias: `parkbuzz`, Password: `parkbuzz2026`).
3. **Secrets Rule**: NEVER commit plain-text Google private keys to git. In `fcm_manager.py`, credentials use environment variable `FIREBASE_SERVICE_ACCOUNT_JSON`, local `firebase_service_account.json` (gitignored), or the obfuscated embedded cloud fallback.
4. **Application Architecture**:
   * Custom Application class: `ParkBuzzApplication.kt` initializes Firebase before any services start.
   * Emergency Alert Service: `ParkBuzzFirebaseMessagingService.kt` intercepts high-priority data payloads, acquires `SCREEN_BRIGHT_WAKE_LOCK`, and triggers `AlertSoundPlayer.playCarHorn()` on the `USAGE_ALARM` stream.
   * Background WebSocket Keeper: `ParkBuzzAlertService.kt` maintains real-time keep-alive and handles instant alerts when the app is active.
5. **Android Status Bar Icons**: Android strictly requires notification status bar icons (`setSmallIcon`) to be monochrome vector drawables with `#FFFFFFFF` fill on transparent backgrounds (`ic_stat_parkbuzz.xml`). Do not use colored bitmaps as small icons.
6. **Notification Large Image**: To display the rich, colorful P logo in notification shades, pass the transparent image URL (`static/images/p_logo.png`) or set `setLargeIcon()`.
7. **Car Horn Audio**: The emergency notification sound is an authentic automotive dual-tone car horn located at `android/app/src/main/res/raw/car_honk.wav` and `android/app/src/main/res/raw/chime.wav`.
8. **Database Schema**: To add fields to vehicles or tags, update `database.py`. All table creations use `CREATE TABLE IF NOT EXISTS`.
9. **Cloud Builds**: Keep Gradle tasks and GitHub workflows compatible with headless Ubuntu environments (`chmod +x android/gradlew`, `--no-daemon`).

