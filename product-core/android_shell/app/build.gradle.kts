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
    }

    signingConfigs {
        create("release") {
            // Настройте при необходимости; по умолчанию — debug signing для sideloading
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
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
    // Ed25519-проверка лицензий v4 (используем низкоуровневый API, без JCA-провайдера)
    implementation("org.bouncycastle:bcprov-jdk18on:1.77")
}
