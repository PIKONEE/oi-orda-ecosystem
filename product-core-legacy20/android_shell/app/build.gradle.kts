plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    // namespace и applicationId заменяются build-скриптом из product.json
    namespace = "kz.digitouch.shell"
    compileSdk = 34

    defaultConfig {
        applicationId = "kz.digitouch.shell"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
    }

    signingConfigs {
        create("release") {
            storeFile = file("oilab-release.jks")
            storePassword = "oilab2026"
            keyAlias = "oilab"
            keyPassword = "oilab2026"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
        debug {
            isDebuggable = true
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        buildConfig = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.webkit:webkit:1.9.0")
    implementation("com.google.android.material:material:1.11.0")
    // LEGACY-20: подпись ключа симметричная (HMAC-SHA256 из стандартной библиотеки).
    // Ed25519 (BouncyCastle), CameraX и ML Kit не нужны — QR-сканера здесь нет,
    // без них APK меньше примерно на 10 МБ.
}
