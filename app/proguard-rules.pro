# Preserve WorkManager workers that AndroidX creates through reflection.
-keep class * extends androidx.work.ListenableWorker {
    public <init>(android.content.Context, androidx.work.WorkerParameters);
}

# Preserve useful source information in crash reports while still obfuscating code.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
