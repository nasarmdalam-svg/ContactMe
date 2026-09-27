package com.example.carsafetag

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

class BootReceiver : BroadcastReceiver() {

    companion object {
        const val TAG = "ParkBuzzBoot"
    }

    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action
        Log.d(TAG, "BootReceiver triggered with action: $action")

        val tagId = intent?.getStringExtra("TAG_ID") ?: "CAR-D3AEED"

        try {
            val serviceIntent = Intent(context, ParkBuzzAlertService::class.java).apply {
                putExtra("TAG_ID", tagId)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent)
            } else {
                context.startService(serviceIntent)
            }
            Log.d(TAG, "ParkBuzzAlertService successfully started from BootReceiver")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start service from BootReceiver: ${e.message}", e)
        }
    }
}
