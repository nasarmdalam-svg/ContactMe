package com.example.carsafetag

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
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
        const val SILENT_KEEPER_CHANNEL_ID = "parkbuzz_silent_keeper"
        const val ALERT_CHANNEL_ID = "car_emergency_alerts"
        const val KEEPER_NOTIF_ID = 8801
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        intent?.getStringExtra("TAG_ID")?.let {
            if (it.isNotBlank()) tagId = it
        }

        // Low-priority, silent keeper notification to prevent Android from killing connection when closed
        startForeground(KEEPER_NOTIF_ID, buildKeeperNotification())

        if (!isRunning) {
            isRunning = true
            connectWebSocket()
        }

        return START_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        // If swiped away, restart service immediately
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

    private fun createChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            // 1. Silent, discreet keeper channel (no sound, no vibration, low priority)
            val keeperChannel = NotificationChannel(
                SILENT_KEEPER_CHANNEL_ID,
                "ParkBuzz Background Monitor",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps connection alive when app is closed"
                setShowBadge(false)
            }
            nm.createNotificationChannel(keeperChannel)

            // 2. High priority alert channel (vibration, heads-up display)
            val alertChannel = NotificationChannel(
                ALERT_CHANNEL_ID,
                "ParkBuzz Emergency Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Emergency heads-up pop-up when vehicle is blocked"
                enableLights(true)
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 500, 200, 500, 200, 1000)
            }
            nm.createNotificationChannel(alertChannel)
        }
    }

    private fun buildKeeperNotification(): Notification {
        val openIntent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, SILENT_KEEPER_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("ParkBuzz Active")
            .setContentText("Monitoring $tagId for instant parking alerts")
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun connectWebSocket() {
        Thread {
            okHttpClient = OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .pingInterval(20, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build()

            val wsUrl = "wss://contactme-go9v.onrender.com/ws/$tagId/owner"
            val request = Request.Builder().url(wsUrl).build()

            fun openConnection() {
                if (!isRunning) return
                try {
                    webSocket = okHttpClient?.newWebSocket(request, object : WebSocketListener() {
                        override fun onOpen(ws: WebSocket, response: Response) {
                            // Connected
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
                            if (isRunning) {
                                try { Thread.sleep(4000) } catch (_: Exception) {}
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

        // 2. Build Heads-Up Screen Pop-Up Notification (NO siren media player!)
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("ALERT_POPUP", true)
            putExtra("ALERT_MSG", message)
            putExtra("ALERT_TYPE", alertType)
        }
        val fullScreenPendingIntent = PendingIntent.getActivity(
            this, (System.currentTimeMillis() % 10000).toInt(), openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notif = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("🚨 ParkBuzz: ${alertType.uppercase()} ALERT")
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText("🚨 $message\n\nTap to open and silence alarm."))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setVibrate(longArrayOf(0, 500, 200, 500, 200, 1000))
            .setFullScreenIntent(fullScreenPendingIntent, true) // SCREEN POP-UP
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
