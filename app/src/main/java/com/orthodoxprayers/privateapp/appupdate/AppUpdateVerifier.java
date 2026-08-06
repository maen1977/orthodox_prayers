package com.orthodoxprayers.privateapp.appupdate;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Build;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

/** Verifies checksum, package identity, version, and signing certificate before installation. */
public final class AppUpdateVerifier {
    private AppUpdateVerifier() { }

    public static void verify(Context context, File apk, AppUpdateRelease release) throws Exception {
        if (apk == null || !apk.isFile() || apk.length() < 1L) throw new SecurityException("apk_missing");
        if (release.sizeBytes > 0L && apk.length() != release.sizeBytes) throw new SecurityException("size_mismatch");
        String checksum = sha256(apk);
        if (!checksum.equals(release.sha256)) throw new SecurityException("checksum_mismatch");

        PackageManager packageManager = context.getPackageManager();
        PackageInfo installed = installedPackageInfo(packageManager, context.getPackageName());
        PackageInfo archive = archivePackageInfo(packageManager, apk.getAbsolutePath());
        if (archive == null) throw new SecurityException("invalid_apk");
        if (!context.getPackageName().equals(archive.packageName)) throw new SecurityException("package_mismatch");
        long archiveCode = longVersionCode(archive);
        if (archiveCode != release.versionCode || archiveCode <= longVersionCode(installed)) {
            throw new SecurityException("version_mismatch");
        }

        Set<String> installedCertificates = certificateDigests(installed);
        Set<String> archiveCertificates = certificateDigests(archive);
        if (installedCertificates.isEmpty() || archiveCertificates.isEmpty()) {
            throw new SecurityException("certificate_missing");
        }
        boolean match = false;
        for (String certificate : archiveCertificates) {
            if (installedCertificates.contains(certificate)) {
                match = true;
                break;
            }
        }
        if (!match) throw new SecurityException("certificate_mismatch");
    }

    public static long installedVersionCode(Context context) {
        try {
            return longVersionCode(installedPackageInfo(context.getPackageManager(), context.getPackageName()));
        } catch (Exception ignored) {
            return 0L;
        }
    }

    public static String sha256(File file) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[64 * 1024];
            try (BufferedInputStream input = new BufferedInputStream(new FileInputStream(file))) {
                int read;
                while ((read = input.read(buffer)) != -1) digest.update(buffer, 0, read);
            }
            StringBuilder value = new StringBuilder(64);
            for (byte item : digest.digest()) value.append(String.format(Locale.ROOT, "%02x", item & 0xff));
            return value.toString();
        } catch (java.security.NoSuchAlgorithmException impossible) {
            throw new IOException("SHA-256 is unavailable", impossible);
        }
    }

    @SuppressWarnings("deprecation")
    private static PackageInfo installedPackageInfo(PackageManager manager, String packageName) throws PackageManager.NameNotFoundException {
        if (Build.VERSION.SDK_INT >= 33) {
            return manager.getPackageInfo(packageName, PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES));
        }
        int flags = Build.VERSION.SDK_INT >= 28 ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        return manager.getPackageInfo(packageName, flags);
    }

    @SuppressWarnings("deprecation")
    private static PackageInfo archivePackageInfo(PackageManager manager, String path) {
        if (Build.VERSION.SDK_INT >= 33) {
            return manager.getPackageArchiveInfo(path, PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES));
        }
        int flags = Build.VERSION.SDK_INT >= 28 ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        return manager.getPackageArchiveInfo(path, flags);
    }

    @SuppressWarnings("deprecation")
    private static Set<String> certificateDigests(PackageInfo packageInfo) throws Exception {
        HashSet<String> result = new HashSet<>();
        Signature[] signatures;
        if (Build.VERSION.SDK_INT >= 28 && packageInfo.signingInfo != null) {
            signatures = packageInfo.signingInfo.hasMultipleSigners()
                    ? packageInfo.signingInfo.getApkContentsSigners()
                    : packageInfo.signingInfo.getSigningCertificateHistory();
        } else {
            signatures = packageInfo.signatures;
        }
        if (signatures == null) return result;
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        for (Signature signature : signatures) {
            if (signature == null) continue;
            byte[] bytes = digest.digest(signature.toByteArray());
            StringBuilder value = new StringBuilder(64);
            for (byte item : bytes) value.append(String.format(Locale.ROOT, "%02x", item & 0xff));
            result.add(value.toString());
            digest.reset();
        }
        return result;
    }

    @SuppressWarnings("deprecation")
    private static long longVersionCode(PackageInfo packageInfo) {
        return Build.VERSION.SDK_INT >= 28 ? packageInfo.getLongVersionCode() : packageInfo.versionCode;
    }
}
