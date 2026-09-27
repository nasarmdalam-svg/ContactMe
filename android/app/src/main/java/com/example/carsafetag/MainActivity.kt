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
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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

        createLoudNotificationChannel()
        requestSilentPermissions()
        startAlertBackgroundService()
        checkIntentForAlert(intent)

        setContent {
            var isLoading by remember { mutableStateOf(true) }
            var loadingStatus by remember { mutableStateOf("Securing vehicle connection...") }

            Box(modifier = Modifier.fillMaxSize()) {
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
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
                                    // If Render spin-up page is detected, keep showing splash and retry
                                    if (title.contains("starting", ignoreCase = true) || 
                                        title.contains("render", ignoreCase = true)) {
                                        loadingStatus = "Starting cloud service... Ready in moments"
                                        postDelayed({
                                            view?.reload()
                                        }, 4000)
                                    } else {
                                        isLoading = false
                                    }
                                }

                                override fun onReceivedError(
                                    view: WebView?,
                                    errorCode: Int,
                                    description: String?,
                                    failingUrl: String?
                                ) {
                                    super.onReceivedError(view, errorCode, description, failingUrl)
                                    loadingStatus = "Reconnecting to ParkBuzz network..."
                                    postDelayed({
                                        view?.loadUrl("https://contactme-go9v.onrender.com/owner/CAR-D3AEED")
                                    }, 4000)
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
                                fun getTagId(): String = "CAR-D3AEED"

                                @JavascriptInterface
                                fun onCallEnded() {
                                    runOnUiThread {
                                        ongoingCallDialog?.dismiss()
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

                            loadUrl("https://contactme-go9v.onrender.com/owner/CAR-D3AEED")
                            webViewInstance = this
                        }
                    }
                )

                AnimatedVisibility(
                    visible = isLoading,
                    enter = fadeIn(),
                    exit = fadeOut()
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color(0xFF0F172A)),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center,
                            modifier = Modifier.padding(24.dp)
                        ) {
                            Image(
                                painter = painterResource(id = R.mipmap.ic_launcher),
                                contentDescription = "ParkBuzz Logo",
                                modifier = Modifier
                                    .size(92.dp)
                                    .clip(CircleShape)
                            )
                            Spacer(modifier = Modifier.height(20.dp))
                            Text(
                                text = "ParkBuzz",
                                color = Color.White,
                                fontSize = 28.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.height(28.dp))
                            CircularProgressIndicator(
                                color = Color(0xFF38BDF8),
                                modifier = Modifier.size(36.dp),
                                strokeWidth = 3.dp
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = "Please wait...",
                                color = Color(0xFF94A3B8),
                                fontSize = 15.sp,
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
                        webViewInstance?.evaluateJavascript("if (window.soundManager) { window.soundManager.stopAlarm(); }", null)
                        d.dismiss()
                    }
                    .setNegativeButton("Dismiss") { d, _ ->
                        webViewInstance?.evaluateJavascript("if (window.soundManager) { window.soundManager.stopAlarm(); }", null)
                        d.dismiss()
                    }
                    .setCancelable(false)
                    .show()
            }
        }
    }

    private fun startAlertBackgroundService() {
        try {
            val serviceIntent = Intent(this, ParkBuzzAlertService::class.java).apply {
                putExtra("TAG_ID", "CAR-D3AEED")
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
        } catch (e: Exception) {
            e.printStackTrace()
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

    private fun requestSilentPermissions() {
        val permissions = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        val needed = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (needed.isNotEmpty()) {
            requestPermissionLauncher.launch(needed.toTypedArray())
        }
    }
}
