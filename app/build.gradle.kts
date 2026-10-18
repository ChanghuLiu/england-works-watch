import java.io.File
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val worksWatchUploadPropertiesPath = providers.gradleProperty("worksWatchUploadProperties").orElse("${System.getProperty("user.home")}/.config/regevidencehub/workswatch-upload.properties").get()
val worksWatchUploadPropertiesFile = file(worksWatchUploadPropertiesPath)
val worksWatchUploadProperties = Properties().apply { if (worksWatchUploadPropertiesFile.isFile) worksWatchUploadPropertiesFile.inputStream().use { load(it) } }
val worksWatchUploadValues = listOf("storeFile", "storePassword", "keyAlias", "keyPassword").map(worksWatchUploadProperties::getProperty)
val worksWatchUploadStoreFile = worksWatchUploadValues.firstOrNull()?.let { candidate ->
    val store = file(candidate)
    if (store.isAbsolute) store else File(worksWatchUploadPropertiesFile.parentFile, candidate)
}
val worksWatchUploadSigningReady = worksWatchUploadValues.all { !it.isNullOrBlank() } && worksWatchUploadPropertiesFile.isFile && worksWatchUploadStoreFile?.isFile == true

android {
    namespace = "com.regevidencehub.workswatch"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.regevidencehub.workswatch"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
    }
    buildFeatures { compose = true; buildConfig = true }
    signingConfigs {
        create("upload") {
            if (worksWatchUploadSigningReady) {
                storeFile = worksWatchUploadStoreFile
                storePassword = worksWatchUploadValues[1]
                keyAlias = worksWatchUploadValues[2]
                keyPassword = worksWatchUploadValues[3]
            }
        }
    }
    buildTypes {
        debug {
            isDebuggable = true
            buildConfigField("String", "API_BASE_URL", "\"http://127.0.0.1:8000\"")
            manifestPlaceholders["usesCleartextTraffic"] = "true"
        }
        release {
            if (worksWatchUploadSigningReady) signingConfig = signingConfigs.getByName("upload")
            isMinifyEnabled = false
            buildConfigField("String", "API_BASE_URL", "\"https://works.regevidencehub.com\"")
            manifestPlaceholders["usesCleartextTraffic"] = "false"
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.10.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.4")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.4")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("com.android.billingclient:billing-ktx:9.1.0")
    testImplementation("junit:junit:4.13.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
}
