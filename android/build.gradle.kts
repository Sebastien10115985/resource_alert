// 顶层构建文件：仅声明插件版本，不在此处 apply
plugins {
    // AGP 9.0+ 内置 Kotlin 支持，不再声明 org.jetbrains.kotlin.android
    id("com.android.application") version "9.4.1" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.4.10" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.4.10" apply false
}
