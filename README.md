# 🚗 Car SafeTag - 100% Free Anonymous Car QR Sticker System

A privacy-focused, zero-cost QR code sticker system for vehicles. When someone scans the sticker on a car, they can send instant parking alerts with loud sound and start a direct voice call with the car owner without exchanging or revealing either party's phone number.

---

### ✨ Key Features

- **🛡️ 100% Private (Number Masking)**: Neither the bystander nor the car owner ever reveals their phone number or identity.
- **💸 100% Free Forever**:
  - No Twilio, no paid SMS, no per-minute telecom carrier bills.
  - No Telegram or WhatsApp bots required.
  - Uses free W3C **Web Push (VAPID)** and **WebRTC** peer-to-peer audio.
- **🔊 Loud Sound Alarm**: Triggers an alert alarm and vibration on the owner's phone.
- **📞 In-Browser Voice Calling (WebRTC)**: Direct live audio stream between both browsers via Google's free public STUN servers.
- **☁️ 24/7 Cloud Ready**: Deploy free to Render or Railway from GitHub so your computer never needs to stay on.
- **🖨️ Batch Sticker Generator**: CLI script to generate high-resolution, ready-to-print PNG QR stickers.

---

### 🚀 Quick Start (Local Testing)

1. **Activate the environment**:
   ```bash
   source venv/bin/activate
   ```

2. **Start the server**:
   ```bash
   uvicorn server:app --reload --port 8000
   ```

3. **Try it in your browser**:
   - Open [http://localhost:8000/activate/CAR-DEMO1](http://localhost:8000/activate/CAR-DEMO1) to activate a sample sticker.
   - Enter your car name and click **Activate**.
   - On the Owner Dashboard, click **Enable Push & Sound** (and test with **🔊 Test Sound**).
   - In an incognito tab or on another device, open [http://localhost:8000/c/CAR-DEMO1](http://localhost:8000/c/CAR-DEMO1).
   - Tap any parking alert or click **Call Owner** to watch the real-time ringing and live audio!

---

### 🖨️ Generating Printable QR Stickers

To generate a batch of ready-to-print stickers:

```bash
# Generate 10 stickers for your production cloud domain
python generate_stickers.py --count 10 --domain https://your-app.onrender.com
```

The stickers will be saved in `stickers_output/` as high-resolution PNG images formatted with:
- Top banner: *CAR CONTACT TAG - PARKED & BLOCKING? SCAN BELOW*
- High-contrast QR code centered.
- Clear instructions for bystanders.
- Unique Tag ID.

---

### ☁️ How to Host 24/7 for Free (Without Keeping Your Laptop On)

#### Step 1: Create a GitHub Repository
1. Go to [github.com/new](https://github.com/new) and create a new repository (e.g. `car-safetag`).
2. In your terminal inside this folder, run:
   ```bash
   git commit -m "Initial commit of Car SafeTag system"
   git remote add origin https://github.com/YOUR_USERNAME/car-safetag.git
   git branch -M main
   git push -u origin main
   ```

#### Step 2: Deploy to Render.com for Free (24/7/365)
1. Sign up for a free account at [render.com](https://render.com).
2. Click **New +** $\rightarrow$ **Web Service**.
3. Select your GitHub repository (`car-safetag`).
4. Render will auto-detect the configuration from `render.yaml` or set:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
5. Click **Create Web Service**.

Within 2 minutes, Render will assign you a live HTTPS URL (e.g. `https://car-safetag.onrender.com`).
Now you can print your stickers using that URL, stick them on cars, and the system runs 24/7 with zero maintenance!

---

### 📱 Adding to Home Screen (PWA)
Car owners can tap **Share $\rightarrow$ Add to Home Screen** on Safari (iOS) or Chrome (Android) to install the Owner Dashboard as an app on their phone for instant access.
