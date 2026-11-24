import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    // AGP 9.0+ 内置 Kotlin 支持，不再需要 org.jetbrains.kotlin.android
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// 从 local.properties 读取 API 地址，真机调试只改该文件即可（不进版本库）
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val apiBaseUrl = localProps.getProperty("api.base.url") ?: "http://10.0.2.2:8000"

android {
    namespace = "com.kwg.resourcealart"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.kwg.resourcealart"
        minSdk = 24
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0-M1"

        // 默认模拟器 10.0.2.2；真机在 local.properties 写 api.base.url=http://<电脑局域网IP>:8000
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    // AGP 9 内置 Kotlin，jvmTarget 跟随 compileOptions

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material3.window.size)
    implementation(libs.androidx.compose.material.icons.core)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.androidx.navigation.compose)

    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit.ext)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    debugImplementation(libs.androidx.compose.ui.tooling)
}
