package com.example.carsafetag

import android.app.Application
import com.google.firebase.FirebaseApp

class ParkBuzzApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // Initialise Firebase as early as possible
        FirebaseApp.initializeApp(this)
    }
}
