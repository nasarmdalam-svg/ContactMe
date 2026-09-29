package com.example.carsafetag

import android.Manifest
import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import com.google.firebase.messaging.FirebaseMessaging
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import com.google.firebase.FirebaseApp
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat

class MainActivity : ComponentActivity() {

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ -> }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        activeInstance = this

        // Enforce dark status bar and navigation bar styling across all Android OS versions
        try {
            enableEdgeToEdge(
                statusBarStyle = SystemBarStyle.dark(android.graphics.Color.parseColor("#090e19")),
                navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.parseColor("#090e19"))
            )
        } catch (e: Exception) {}
        try {
            window.statusBarColor = android.graphics.Color.parseColor("#090e19")
            window.navigationBarColor = android.graphics.Color.parseColor("#090e19")
        } catch (e: Exception) {}

        // Firebase initialized via Application class



        // Prompt for runtime permissions (Notifications & Audio)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            requestPermissionLauncher.launch(
                arrayOf(
                    android.Manifest.permission.POST_NOTIFICATIONS,
                    android.Manifest.permission.RECORD_AUDIO
                )
            )
        } else {
            requestPermissionLauncher.launch(
                arrayOf(
                    android.Manifest.permission.RECORD_AUDIO
                )
            )
        }

        // Initialize Firebase FCM Token and register with backend for millions-of-devices support
        try {
            FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    val token = task.result
                    android.util.Log.d("ParkBuzzFCM", "Initial FCM token retrieved: $token")
                    val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
                    val tagId = prefs.getString("ACTIVE_TAG_ID", null)
                    if (!tagId.isNullOrBlank()) {
                        ParkBuzzFirebaseMessagingService.registerTokenWithServer(this, token, tagId)
                    }
                }
            }
        } catch (e: Exception) {
            android.util.Log.e("ParkBuzzFCM", "Failed to get FCM token: ${e.message}")
        }

        // Trigger fast background HTTP pre-warm ping in parallel with UI init
        Thread {
            try {
                val client = okhttp3.OkHttpClient.Builder()
                    .connectTimeout(6, java.util.concurrent.TimeUnit.SECONDS)
                    .readTimeout(6, java.util.concurrent.TimeUnit.SECONDS)
                    .build()
                val req = okhttp3.Request.Builder().url("https://contactme-go9v.onrender.com/ping").build()
                client.newCall(req).execute()
            } catch (e: Exception) {}
        }.start()

        setContent {
            var isLoading by remember { mutableStateOf(true) }
            var loadingStatus by remember { mutableStateOf("Securing vehicle connection...") }

            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0xFF090E19))
            ) {
                AndroidView(
                    modifier = Modifier
                        .fillMaxSize()
                        .statusBarsPadding()
                        .navigationBarsPadding()
                        .imePadding(),
                    factory = { context ->
                        WebView(context).apply {
                            layoutParams = ViewGroup.LayoutParams(
                                ViewGroup.LayoutParams.MATCH_PARENT,
                                ViewGroup.LayoutParams.MATCH_PARENT
                            )
                            settings.apply {
                                javaScriptEnabled = true
                                domStorageEnabled = true
                                databaseEnabled = true
                                mediaPlaybackRequiresUserGesture = false
                                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                                cacheMode = WebSettings.LOAD_DEFAULT
                            }
                            webViewClient = object : WebViewClient() {
                                override fun onPageFinished(view: WebView?, url: String?) {
                                    super.onPageFinished(view, url)
                                    val title = view?.title ?: ""
                                    // Inspect title AND body text to catch Render free-tier spin-up screens
                                    view?.evaluateJavascript("(function(){ return document.body ? (document.body.innerText || '') : ''; })()") { bodyContent ->
                                        val body = (bodyContent ?: "").replace("\\n", " ").lowercase()
                                        val isSpinningUp = title.contains("starting", ignoreCase = true) || 
                                                           title.contains("render", ignoreCase = true) ||
                                                           body.contains("spinning up") ||
                                                           body.contains("please wait") ||
                                                           body.contains("service is starting") ||
                                                           body.contains("503 service") ||
                                                           body.contains("502 bad gateway")

                                        if (isSpinningUp) {
                                            isLoading = true
                                            loadingStatus = "Connecting to ParkingBuzz Cloud..."
                                            view.postDelayed({
                                                view.reload()
                                            }, 2500)
                                        } else {
                                            isLoading = false
                                        }
                                    }
                                }

                                private fun showOfflinePage(view: WebView?, failingUrl: String?) {
                                    isLoading = false
                                    val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
                                    val tag = prefs.getString("ACTIVE_TAG_ID", null)
                                    val targetUrl = failingUrl ?: if (!tag.isNullOrBlank()) {
                                        "https://contactme-go9v.onrender.com/owner/$tag"
                                    } else {
                                        "https://contactme-go9v.onrender.com/register"
                                    }
                                    val offlineHtml = getOfflineHtml(targetUrl)
                                    view?.loadDataWithBaseURL("https://contactme-go9v.onrender.com/", offlineHtml, "text/html", "UTF-8", null)
                                }

                                override fun onReceivedError(
                                    view: WebView?,
                                    errorCode: Int,
                                    description: String?,
                                    failingUrl: String?
                                ) {
                                    showOfflinePage(view, failingUrl)
                                }

                                override fun onReceivedError(
                                    view: WebView?,
                                    request: android.webkit.WebResourceRequest?,
                                    error: android.webkit.WebResourceError?
                                ) {
                                    if (request?.isForMainFrame == true) {
                                        showOfflinePage(view, request.url.toString())
                                    }
                                }
                            }
                            webChromeClient = object : WebChromeClient() {
                                override fun onPermissionRequest(request: PermissionRequest?) {
                                    request?.grant(request.resources)
                                }
                            }
                            addJavascriptInterface(object {
                                @JavascriptInterface
                                fun isParkBuzzApp(): Boolean = true

                                @JavascriptInterface
                                fun getTagId(): String {
                                    val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
                                    return prefs.getString("ACTIVE_TAG_ID", "") ?: ""
                                }

                                @JavascriptInterface
                                fun onTagLoaded(newTagId: String) {
                                    if (newTagId.isNotBlank()) {
                                        val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
                                        prefs.edit().putString("ACTIVE_TAG_ID", newTagId).apply()
                                        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                                            ParkBuzzFirebaseMessagingService.registerTokenWithServer(this@MainActivity, token, newTagId)
                                        }
                                    }
                                }

                                @JavascriptInterface
                                fun onCallEnded() {
                                    runOnUiThread {
                                        ongoingCallDialog?.dismiss()
                                    }
                                }

                                @JavascriptInterface
                                fun logout() {
                                    performAppLogout()
                                }

                                @JavascriptInterface
                                fun retryConnection() {
                                    runOnUiThread {
                                        isLoading = true
                                        loadingStatus = "Reconnecting to ParkingBuzz..."
                                        val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
                                        val tag = prefs.getString("ACTIVE_TAG_ID", null)
                                        val retryUrl = if (!tag.isNullOrBlank()) {
                                            "https://contactme-go9v.onrender.com/owner/$tag"
                                        } else {
                                            "https://contactme-go9v.onrender.com/register"
                                        }
                                        webViewInstance?.loadUrl(retryUrl)
                                    }
                                }
                            }, "ParkBuzzApp")

                            setDownloadListener { url, _, _, _, _ ->
                                try {
                                    val downloadIntent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                                    context.startActivity(downloadIntent)
                                } catch (e: Exception) {
                                    e.printStackTrace()
                                }
                            }

                            val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
                            val savedTag = prefs.getString("ACTIVE_TAG_ID", null)
                            val startUrl = if (!savedTag.isNullOrBlank()) {
                                "https://contactme-go9v.onrender.com/owner/$savedTag"
                            } else {
                                "https://contactme-go9v.onrender.com/register"
                            }
                            loadUrl(startUrl)
                            webViewInstance = this
                        }
                    }
                )

                AnimatedVisibility(
                    visible = isLoading,
                    enter = fadeIn(),
                    exit = fadeOut()
                ) {
                    val infiniteTransition = rememberInfiniteTransition(label = "car_drive")
                    val carOffset by infiniteTransition.animateFloat(
                        initialValue = -70f,
                        targetValue = 70f,
                        animationSpec = infiniteRepeatable(
                            animation = tween(1400, easing = LinearEasing),
                            repeatMode = RepeatMode.Reverse
                        ),
                        label = "car_x"
                    )
                    val carBounce by infiniteTransition.animateFloat(
                        initialValue = 0f,
                        targetValue = -3f,
                        animationSpec = infiniteRepeatable(
                            animation = tween(280, easing = FastOutSlowInEasing),
                            repeatMode = RepeatMode.Reverse
                        ),
                        label = "car_y"
                    )

                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color(0xFF0F172A))
                            .statusBarsPadding()
                            .navigationBarsPadding(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center,
                            modifier = Modifier.padding(24.dp)
                        ) {
                            Image(
                                painter = painterResource(id = R.mipmap.ic_launcher),
                                contentDescription = "ParkingBuzz Logo",
                                modifier = Modifier
                                    .size(92.dp)
                                    .clip(CircleShape)
                            )
                            Spacer(modifier = Modifier.height(18.dp))
                            Text(
                                text = "ParkingBuzz",
                                color = Color.White,
                                fontSize = 28.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.height(26.dp))

                            // Animated Car Driving on Glowing Road Track
                            Box(
                                modifier = Modifier
                                    .width(220.dp)
                                    .height(54.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                // Road line track
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(3.dp)
                                        .align(Alignment.BottomCenter)
                                        .background(
                                            brush = Brush.horizontalGradient(
                                                colors = listOf(
                                                    Color.Transparent,
                                                    Color(0xFF38BDF8),
                                                    Color(0xFF2563EB),
                                                    Color.Transparent
                                                )
                                            ),
                                            shape = RoundedCornerShape(2.dp)
                                        )
                                )
                                // Gliding Car
                                Text(
                                    text = "🚗",
                                    fontSize = 32.sp,
                                    modifier = Modifier
                                        .offset(x = carOffset.dp, y = carBounce.dp)
                                        .align(Alignment.Center)
                                )
                            }
                            Spacer(modifier = Modifier.height(18.dp))
                            Text(
                                text = loadingStatus,
                                color = Color(0xFF94A3B8),
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }
            }
        }
    }

    private var webViewInstance: WebView? = null
    private var ongoingCallDialog: AlertDialog? = null

    private fun showOngoingCallDialog() {
        runOnUiThread {
            ongoingCallDialog?.dismiss()
            ongoingCallDialog = AlertDialog.Builder(this)
                .setTitle("📞 Active Voice Call")
                .setMessage("Speaking live with bystander near your vehicle.")
                .setPositiveButton("🔴 Disconnect / End Call") { d, _ ->
                    webViewInstance?.evaluateJavascript("if (document.getElementById('btnHangupCall')) { document.getElementById('btnHangupCall').click(); }", null)
                    d.dismiss()
                }
                .setCancelable(false)
                .show()
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        checkIntentForAlert(intent)
    }

    private fun checkIntentForAlert(intent: Intent?) {
        if (intent?.getBooleanExtra("ALERT_POPUP", false) == true) {
            val alertType = intent.getStringExtra("ALERT_TYPE") ?: ""
            val msg = intent.getStringExtra("ALERT_MSG") ?: "Someone needs you to move your vehicle!"

            if (alertType.equals("incoming_call", ignoreCase = true) || alertType.contains("call", ignoreCase = true)) {
                AlertDialog.Builder(this)
                    .setTitle("📞 Incoming Voice Call")
                    .setMessage("A bystander near your vehicle is calling you live!")
                    .setPositiveButton("🟢 Accept Call") { d, _ ->
                        webViewInstance?.evaluateJavascript("if (document.getElementById('btnAcceptCall')) { document.getElementById('btnAcceptCall').click(); }", null)
                        d.dismiss()
                        showOngoingCallDialog()
                    }
                    .setNegativeButton("🔴 Decline") { d, _ ->
                        webViewInstance?.evaluateJavascript("if (document.getElementById('btnRejectCall')) { document.getElementById('btnRejectCall').click(); }", null)
                        d.dismiss()
                    }
                    .setCancelable(false)
                    .show()
            } else {
                AlertDialog.Builder(this)
                    .setTitle("🚨 URGENT PARKING ALERT")
                    .setMessage(msg)
                    .setPositiveButton("I Am On My Way") { d, _ ->
                        AlertSoundPlayer.stop()
                        webViewInstance?.evaluateJavascript("if (window.soundManager) { window.soundManager.stopAlarm(); }", null)
                        d.dismiss()
                    }
                    .setNegativeButton("Dismiss") { d, _ ->
                        AlertSoundPlayer.stop()
                        webViewInstance?.evaluateJavascript("if (window.soundManager) { window.soundManager.stopAlarm(); }", null)
                        d.dismiss()
                    }
                    .setCancelable(false)
                    .show()
            }
        }
    }


    private fun createLoudNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channelId = "car_emergency_alerts"
            val channelName = "ParkBuzz Urgent Alerts"
            val importance = NotificationManager.IMPORTANCE_HIGH
            val channel = NotificationChannel(channelId, channelName, importance).apply {
                description = "Alert pop-up when someone scans your ParkBuzz vehicle sticker"
                enableLights(true)
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 500, 200, 500, 200, 1000)
            }

            val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    fun performAppLogout() {
        val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
        val oldTag = prefs.getString("ACTIVE_TAG_ID", null)
        prefs.edit().remove("ACTIVE_TAG_ID").commit()

        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (task.isSuccessful) {
                val token = task.result
                if (!token.isNullOrBlank() && !oldTag.isNullOrBlank()) {
                    ParkBuzzFirebaseMessagingService.unregisterTokenWithServer(this@MainActivity, token, oldTag)
                }
            }
            try {
                FirebaseMessaging.getInstance().deleteToken()
            } catch (e: Exception) {
                android.util.Log.e("MainActivity", "Error deleting FCM token: ${e.message}")
            }
        }

        runOnUiThread {
            try {
                android.webkit.WebStorage.getInstance().deleteAllData()
                val cm = android.webkit.CookieManager.getInstance()
                cm.removeAllCookies(null)
                cm.flush()
            } catch (e: Exception) {}
            webViewInstance?.clearCache(true)
            webViewInstance?.clearHistory()
            webViewInstance?.loadUrl("https://contactme-go9v.onrender.com/register?mode=logged_out")
        }
    }

    private fun getOfflineHtml(targetUrl: String): String {
        return """
            <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
              <title>Offline — ParkingBuzz</title>
              <style>
                * { box-sizing: border-box; margin: 0; padding: 0; }
                body {
                  background: radial-gradient(circle at 50% 18%, #172554 0%, #090e19 75%, #050811 100%);
                  color: #f1f5f9;
                  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                  min-height: 100vh;
                  display: flex;
                  flex-direction: column;
                  align-items: center;
                  justify-content: center;
                  padding: 30px 24px;
                  text-align: center;
                  -webkit-font-smoothing: antialiased;
                  user-select: none;
                }
                .badge-wrap {
                  position: relative;
                  width: 100px;
                  height: 100px;
                  margin-bottom: 24px;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                }
                .pulse-ring {
                  position: absolute;
                  inset: -12px;
                  border-radius: 50%;
                  border: 2px solid rgba(56, 189, 248, 0.4);
                  animation: pulse 2.4s infinite cubic-bezier(0.2, 0.8, 0.2, 1);
                }
                .pulse-ring-2 {
                  position: absolute;
                  inset: -24px;
                  border-radius: 50%;
                  border: 1px solid rgba(56, 189, 248, 0.2);
                  animation: pulse 2.4s infinite cubic-bezier(0.2, 0.8, 0.2, 1) 0.8s;
                }
                @keyframes pulse {
                  0% { transform: scale(0.85); opacity: 0.8; }
                  50% { transform: scale(1.08); opacity: 0.3; }
                  100% { transform: scale(1.25); opacity: 0; }
                }
                .logo-glow {
                  width: 90px;
                  height: 90px;
                  border-radius: 50%;
                  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                  border: 2px solid rgba(56, 189, 248, 0.5);
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), inset 0 0 15px rgba(56, 189, 248, 0.2);
                  font-size: 40px;
                  position: relative;
                  z-index: 2;
                }
                .status-pill {
                  display: inline-flex;
                  align-items: center;
                  gap: 6px;
                  padding: 6px 14px;
                  border-radius: 999px;
                  background: rgba(239, 68, 68, 0.15);
                  border: 1px solid rgba(239, 68, 68, 0.35);
                  color: #f87171;
                  font-size: 11px;
                  font-weight: 800;
                  letter-spacing: 0.6px;
                  text-transform: uppercase;
                  margin-bottom: 16px;
                }
                .status-dot {
                  width: 7px;
                  height: 7px;
                  border-radius: 50%;
                  background: #ef4444;
                  box-shadow: 0 0 8px #ef4444;
                }
                h1 {
                  font-size: 23px;
                  font-weight: 900;
                  color: #ffffff;
                  letter-spacing: -0.5px;
                  margin-bottom: 10px;
                }
                p {
                  font-size: 13.5px;
                  color: #94a3b8;
                  line-height: 1.6;
                  max-width: 310px;
                  margin-bottom: 28px;
                }
                .btn-retry {
                  width: 100%;
                  max-width: 290px;
                  padding: 15px 24px;
                  background: linear-gradient(135deg, #38bdf8 0%, #2563eb 100%);
                  color: #040812;
                  border: none;
                  border-radius: 14px;
                  font-size: 15px;
                  font-weight: 800;
                  letter-spacing: 0.3px;
                  cursor: pointer;
                  box-shadow: 0 10px 25px rgba(37, 99, 235, 0.45);
                  transition: all 0.2s ease;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  gap: 8px;
                  text-decoration: none;
                }
                .btn-retry:active {
                  transform: scale(0.97);
                }
                .tip-box {
                  margin-top: 32px;
                  padding: 14px 18px;
                  border-radius: 14px;
                  background: rgba(255, 255, 255, 0.03);
                  border: 1px solid rgba(255, 255, 255, 0.08);
                  font-size: 12px;
                  color: #64748b;
                  max-width: 290px;
                  display: flex;
                  align-items: center;
                  gap: 10px;
                  text-align: left;
                }
              </style>
            </head>
            <body>
              <div class="badge-wrap">
                <div class="pulse-ring"></div>
                <div class="pulse-ring-2"></div>
                <div class="logo-glow">📡</div>
              </div>

              <div class="status-pill">
                <span class="status-dot"></span>
                Offline Mode
              </div>

              <h1>Connection Lost</h1>
              <p>ParkingBuzz requires an active internet connection to protect your vehicle and synchronize real-time alerts.</p>

              <button class="btn-retry" id="retryBtn" onclick="doRetry()">
                <span>🔄</span>
                <span id="retryBtnText">Retry Connection</span>
              </button>

              <div class="tip-box">
                <span style="font-size: 18px;">💡</span>
                <span>Check your Wi-Fi or mobile data settings. The app will automatically reconnect as soon as signal is detected.</span>
              </div>

              <script>
                function doRetry() {
                  const btn = document.getElementById('retryBtnText');
                  btn.textContent = 'Connecting...';
                  if (window.ParkBuzzApp && window.ParkBuzzApp.retryConnection) {
                    window.ParkBuzzApp.retryConnection();
                  } else {
                    window.location.reload();
                  }
                }

                window.addEventListener('online', function() {
                  doRetry();
                });
              </script>
            </body>
            </html>
        """.trimIndent()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (activeInstance == this) {
            activeInstance = null
        }
    }

    companion object {
        var activeInstance: MainActivity? = null
            private set

        fun reloadActiveWebView() {
            activeInstance?.runOnUiThread {
                activeInstance?.webViewInstance?.reload()
            }
        }

        fun triggerLogout() {
            activeInstance?.runOnUiThread {
                activeInstance?.performAppLogout()
            }
        }
    }
}

