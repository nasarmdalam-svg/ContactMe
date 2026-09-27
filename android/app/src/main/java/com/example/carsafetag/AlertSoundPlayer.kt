package com.example.carsafetag

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.util.Log

object AlertSoundPlayer {
    private const val TAG = "AlertSoundPlayer"
    private var activePlayer: MediaPlayer? = null

    @Synchronized
    fun playCarHorn(context: Context) {
        try {
            stop()
            val player = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .build()
                )
                try {
                    val afd = context.resources.openRawResourceFd(R.raw.car_honk)
                    if (afd != null) {
                        setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
                        afd.close()
                    } else {
                        val soundUri = Uri.parse("android.resource://${context.packageName}/${R.raw.car_honk}")
                        setDataSource(context.applicationContext, soundUri)
                    }
                } catch (e: Exception) {
                    val soundUri = Uri.parse("android.resource://${context.packageName}/${R.raw.car_honk}")
                    setDataSource(context.applicationContext, soundUri)
                }
                prepare()
                // Ensure max volume for the horn
                setVolume(1.0f, 1.0f)
                start()
            }
            activePlayer = player
            player.setOnCompletionListener {
                synchronized(AlertSoundPlayer) {
                    try {
                        it.release()
                    } catch (_: Exception) {}
                    if (activePlayer == it) {
                        activePlayer = null
                    }
                }
            }
            Log.d(TAG, "Loud automotive horn sound started successfully!")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to play car horn: ${e.message}", e)
        }
    }

    @Synchronized
    fun stop() {
        try {
            activePlayer?.let {
                if (it.isPlaying) {
                    it.stop()
                }
                it.release()
            }
        } catch (_: Exception) {}
        activePlayer = null
    }
}
