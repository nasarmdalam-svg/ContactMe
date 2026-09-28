package com.example.carsafetag

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Toast
import androidx.core.app.NotificationCompat
import androidx.core.app.RemoteInput
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

class NotificationActionReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "NotifActionReceiver"
        const val ACTION_SNOOZE = "com.parkingbuzz.alert.ACTION_SNOOZE"
        const val ACTION_REPLY = "com.parkingbuzz.alert.ACTION_REPLY"
        const val ACTION_DISMISS = "com.parkingbuzz.alert.ACTION_DISMISS"

        const val EXTRA_TAG_ID = "EXTRA_TAG_ID"
        const val EXTRA_NOTIFICATION_ID = "EXTRA_NOTIFICATION_ID"
        const val EXTRA_PRESET_REPLY = "EXTRA_PRESET_REPLY"
        const val KEY_TEXT_REPLY = "key_text_reply"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        val notifId = intent.getIntExtra(EXTRA_NOTIFICATION_ID, 0)
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        // Silence the car horn immediately on any user action
        AlertSoundPlayer.stop()

        var tagId = intent.getStringExtra(EXTRA_TAG_ID)
        if (tagId.isNullOrBlank()) {
            val prefs = context.getSharedPreferences("ParkBuzzPrefs", Context.MODE_PRIVATE)
            tagId = prefs.getString("ACTIVE_TAG_ID", "BUZZ-653178") ?: "BUZZ-653178"
        }

        when (action) {
            ACTION_SNOOZE -> {
                // Cancel notification immediately
                if (notifId != 0) {
                    nm.cancel(notifId)
                }

                Handler(Looper.getMainLooper()).post {
                    Toast.makeText(context, "💤 ParkingBuzz Protection Snoozed (1 hr)", Toast.LENGTH_SHORT).show()
                }

                // Send snooze request to server
                Thread {
                    try {
                        val client = OkHttpClient()
                        val payload = JSONObject().apply {
                            put("duration_minutes", 60)
                        }
                        val body = payload.toString().toRequestBody("application/json".toMediaType())
                        val request = Request.Builder()
                            .url("https://contactme-go9v.onrender.com/api/owner/snooze/$tagId")
                            .post(body)
                            .build()
                        val response = client.newCall(request).execute()
                        Log.d(TAG, "Snooze delivered for $tagId: code ${response.code}")
                    } catch (e: Exception) {
                        Log.e(TAG, "Error snoozing on server: ${e.message}")
                    }
                }.start()
            }

            ACTION_REPLY -> {
                // Extract text from RemoteInput (inline reply) or preset action extra
                val remoteInputResults = RemoteInput.getResultsFromIntent(intent)
                val replyText = remoteInputResults?.getCharSequence(KEY_TEXT_REPLY)?.toString()
                    ?: intent.getStringExtra(EXTRA_PRESET_REPLY)
                    ?: "Coming in 2 mins! 🏃"

                // Cancel the loud alert notification immediately and stop all sounds
                nm.cancel(notifId)
                AlertSoundPlayer.stop()

                Handler(Looper.getMainLooper()).post {
                    Toast.makeText(context, "✓ Sent: \"$replyText\"", Toast.LENGTH_SHORT).show()
                }

                // Send reply to server so bystander sees it live instantly
                Thread {
                    try {
                        val client = OkHttpClient()
                        val payload = JSONObject().apply {
                            put("message", replyText)
                        }
                        val body = payload.toString().toRequestBody("application/json".toMediaType())
                        val request = Request.Builder()
                            .url("https://contactme-go9v.onrender.com/api/owner/respond/$tagId")
                            .post(body)
                            .build()
                        val response = client.newCall(request).execute()
                        Log.d(TAG, "Owner reply delivered for $tagId: code ${response.code}")
                    } catch (e: Exception) {
                        Log.e(TAG, "Error delivering reply to server: ${e.message}")
                    }
                }.start()
            }

            ACTION_DISMISS -> {
                if (notifId != 0) {
                    nm.cancel(notifId)
                }
            }
        }
    }
}
