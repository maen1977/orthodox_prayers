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


val generatedBibleAssets = layout.buildDirectory.dir("generated/bibleAssets")
val bibleCorpusOutput = generatedBibleAssets.map { it.dir("bible/corpus") }
val bibleCorpusCache = layout.buildDirectory.dir("bible-download-cache")

val generatedChurchServiceAssets = layout.buildDirectory.dir("generated/churchServiceAssets")
val churchServiceOutput = generatedChurchServiceAssets.map { it.dir("data/church") }
val churchServiceCache = layout.buildDirectory.dir("church-service-download-cache")
val prepareBibleCorpus by tasks.registering(Exec::class) {
    group = "orthodox prayers"
    description = "Downloads official eBible USFM archives and compiles offline Bible assets."
    inputs.file(rootProject.file("scripts/prepare_bible_corpus.py"))
    outputs.dir(bibleCorpusOutput)
    commandLine(
        "python",
        rootProject.file("scripts/prepare_bible_corpus.py").absolutePath,
        "--output-dir", bibleCorpusOutput.get().asFile.absolutePath,
        "--cache-dir", bibleCorpusCache.get().asFile.absolutePath
    )
}

val prepareChurchServiceCorpus by tasks.registering(Exec::class) {
    group = "orthodox prayers"
    description = "Downloads authorized native Orthodox church-service texts and compiles offline assets without translation."
    inputs.file(rootProject.file("scripts/prepare_church_service_corpus.py"))
    inputs.file(rootProject.file("canonical/church_service_full_sources.json"))
    outputs.dir(churchServiceOutput)
    commandLine(
        "python",
        rootProject.file("scripts/prepare_church_service_corpus.py").absolutePath,
        "--manifest", rootProject.file("canonical/church_service_full_sources.json").absolutePath,
        "--output-dir", churchServiceOutput.get().asFile.absolutePath,
        "--cache-dir", churchServiceCache.get().asFile.absolutePath
    )
}

android {
    namespace = "com.orthodoxprayers.privateapp"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.orthodoxprayers.privateapp"
        minSdk = 26
        targetSdk = 36
        versionCode = 50604
        versionName = "5.6.4"
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
    sourceSets.getByName("main").assets.srcDir(generatedChurchServiceAssets.get().asFile)

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


tasks.named("preBuild").configure { dependsOn(prepareBibleCorpus, prepareChurchServiceCorpus) }
