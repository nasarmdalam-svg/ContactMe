package com.example.carsafetag

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.BitmapFactory
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
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

    private var partialWakeLock: PowerManager.WakeLock? = null

    companion object {
        const val TAG = "ParkBuzzService"
        const val SILENT_KEEPER_CHANNEL_ID = "parkbuzz_silent_keeper_v9"
        const val ALERT_CHANNEL_ID = "parkbuzz_alert_popup_v9"
        const val KEEPER_NOTIF_ID = 8801
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannels()
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            partialWakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ParkBuzz:KeepAliveLock")
            partialWakeLock?.acquire()
        } catch (_: Exception) {}
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        intent?.getStringExtra("TAG_ID")?.let {
            if (it.isNotBlank()) tagId = it
        }

        // Android 14+ (API 34+) compatibility: MUST specify foregroundServiceType
        try {
            val notification = buildKeeperNotification()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                startForeground(
                    KEEPER_NOTIF_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING
                )
            } else {
                startForeground(KEEPER_NOTIF_ID, notification)
            }
            Log.d(TAG, "Foreground service started silently for tag: $tagId")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to startForeground: ${e.message}", e)
        }

        if (!isRunning) {
            isRunning = true
            connectWebSocket()
        }

        return START_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        // When user swipes away app from recent apps, broadcast to BootReceiver to guarantee keep-alive
        try {
            val restartIntent = Intent(applicationContext, BootReceiver::class.java).apply {
                action = "com.example.carsafetag.RESTART_SERVICE"
                putExtra("TAG_ID", tagId)
            }
            val pendingIntent = PendingIntent.getBroadcast(
                this, 101, restartIntent,
                PendingIntent.FLAG_ONE_SHOT or PendingIntent.FLAG_IMMUTABLE
            )
            val alarmManager = getSystemService(Context.ALARM_SERVICE) as AlarmManager
            alarmManager.set(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + 1000,
                pendingIntent
            )
        } catch (e: Exception) {
            Log.e(TAG, "Error scheduling restart: ${e.message}")
        }
        super.onTaskRemoved(rootIntent)
    }

    private fun createChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

            // 1. Silent keeper channel (MIN importance ensures NO icon on top status bar while keeping service alive)
            val keeperChannel = NotificationChannel(
                SILENT_KEEPER_CHANNEL_ID,
                "ParkBuzz Background Service",
                NotificationManager.IMPORTANCE_MIN
            ).apply {
                description = "Keeps ParkBuzz connected silently in background"
                setShowBadge(false)
                enableLights(false)
                enableVibration(false)
                setSound(null, null)
            }
            nm.createNotificationChannel(keeperChannel)

            // 2. High priority alert channel (Heads-up pop-up on screen)
            val alertChannel = NotificationChannel(
                ALERT_CHANNEL_ID,
                "ParkBuzz Emergency Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Emergency heads-up alert when vehicle is blocked"
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
            .setContentText("Monitoring silently in background")
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .setShowWhen(false)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setVisibility(NotificationCompat.VISIBILITY_SECRET)
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
                    Log.d(TAG, "Connecting to WebSocket: $wsUrl")
                    webSocket = okHttpClient?.newWebSocket(request, object : WebSocketListener() {
                        override fun onOpen(ws: WebSocket, response: Response) {
                            Log.d(TAG, "WebSocket connected successfully!")
                        }

                        override fun onMessage(ws: WebSocket, text: String) {
                            Log.d(TAG, "WebSocket message received: $text")
                            try {
                                val json = JSONObject(text)
                                val type = json.optString("type")
                                if (type == "alert_received" || type == "alert") {
                                    val alertType = json.optString("alert_type", "URGENT")
                                    val message = json.optString("message", "Someone needs you to move your vehicle!")
                                    fireEmergencyAlert(alertType, message)
                                } else if (type == "call_request" || type == "incoming_call") {
                                    fireEmergencyAlert("incoming_call", "A bystander near your vehicle is calling you live!")
                                }
                            } catch (e: Exception) {
                                Log.e(TAG, "Error parsing message: ${e.message}")
                            }
                        }

                        override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                            Log.w(TAG, "WebSocket failure: ${t.message}. Reconnecting in 4s...")
                            if (isRunning) {
                                try { Thread.sleep(4000) } catch (_: Exception) {}
                                openConnection()
                            }
                        }

                        override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                            Log.w(TAG, "WebSocket closed: $reason. Reconnecting in 3s...")
                            if (isRunning) {
                                try { Thread.sleep(3000) } catch (_: Exception) {}
                                openConnection()
                            }
                        }
                    })
                } catch (e: Exception) {
                    Log.e(TAG, "Exception opening WebSocket: ${e.message}")
                    if (isRunning) {
                        try { Thread.sleep(5000) } catch (_: Exception) {}
                        openConnection()
                    }
                }
            }

            openConnection()
        }.start()
    }

    private fun fireEmergencyAlert(alertType: String, message: String) {
        // 1. Wake up the screen if phone is locked in pocket
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            @Suppress("DEPRECATION")
            val wakeLock = pm.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP or PowerManager.ON_AFTER_RELEASE,
                "ParkBuzz:AlertWakeLock"
            )
            wakeLock.acquire(10000)
        } catch (_: Exception) {}

        // 2. Play the clean chime audio file embedded inside the app (res/raw/chime.wav)
        try {
            val soundUri = Uri.parse("android.resource://$packageName/${R.raw.chime}")
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
        } catch (e: Exception) {
            Log.e(TAG, "Chime playback error: ${e.message}")
        }

        // 3. Show Heads-Up Screen Pop-Up Notification
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

        val isCall = alertType.equals("incoming_call", ignoreCase = true) || alertType.contains("call", ignoreCase = true)
        val notifTitle = if (isCall) "📞 Incoming Voice Call" else "🚨 ParkBuzz: ${alertType.uppercase()} ALERT"
        val notifBigText = if (isCall) "📞 A bystander near your vehicle is calling you live.\n\nTap to Answer or Decline." else "🚨 $message\n\nTap to open app and silence."

        val appLogo = try {
            BitmapFactory.decodeResource(resources, R.mipmap.ic_launcher)
        } catch (_: Exception) { null }

        val notifBuilder = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setColor(0xFF38BDF8.toInt())
            .setContentTitle(notifTitle)
            .setContentText(if (isCall) "Incoming Voice Call..." else message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(notifBigText))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setVibrate(longArrayOf(0, 500, 200, 500, 200, 1000))
            .setFullScreenIntent(fullScreenPendingIntent, true) // SCREEN POP-UP
            .setContentIntent(fullScreenPendingIntent)
            .setAutoCancel(true)

        if (appLogo != null) {
            notifBuilder.setLargeIcon(appLogo)
        }

        val notif = notifBuilder.build()

        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify((System.currentTimeMillis() % 10000).toInt(), notif)
    }

    override fun onDestroy() {
        isRunning = false
        try { partialWakeLock?.release() } catch (_: Exception) {}
        try { webSocket?.close(1000, "Service stopped") } catch (_: Exception) {}
        super.onDestroy()
    }
}
