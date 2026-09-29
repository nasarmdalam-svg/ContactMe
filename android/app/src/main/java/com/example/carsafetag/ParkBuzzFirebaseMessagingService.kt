package com.example.carsafetag

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.media.AudioAttributes
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.RemoteInput
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
        const val ALERT_CHANNEL_ID = "parkbuzz_alert_horn_v10"
        const val STATUS_CHANNEL_ID = "parkbuzz_status_v11"
        private var lastAlertKey = ""
        private var lastAlertTimeMs = 0L

        fun registerTokenWithServer(context: Context, token: String, tagId: String) {
            if (tagId.isBlank()) return
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

        fun unregisterTokenWithServer(context: Context, token: String, tagId: String) {
            if (token.isBlank() || tagId.isBlank()) return
            Thread {
                try {
                    val client = OkHttpClient()
                    val payload = JSONObject().apply {
                        put("fcm_token", token)
                        put("device_type", "android")
                    }
                    val body = payload.toString().toRequestBody("application/json".toMediaType())
                    val request = Request.Builder()
                        .url("https://contactme-go9v.onrender.com/api/fcm/unregister/$tagId")
                        .post(body)
                        .build()
                    val response = client.newCall(request).execute()
                    Log.d(TAG, "FCM token unregistered from server for tag $tagId: code ${response.code}")
                } catch (e: Exception) {
                    Log.e(TAG, "Error unregistering FCM token: ${e.message}")
                }
            }.start()
        }
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d(TAG, "New FCM Token received: $token")
        val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
        val tagId = prefs.getString("ACTIVE_TAG_ID", null)
        if (!tagId.isNullOrBlank()) {
            registerTokenWithServer(this, token, tagId)
        }
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)
        Log.d(TAG, "FCM message received: data=${remoteMessage.data}, notif=${remoteMessage.notification?.title}")

        val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
        val activeTagId = prefs.getString("ACTIVE_TAG_ID", null)

        // Strict Check 1: If user is logged out (no active tag saved), DROP notification completely!
        if (activeTagId.isNullOrBlank()) {
            Log.d(TAG, "User is logged out (no active tag). Dropping alert completely.")
            return
        }

        val data = remoteMessage.data
        val tagId = data["tag_id"] ?: ""

        // Strict Check 2: If incoming alert is for a different vehicle, drop it!
        val cleanActive = activeTagId.replace("BUZZ-", "").trim().uppercase()
        val cleanNotif = tagId.replace("BUZZ-", "").trim().uppercase()
        if (cleanActive.isNotEmpty() && cleanNotif.isNotEmpty() && cleanActive != cleanNotif) {
            Log.d(TAG, "Notification tag ($tagId) does not match active logged-in tag ($activeTagId). Dropping alert.")
            return
        }

        val alertType = data["alert_type"] ?: remoteMessage.notification?.title ?: "blocking"
        val message = data["message"] ?: remoteMessage.notification?.body ?: "Someone is alerting your vehicle!"

        val isAdminOrStatus = alertType.equals("APPROVED", ignoreCase = true) ||
                              alertType.equals("BLOCKED", ignoreCase = true) ||
                              alertType.equals("SUSPENDED", ignoreCase = true) ||
                              alertType.equals("UNBLOCKED", ignoreCase = true) ||
                              alertType.equals("DELETED", ignoreCase = true) ||
                              alertType.equals("ADMIN_NOTICE", ignoreCase = true)

        if (isAdminOrStatus) {
            fireAdminOrStatusNotification(alertType, message, tagId)
            return
        }

        val currentKey = "$tagId:$alertType:$message"
        val now = System.currentTimeMillis()
        if (currentKey == lastAlertKey && (now - lastAlertTimeMs) < 3000) {
            Log.d(TAG, "Silently ignoring duplicate alert within 3s: $currentKey")
            return
        }
        lastAlertKey = currentKey
        lastAlertTimeMs = now

        fireEmergencyAlert(alertType, message, tagId)
    }

    private fun fireEmergencyAlert(alertType: String, message: String, tagId: String) {
        Log.d(TAG, "fireEmergencyAlert triggered for: $alertType - $message (tag: $tagId)")
        
        // 1. Ensure high priority alert channel exists
        createAlertChannelIfNeeded()

        // 2. Resolve active tag ID
        val finalTagId = if (tagId.isNotBlank()) tagId else {
            val prefs = getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
            prefs.getString("ACTIVE_TAG_ID", "BUZZ-653178") ?: "BUZZ-653178"
        }

        // 3. Wake up the screen briefly to get owner's attention
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

        // 4. Play the loud car horn sound using AlertSoundPlayer
        AlertSoundPlayer.playCarHorn(this)

        val notifId = (System.currentTimeMillis() % 100000).toInt() + 1000
        val isCall = alertType.equals("incoming_call", ignoreCase = true) || alertType.contains("call", ignoreCase = true)
        val notifTitle = if (isCall) "📞 Incoming Voice Call" else "🚨 ParkingBuzz: ${alertType.uppercase()} ALERT"
        val notifBigText = if (isCall) {
            "📞 A bystander near your vehicle is calling you live.\n\nTap to Answer or Decline."
        } else {
            "🚨 $message\n\nChoose an action below to respond instantly."
        }

        val appLogo = try {
            BitmapFactory.decodeResource(resources, R.mipmap.ic_launcher)
        } catch (_: Exception) { null }

        val soundUri = Uri.parse("android.resource://$packageName/${R.raw.chime}")

        // --- Action 1: "💬 Reply" (Inline Direct Reply + Suggestions) ---
        val replyIntent = Intent(this, NotificationActionReceiver::class.java).apply {
            action = NotificationActionReceiver.ACTION_REPLY
            putExtra(NotificationActionReceiver.EXTRA_TAG_ID, finalTagId)
            putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notifId)
        }
        val replyPendingIntent = PendingIntent.getBroadcast(
            this,
            notifId + 1,
            replyIntent,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE
            } else {
                PendingIntent.FLAG_UPDATE_CURRENT
            }
        )

        val remoteInput = RemoteInput.Builder(NotificationActionReceiver.KEY_TEXT_REPLY)
            .setLabel("Reply to bystander...")
            .setChoices(arrayOf(
                "Coming in 2 mins! 🏃",
                "On my way! 🚗",
                "Moved! 👍",
                "Reaching in 5 mins ⏳"
            ))
            .build()

        val replyAction = NotificationCompat.Action.Builder(
            R.drawable.ic_stat_parkbuzz,
            "💬 Reply",
            replyPendingIntent
        ).addRemoteInput(remoteInput).build()

        // --- Action 2: "🏃 2 Mins" (Single-Tap Instant Preset Reply) ---
        val instantReplyIntent = Intent(this, NotificationActionReceiver::class.java).apply {
            action = NotificationActionReceiver.ACTION_REPLY
            putExtra(NotificationActionReceiver.EXTRA_TAG_ID, finalTagId)
            putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notifId)
            putExtra(NotificationActionReceiver.EXTRA_PRESET_REPLY, "Coming in 2 mins! 🏃")
        }
        val instantReplyPendingIntent = PendingIntent.getBroadcast(
            this,
            notifId + 2,
            instantReplyIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val instantReplyAction = NotificationCompat.Action.Builder(
            R.drawable.ic_stat_parkbuzz,
            "🏃 2 Mins",
            instantReplyPendingIntent
        ).build()

        // --- Action 3: "💤 Snooze (1h)" (Single-Tap 1-Hour Snooze) ---
        val snoozeIntent = Intent(this, NotificationActionReceiver::class.java).apply {
            action = NotificationActionReceiver.ACTION_SNOOZE
            putExtra(NotificationActionReceiver.EXTRA_TAG_ID, finalTagId)
            putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notifId)
        }
        val snoozePendingIntent = PendingIntent.getBroadcast(
            this,
            notifId + 3,
            snoozeIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val snoozeAction = NotificationCompat.Action.Builder(
            R.drawable.ic_stat_parkbuzz,
            "💤 Snooze (1h)",
            snoozePendingIntent
        ).build()

        // --- Action Dismiss: Silence horn & dismiss without opening app ---
        val dismissIntent = Intent(this, NotificationActionReceiver::class.java).apply {
            action = NotificationActionReceiver.ACTION_DISMISS
            putExtra(NotificationActionReceiver.EXTRA_NOTIFICATION_ID, notifId)
        }
        val dismissPendingIntent = PendingIntent.getBroadcast(
            this,
            notifId + 4,
            dismissIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notifBuilder = NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_parkbuzz)
            .setColor(0xFF38BDF8.toInt())
            .setContentTitle(notifTitle)
            .setContentText(if (isCall) "Incoming Voice Call..." else message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(notifBigText))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setSound(soundUri)
            .setVibrate(longArrayOf(0, 500, 200, 500, 200, 1000))
            .setAutoCancel(true)

        if (appLogo != null) {
            notifBuilder.setLargeIcon(appLogo)
        }

        if (isCall) {
            // Only voice calls launch the full-screen call answer screen
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
            notifBuilder.setFullScreenIntent(fullScreenPendingIntent, true)
            notifBuilder.setContentIntent(fullScreenPendingIntent)
        } else {
            // For vehicle alerts:
            // Tapping the notification body silences and dismisses - NEVER forcefully opens the app!
            notifBuilder.setContentIntent(dismissPendingIntent)
            notifBuilder.setDeleteIntent(dismissPendingIntent)

            // Direct actions right on the notification
            notifBuilder.addAction(replyAction)
            notifBuilder.addAction(instantReplyAction)
            notifBuilder.addAction(snoozeAction)
        }

        val notif = notifBuilder.build()
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notifId, notif)
    }

    private fun fireAdminOrStatusNotification(alertType: String, message: String, tagId: String) {
        Log.d(TAG, "fireAdminOrStatusNotification: $alertType - $message (tag: $tagId)")
        createStatusChannelIfNeeded()

        val notifId = (System.currentTimeMillis() % 100000).toInt() + 2000
        val isApproved = alertType.equals("APPROVED", ignoreCase = true)
        val isBlocked = alertType.equals("BLOCKED", ignoreCase = true) || alertType.equals("SUSPENDED", ignoreCase = true)
        val isUnblocked = alertType.equals("UNBLOCKED", ignoreCase = true)
        val isDeleted = alertType.equals("DELETED", ignoreCase = true)

        // 1. Instantly update live in-app WebView if app is currently visible/open
        if (isApproved || isBlocked || isUnblocked) {
            MainActivity.reloadActiveWebView()
        } else if (isDeleted) {
            MainActivity.triggerLogout()
        }

        // 2. Resolve Notification Title & Content
        val notifTitle = when {
            isApproved -> "🎉 ParkingBuzz Sticker Activated"
            isBlocked -> "🛑 Account Suspended - ParkingBuzz"
            isUnblocked -> "✅ Account Reactivated - ParkingBuzz"
            isDeleted -> "⚠️ Account Removed - ParkingBuzz"
            else -> "📢 Administrator Notice - ParkingBuzz"
        }

        val appLogo = try {
            BitmapFactory.decodeResource(resources, R.mipmap.ic_launcher)
        } catch (_: Exception) { null }

        // When user taps the notification, open MainActivity!
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val contentPendingIntent = PendingIntent.getActivity(
            this, notifId, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val soundUri = Uri.parse("android.resource://$packageName/${R.raw.chime}")

        val notifBuilder = NotificationCompat.Builder(this, STATUS_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_parkbuzz)
            .setColor(if (isBlocked) 0xFFEF4444.toInt() else 0xFF38BDF8.toInt())
            .setContentTitle(notifTitle)
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setSound(soundUri)
            .setAutoCancel(true)
            .setContentIntent(contentPendingIntent)

        if (appLogo != null) {
            notifBuilder.setLargeIcon(appLogo)
        }

        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notifId, notifBuilder.build())
    }

    private fun createStatusChannelIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val soundUri = Uri.parse("android.resource://$packageName/${R.raw.chime}")
            val audioAttributes = AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .build()

            val statusChannel = NotificationChannel(
                STATUS_CHANNEL_ID,
                "ParkingBuzz Account Updates",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Account verification, approval, and administrative status updates"
                enableLights(true)
                enableVibration(true)
                setSound(soundUri, audioAttributes)
            }
            nm.createNotificationChannel(statusChannel)
        }
    }

    private fun createAlertChannelIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val soundUri = Uri.parse("android.resource://$packageName/${R.raw.chime}")
            val audioAttributes = AudioAttributes.Builder()
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .setUsage(AudioAttributes.USAGE_ALARM)
                .build()

            val alertChannel = NotificationChannel(
                ALERT_CHANNEL_ID,
                "ParkingBuzz Emergency Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Emergency heads-up alert when vehicle is blocked"
                enableLights(true)
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 500, 200, 500, 200, 1000)
                setSound(soundUri, audioAttributes)
                setBypassDnd(true)
            }
            nm.createNotificationChannel(alertChannel)
        }
    }
}
