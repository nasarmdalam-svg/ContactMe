package com.example.carsafetag

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat

import android.app.AlertDialog
import android.content.Intent
import android.webkit.JavascriptInterface

class MainActivity : ComponentActivity() {

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ -> }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        createLoudNotificationChannel()
        requestAppPermissions()
        startAlertBackgroundService()
        checkIntentForAlert(intent)

        setContent {
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
                        webViewClient = WebViewClient()
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
                        }, "ParkBuzzApp")

                        loadUrl("https://contactme-go9v.onrender.com/owner/CAR-D3AEED")
                        webViewInstance = this
                    }
                }
            )
        }
    }

    private var webViewInstance: WebView? = null

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        checkIntentForAlert(intent)
    }

    private fun checkIntentForAlert(intent: Intent?) {
        if (intent?.getBooleanExtra("ALERT_POPUP", false) == true) {
            val msg = intent.getStringExtra("ALERT_MSG") ?: "Someone needs you to move your vehicle!"
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

    private fun requestAppPermissions() {
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
