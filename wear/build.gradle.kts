plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    kotlin("plugin.serialization") version "2.0.21"
}

android {
    namespace = "com.example.besu.wear"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.besu"
        minSdk = 30
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        // --- C++ BUILD CONFIG ---
        externalNativeBuild {
            cmake {
                // Pass flags to the C++ compiler:
                // -O3: Maximum optimization level
                // -ffast-math: faster floating point math (safe for audio synthesis)
                // -DANDROID_ARM_NEON=TRUE: Define the NEON flag for our code
                cppFlags("-O3 -ffast-math")
                arguments("-DANDROID_ARM_NEON=TRUE")
            }
        }

        ndk {
            // Filter to only build for the architecture used by watches (ARM64)
            // This reduces APK size and build time.
            // Almost all modern Wear OS devices are arm64-v8a.
            abiFilters.addAll(listOf("armeabi-v7a", "arm64-v8a"))
        }
    }

    // --- LINK CMAKE LISTS ---
    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
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
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    useLibrary("wear-sdk")
    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation(libs.play.services.wearable)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.compose.material)
    implementation(libs.androidx.compose.foundation)
    implementation(libs.androidx.wear.tooling.preview)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.core.splashscreen)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
    implementation("com.google.android.gms:play-services-wearable:18.1.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("androidx.wear.compose:compose-material:1.3.0")
    implementation("androidx.wear.compose:compose-foundation:1.3.0")
    implementation("androidx.wear.compose:compose-navigation:1.3.0")
    implementation("androidx.wear:wear:1.3.0")
    implementation("androidx.fragment:fragment-ktx:1.6.2")
}