package com.example.carsafetag

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class ParkBuzzFirebaseMessagingService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "ParkBuzzFCM"
        const val ALERT_CHANNEL_ID = "parkbuzz_alert_popup_v9"

        fun registerTokenWithServer(context: Context, token: String, tagId: String = "CAR-D3AEED") {
            Thread {
                try {
                    val client = OkHttpClient()
                    val payload = JSONObject().apply {
                        put("fcm_token", token)
                        put("device_type", "android")
                    }
                    val body = payload.toString().toRequestBody("application/json".toMediaType())
                    val request = Request.Builder()
                        .url("https://contactme-go9v.onrender.com/api/fcm/register/$tagId")
                        .post(body)
                        .build()
                    val response = client.newCall(request).execute()
                    Log.d(TAG, "FCM token registered with server for tag $tagId: code ${response.code}")
                } catch (e: Exception) {
                    Log.e(TAG, "Error registering FCM token: ${e.message}")
                }
            }.start()
        }
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d(TAG, "New FCM Token received: $token")
        // Retrieve stored active tag ID
        val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
        val tagId = prefs.getString("ACTIVE_TAG_ID", "CAR-D3AEED") ?: "CAR-D3AEED"
        registerTokenWithServer(this, token, tagId)
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)
        Log.d(TAG, "FCM message received: data=${remoteMessage.data}, notif=${remoteMessage.notification?.title}")

        val data = remoteMessage.data
        val alertType = data["alert_type"] ?: remoteMessage.notification?.title ?: "blocking"
        val message = data["message"] ?: remoteMessage.notification?.body ?: "Someone is alerting your vehicle!"

        fireEmergencyAlert(alertType, message)
    }

    private fun fireEmergencyAlert(alertType: String, message: String) {
        Log.d(TAG, "fireEmergencyAlert triggered for: $alertType - $message")
        // 1. Ensure high priority alert channel exists first!
        createAlertChannelIfNeeded()

        // 2. Wake up the screen even if phone is deeply asleep / locked in pocket
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
            @Suppress("DEPRECATION")
            val wakeLock = pm.newWakeLock(
                PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP or PowerManager.ON_AFTER_RELEASE,
                "ParkBuzz:FCMWakeLock"
            )
            wakeLock.acquire(10000)
        } catch (e: Exception) {
            Log.e(TAG, "WakeLock error: ${e.message}")
        }

        // 2. Play the loud chime sound
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

        // 3. Ensure high priority alert channel exists
        createAlertChannelIfNeeded()

        // 4. Show Full-Screen / Heads-Up Pop-Up Notification
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
        val notifTitle = if (isCall) "📞 Incoming Voice Call" else "🚨 ParkingBuzz: ${alertType.uppercase()} ALERT"
        val notifBigText = if (isCall) "📞 A bystander near your vehicle is calling you live.\n\nTap to Answer or Decline." else "🚨 $message\n\nTap to open app and silence."

        val appLogo = try {
            BitmapFactory.decodeResource(resources, R.mipmap.ic_launcher)
        } catch (_: Exception) { null }

        val notifBuilder = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_parkbuzz)
            .setColor(0xFF38BDF8.toInt())
            .setContentTitle(notifTitle)
            .setContentText(if (isCall) "Incoming Voice Call..." else message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(notifBigText))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setVibrate(longArrayOf(0, 500, 200, 500, 200, 1000))
            .setFullScreenIntent(fullScreenPendingIntent, true)
            .setContentIntent(fullScreenPendingIntent)
            .setAutoCancel(true)

        if (appLogo != null) {
            notifBuilder.setLargeIcon(appLogo)
        }

        val notif = notifBuilder.build()
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify((System.currentTimeMillis() % 10000).toInt(), notif)
    }

    private fun createAlertChannelIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val alertChannel = NotificationChannel(
                ALERT_CHANNEL_ID,
                "ParkingBuzz Emergency Alerts",
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
}
