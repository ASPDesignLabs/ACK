plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    kotlin("plugin.serialization") version "2.0.21"
}

android {
    namespace = "com.example.besu"
    compileSdk = 36

    packaging {
        resources {
            pickFirsts += "assets/symbols/**"
            pickFirsts += "assets/patterns/**"
        }
    }


    defaultConfig {
        applicationId = "com.example.besu"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
        ndk {
            abiFilters.addAll(listOf("armeabi-v7a", "arm64-v8a", "x86_64"))
        }



        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    packaging {
        jniLibs {
            pickFirsts.add("lib/x86_64/libvtm-jni.so")
            pickFirsts.add("lib/armeabi-v7a/libvtm-jni.so")
            pickFirsts.add("lib/arm64-v8a/libvtm-jni.so")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }

}

dependencies {

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.constraintlayout)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    implementation("com.google.android.gms:play-services-wearable:18.1.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("androidx.compose.material:material:1.6.0")
    implementation("androidx.activity:activity-compose:1.8.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("androidx.compose.material3:material3:1.3.1")
    implementation("com.google.android.gms:play-services-location:21.0.1")
    implementation(libs.androidx.constraintlayout)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.compose.foundation)
    val camerax_version = "1.4.1"
    implementation("androidx.camera:camera-core:$camerax_version")
    implementation("androidx.camera:camera-camera2:$camerax_version")
    implementation("androidx.camera:camera-lifecycle:$camerax_version")
    implementation("androidx.camera:camera-view:$camerax_version")
// Mapsforge: 100% Java Offline Vector Maps (Zero C++ / Zero ELF errors)
    implementation("org.mapsforge:mapsforge-map-android:0.20.0")
    implementation("org.mapsforge:mapsforge-themes:0.20.0")
    implementation("org.mapsforge:vtm-android:0.25.0")
    implementation("org.mapsforge:vtm-themes:0.25.0")
// For hardware acceleration

}