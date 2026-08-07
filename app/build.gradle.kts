import java.io.InputStream
import java.net.URI
import java.net.URLConnection

plugins {
    id("com.android.application")
}

val releaseKeystoreFile = System.getenv("ANDROID_KEYSTORE_FILE")
val releaseKeystorePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
val releaseKeyAlias = System.getenv("ANDROID_KEY_ALIAS")
val releaseKeyPassword = System.getenv("ANDROID_KEY_PASSWORD")
val releaseSigningAvailable = listOf(
    releaseKeystoreFile,
    releaseKeystorePassword,
    releaseKeyAlias,
    releaseKeyPassword
).all { !it.isNullOrBlank() }


val bibleCorpusFiles = linkedMapOf(
    "vref.txt" to Triple("https://raw.githubusercontent.com/BibleNLP/ebible/main/metadata/vref.txt", 40000, 40000),
    "arb-arb-vd.txt" to Triple("https://raw.githubusercontent.com/BibleNLP/ebible/main/corpus/arb-arb-vd.txt", 40000, 31000),
    "eng-eng-webbe.txt" to Triple("https://raw.githubusercontent.com/BibleNLP/ebible/main/corpus/eng-eng-webbe.txt", 40000, 37000),
    "grc-grcbrent.txt" to Triple("https://raw.githubusercontent.com/BibleNLP/ebible/main/corpus/grc-grcbrent.txt", 40000, 26000),
    "grc-grcbyz.txt" to Triple("https://raw.githubusercontent.com/BibleNLP/ebible/main/corpus/grc-grcbyz.txt", 40000, 7900)
)
val generatedBibleAssets = layout.buildDirectory.dir("generated/bibleAssets")
val prepareBibleCorpus by tasks.registering {
    group = "orthodox prayers"
    description = "Downloads redistributable public-domain Bible corpus files and embeds them in the APK."
    val outputRoot = generatedBibleAssets.map { it.dir("bible/corpus") }
    outputs.dir(outputRoot)
    doLast {
        val outputDir = outputRoot.get().asFile
        outputDir.mkdirs()
        bibleCorpusFiles.forEach { (name, spec) ->
            val target = outputDir.resolve(name)
            if (!target.isFile || target.length() < 1024L) {
                val connection: URLConnection = URI(spec.first).toURL().openConnection().apply {
                    connectTimeout = 30000
                    readTimeout = 120000
                    setRequestProperty("User-Agent", "OrthodoxPrayers-BibleBuilder/5.4")
                }
                connection.getInputStream().use { input: InputStream ->
                    target.outputStream().use { output -> input.copyTo(output) }
                }
            }
            val counts = target.bufferedReader(Charsets.UTF_8).useLines { lines ->
                var total = 0
                var nonBlank = 0
                lines.forEach { line ->
                    total++
                    if (line.isNotBlank() && line.trim() != "<range>") nonBlank++
                }
                Pair(total, nonBlank)
            }
            require(counts.first >= spec.second) { "Bible corpus file $name is truncated: ${counts.first} lines" }
            require(counts.second >= spec.third) { "Bible corpus file $name has too little Scripture text: ${counts.second} nonblank lines" }
        }
    }
}

android {
    namespace = "com.orthodoxprayers.privateapp"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.orthodoxprayers.privateapp"
        minSdk = 26
        targetSdk = 36
        versionCode = 50400
        versionName = "5.4.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        if (releaseSigningAvailable) {
            create("release") {
                storeFile = file(requireNotNull(releaseKeystoreFile))
                storePassword = releaseKeystorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
                enableV4Signing = true
            }
        }
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.findByName("release")
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    sourceSets.getByName("main").assets.srcDir(generatedBibleAssets.get().asFile)

    lint {
        abortOnError = true
        checkReleaseBuilds = true
        warningsAsErrors = false
    }
}

dependencies {
    implementation("androidx.activity:activity:1.10.1")
    implementation("androidx.recyclerview:recyclerview:1.4.0")
    implementation("androidx.work:work-runtime:2.11.2")
    implementation("androidx.profileinstaller:profileinstaller:1.4.1")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test:core:1.6.1")
    androidTestImplementation("androidx.test:runner:1.6.2")
}


tasks.named("preBuild").configure { dependsOn(prepareBibleCorpus) }
