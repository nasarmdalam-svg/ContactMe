package com.example.carsafetag

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class ParkBuzzAlertService : Service() {

    private var okHttpClient: OkHttpClient? = null
    private var webSocket: WebSocket? = null
    private var isRunning = false
    private var tagId = "CAR-D3AEED"

    companion object {
        const val ALERT_CHANNEL_ID = "car_emergency_alerts"
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createAlertNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        intent?.getStringExtra("TAG_ID")?.let {
            if (it.isNotBlank()) tagId = it
        }

        // Run SILENTLY in the background - NO status bar notification icon!
        if (!isRunning) {
            isRunning = true
            connectWebSocket()
        }

        return START_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        // If user swipes app away from recents, silently restart within 1 second
        try {
            val restartIntent = Intent(applicationContext, ParkBuzzAlertService::class.java).apply {
                putExtra("TAG_ID", tagId)
            }
            val pendingIntent = PendingIntent.getService(
                this, 101, restartIntent,
                PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
            )
            val alarmManager = getSystemService(Context.ALARM_SERVICE) as AlarmManager
            alarmManager.set(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + 1000,
                pendingIntent
            )
        } catch (_: Exception) {}
        super.onTaskRemoved(rootIntent)
    }

    private fun createAlertNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val alertChannel = NotificationChannel(
                ALERT_CHANNEL_ID,
                "ParkBuzz Urgent Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Loud siren and screen pop-up when someone scans your vehicle sticker"
                enableLights(true)
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 500, 200, 500, 200, 1000)

                val audioAttributes = AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .build()

                val soundUri = Uri.parse("android.resource://$packageName/${R.raw.alarm}")
                setSound(soundUri, audioAttributes)
            }
            nm.createNotificationChannel(alertChannel)
        }
    }

    private fun connectWebSocket() {
        Thread {
            okHttpClient = OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .pingInterval(25, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build()

            val wsUrl = "wss://contactme-go9v.onrender.com/ws/$tagId/owner"
            val request = Request.Builder().url(wsUrl).build()

            fun openConnection() {
                if (!isRunning) return
                try {
                    webSocket = okHttpClient?.newWebSocket(request, object : WebSocketListener() {
                        override fun onOpen(ws: WebSocket, response: Response) {
                            // Connected silently
                        }

                        override fun onMessage(ws: WebSocket, text: String) {
                            try {
                                val json = JSONObject(text)
                                val type = json.optString("type")
                                if (type == "alert_received" || type == "alert") {
                                    val alertType = json.optString("alert_type", "URGENT")
                                    val message = json.optString("message", "Someone scanned your vehicle sticker!")
                                    fireEmergencyPopUp(alertType, message)
                                }
                            } catch (_: Exception) {}
                        }

                        override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                            // Reconnect after 5 seconds if connection fails
                            if (isRunning) {
                                try { Thread.sleep(5000) } catch (_: Exception) {}
                                openConnection()
                            }
                        }

                        override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                            if (isRunning) {
                                try { Thread.sleep(3000) } catch (_: Exception) {}
                                openConnection()
                            }
                        }
                    })
                } catch (_: Exception) {
                    if (isRunning) {
                        try { Thread.sleep(5000) } catch (_: Exception) {}
                        openConnection()
                    }
                }
            }

            openConnection()
        }.start()
    }

    private fun fireEmergencyPopUp(alertType: String, message: String) {
        // 1. Wake up screen immediately
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            @Suppress("DEPRECATION")
            val wakeLock = pm.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP or PowerManager.ON_AFTER_RELEASE,
                "ParkBuzz:AlertWakeLock"
            )
            wakeLock.acquire(10000)
        } catch (_: Exception) {}

        // 2. Play the loud siren audio immediately
        try {
            val soundUri = Uri.parse("android.resource://$packageName/${R.raw.alarm}")
            val mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .build()
                )
                setDataSource(applicationContext, soundUri)
                prepare()
                start()
            }
            mediaPlayer.setOnCompletionListener { it.release() }
        } catch (_: Exception) {}

        // 3. Show Heads-Up Screen Pop-Up
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("ALERT_POPUP", true)
            putExtra("ALERT_MSG", message)
        }
        val fullScreenPendingIntent = PendingIntent.getActivity(
            this, (System.currentTimeMillis() % 10000).toInt(), openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val soundUri = Uri.parse("android.resource://$packageName/${R.raw.alarm}")

        val notif = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("🚨 ParkBuzz: ${alertType.uppercase()} ALERT")
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText("🚨 $message\n\nPlease check or move your vehicle!"))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setSound(soundUri)
            .setVibrate(longArrayOf(0, 500, 200, 500, 200, 1000))
            .setFullScreenIntent(fullScreenPendingIntent, true) // SCREEN POP-UP!
            .setContentIntent(fullScreenPendingIntent)
            .setAutoCancel(true)
            .build()

        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify((System.currentTimeMillis() % 10000).toInt(), notif)
    }

    override fun onDestroy() {
        isRunning = false
        try { webSocket?.close(1000, "Service stopped") } catch (_: Exception) {}
        super.onDestroy()
    }
}
