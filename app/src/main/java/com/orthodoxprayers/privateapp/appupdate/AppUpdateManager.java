package com.orthodoxprayers.privateapp.appupdate;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.ProgressDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.widget.Toast;

import androidx.core.content.FileProvider;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.MainActivity;
import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.ui.LocalizedResources;
import com.orthodoxprayers.privateapp.work.AppUpdateWorker;

import java.io.File;
import java.text.DecimalFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Coordinates GitHub release checks, secure APK downloads, notifications, and user-approved installation. */
public final class AppUpdateManager {
    public enum BackgroundResult { SUCCESS, RETRY }

    public static final String EXTRA_APP_UPDATE_ACTION =
            "com.orthodoxprayers.privateapp.extra.APP_UPDATE_ACTION";
    public static final String ACTION_SHOW = "show";
    public static final String ACTION_INSTALL = "install";

    private static final String PERIODIC_WORK = "orthodox-prayers-app-update-check-v1";
    private static final String NOTIFICATION_CHANNEL = "app_updates";
    private static final int NOTIFICATION_ID = 5201;
    private static final long APP_OPEN_CHECK_INTERVAL_MS = TimeUnit.HOURS.toMillis(6);
    private static final long PERIODIC_INTERVAL_HOURS = 12L;
    private static final long LATER_SNOOZE_MS = TimeUnit.HOURS.toMillis(24);

    private final Context context;
    private final AppPreferences preferences;
    private final AppUpdateClient client = new AppUpdateClient();
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean checkRunning = new AtomicBoolean(false);
    private final AtomicBoolean releaseDialogShowing = new AtomicBoolean(false);
    private final Object callbackLock = new Object();
    private final List<CheckCallback> pendingCheckCallbacks = new ArrayList<>();

    public AppUpdateManager(Context context, AppPreferences preferences) {
        this.context = context.getApplicationContext();
        this.preferences = preferences;
        createNotificationChannel();
    }

    public void schedulePeriodicChecks() {
        WorkManager manager = WorkManager.getInstance(context);
        if (!preferences.appUpdateChecksEnabled()) {
            manager.cancelUniqueWork(PERIODIC_WORK);
            return;
        }
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                AppUpdateWorker.class,
                PERIODIC_INTERVAL_HOURS,
                TimeUnit.HOURS,
                2L,
                TimeUnit.HOURS
        ).setConstraints(constraints).build();
        manager.enqueueUniquePeriodicWork(
                PERIODIC_WORK,
                ExistingPeriodicWorkPolicy.UPDATE,
                request
        );
    }

    public void checkOnAppOpen(Activity activity) {
        if (activity == null || activity.isFinishing() || !preferences.appUpdateChecksEnabled()) return;
        long now = System.currentTimeMillis();
        if (now - preferences.lastAppUpdateCheck() < APP_OPEN_CHECK_INTERVAL_MS) {
            AppUpdateRelease saved = savedRelease();
            if (saved != null && shouldOffer(saved)) showReleaseDialog(activity, saved);
            return;
        }
        checkAsync((release, error) -> {
            if (activity.isFinishing() || activity.isDestroyed()) return;
            if (error == null && release != null && shouldOffer(release)) showReleaseDialog(activity, release);
        });
    }

    public void checkNowInteractive(Activity activity, Runnable completion) {
        if (activity == null || activity.isFinishing()) return;
        Toast.makeText(activity, text(R.string.app_update_checking), Toast.LENGTH_SHORT).show();
        checkAsync((release, error) -> {
            if (completion != null) completion.run();
            if (activity.isFinishing() || activity.isDestroyed()) return;
            if (error != null) {
                Toast.makeText(activity, text(R.string.app_update_check_failed), Toast.LENGTH_LONG).show();
                return;
            }
            if (release == null || !release.isNewerThan(installedVersionCode())) {
                Toast.makeText(activity, text(R.string.app_update_up_to_date), Toast.LENGTH_LONG).show();
                return;
            }
            showReleaseDialog(activity, release);
        });
    }

    public BackgroundResult performBackgroundCheck() {
        if (!preferences.appUpdateChecksEnabled()) return BackgroundResult.SUCCESS;
        try {
            AppUpdateRelease release = client.fetchLatestRelease();
            saveCheckSuccess(release);
            if (!release.isNewerThan(installedVersionCode())) {
                clearDownloadedUpdate();
                return BackgroundResult.SUCCESS;
            }
            if (!shouldOffer(release)) return BackgroundResult.SUCCESS;

            boolean ready = false;
            if (preferences.autoDownloadAppUpdates() && !isActiveNetworkMetered()) {
                try {
                    File apk = downloadAndVerifyBlocking(release, null);
                    preferences.setDownloadedAppUpdatePath(apk.getAbsolutePath());
                    ready = true;
                } catch (Exception ignored) {
                    clearDownloadedUpdate();
                }
            }
            notifyUpdate(release, ready);
            return BackgroundResult.SUCCESS;
        } catch (Exception error) {
            preferences.recordAppUpdateCheck(false, "network_error", System.currentTimeMillis());
            return BackgroundResult.RETRY;
        }
    }

    public void handleLaunchIntent(Activity activity, Intent intent) {
        if (activity == null || intent == null) return;
        String action = intent.getStringExtra(EXTRA_APP_UPDATE_ACTION);
        if (action == null || action.trim().isEmpty()) return;
        intent.removeExtra(EXTRA_APP_UPDATE_ACTION);
        AppUpdateRelease release = savedRelease();
        if (release == null || !release.isNewerThan(installedVersionCode())) {
            checkNowInteractive(activity, null);
            return;
        }
        if (ACTION_INSTALL.equals(action)) {
            installCachedOrDownload(activity, release);
        } else {
            showReleaseDialog(activity, release);
        }
    }

    public boolean resumePendingInstall(Activity activity) {
        if (activity == null || !preferences.pendingAppUpdateInstall()) return false;
        if (!context.getPackageManager().canRequestPackageInstalls()) return true;
        AppUpdateRelease release = savedRelease();
        File apk = cachedApk();
        if (release == null || apk == null) {
            preferences.setPendingAppUpdateInstall(false);
            return false;
        }
        executor.execute(() -> {
            try {
                AppUpdateVerifier.verify(context, apk, release);
                activity.runOnUiThread(() -> launchInstaller(activity, apk));
            } catch (Exception error) {
                clearDownloadedUpdate();
                activity.runOnUiThread(() -> Toast.makeText(
                        activity,
                        text(R.string.app_update_verification_failed),
                        Toast.LENGTH_LONG
                ).show());
            }
        });
        return true;
    }

    public String availableVersionName() {
        AppUpdateRelease release = savedRelease();
        return release != null && release.isNewerThan(installedVersionCode()) ? release.versionName : "";
    }

    public long installedVersionCode() {
        return AppUpdateVerifier.installedVersionCode(context);
    }

    private void checkAsync(CheckCallback callback) {
        synchronized (callbackLock) {
            pendingCheckCallbacks.add(callback);
            if (!checkRunning.compareAndSet(false, true)) return;
        }
        executor.execute(() -> {
            AppUpdateRelease release = null;
            Exception error = null;
            try {
                release = client.fetchLatestRelease();
                saveCheckSuccess(release);
            } catch (Exception caught) {
                error = caught;
                preferences.recordAppUpdateCheck(false, "network_error", System.currentTimeMillis());
            }
            AppUpdateRelease finalRelease = release;
            Exception finalError = error;
            List<CheckCallback> callbacks;
            synchronized (callbackLock) {
                callbacks = new ArrayList<>(pendingCheckCallbacks);
                pendingCheckCallbacks.clear();
                checkRunning.set(false);
            }
            new android.os.Handler(android.os.Looper.getMainLooper()).post(() -> {
                for (CheckCallback item : callbacks) item.onComplete(finalRelease, finalError);
            });
        });
    }

    private void saveCheckSuccess(AppUpdateRelease release) {
        preferences.recordAppUpdateCheck(true, "checked", System.currentTimeMillis());
        preferences.setAvailableAppUpdateJson(release.toJson().toString());
        if (preferences.deferredAppUpdateVersionCode() != 0L
                && preferences.deferredAppUpdateVersionCode() != release.versionCode) {
            preferences.clearDeferredAppUpdate();
        }
        if (!release.isNewerThan(installedVersionCode())) {
            preferences.setSkippedAppUpdateVersionCode(0L);
        }
    }

    private boolean shouldOffer(AppUpdateRelease release) {
        if (release == null || !release.isNewerThan(installedVersionCode())) return false;
        if (release.isMandatoryFor(installedVersionCode())) return true;
        if (preferences.skippedAppUpdateVersionCode() == release.versionCode) return false;
        return preferences.deferredAppUpdateVersionCode() != release.versionCode
                || System.currentTimeMillis() >= preferences.deferredAppUpdateUntil();
    }

    private void showReleaseDialog(Activity activity, AppUpdateRelease release) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        if (!releaseDialogShowing.compareAndSet(false, true)) return;
        boolean mandatory = release.isMandatoryFor(installedVersionCode());
        String notes = release.releaseNotes;
        if (notes.length() > 1_600) notes = notes.substring(0, 1_600) + "…";
        StringBuilder message = new StringBuilder(format(R.string.app_update_available_message, release.versionName));
        if (release.sizeBytes > 0L) {
            message.append("\n").append(format(R.string.app_update_size, humanSize(release.sizeBytes)));
        }
        if (!notes.isEmpty()) message.append("\n\n").append(notes);

        AlertDialog.Builder builder = new AlertDialog.Builder(activity)
                .setTitle(text(R.string.app_update_available_title))
                .setMessage(message.toString())
                .setPositiveButton(text(R.string.app_update_now), (dialog, which) -> installCachedOrDownload(activity, release));
        if (!mandatory) {
            builder.setNegativeButton(text(R.string.app_update_later), (dialog, which) ->
                            preferences.deferAppUpdate(release.versionCode, System.currentTimeMillis() + LATER_SNOOZE_MS))
                    .setNeutralButton(text(R.string.app_update_skip_version), (dialog, which) -> {
                        preferences.setSkippedAppUpdateVersionCode(release.versionCode);
                        cancelUpdateNotification();
                    });
        }
        AlertDialog dialog = builder.create();
        dialog.setCancelable(!mandatory);
        dialog.setCanceledOnTouchOutside(false);
        dialog.setOnDismissListener(ignored -> releaseDialogShowing.set(false));
        try {
            dialog.show();
        } catch (RuntimeException error) {
            releaseDialogShowing.set(false);
            throw error;
        }
    }

    private void installCachedOrDownload(Activity activity, AppUpdateRelease release) {
        File cached = cachedApk();
        if (cached != null) {
            executor.execute(() -> {
                try {
                    AppUpdateVerifier.verify(context, cached, release);
                    activity.runOnUiThread(() -> requestInstallPermissionOrLaunch(activity, cached));
                } catch (Exception ignored) {
                    clearDownloadedUpdate();
                    activity.runOnUiThread(() -> downloadAndInstall(activity, release));
                }
            });
            return;
        }
        downloadAndInstall(activity, release);
    }

    @SuppressWarnings("deprecation")
    private void downloadAndInstall(Activity activity, AppUpdateRelease release) {
        ProgressDialog progress = new ProgressDialog(activity);
        progress.setTitle(text(R.string.app_update_downloading));
        progress.setMessage(text(R.string.app_update_download_wait));
        progress.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);
        progress.setIndeterminate(false);
        progress.setMax(100);
        progress.setCancelable(false);
        progress.show();

        executor.execute(() -> {
            try {
                File apk = downloadAndVerifyBlocking(release, (downloaded, total) -> {
                    if (total <= 0L) return;
                    int percent = (int) Math.max(0L, Math.min(100L, downloaded * 100L / total));
                    activity.runOnUiThread(() -> progress.setProgress(percent));
                });
                preferences.setDownloadedAppUpdatePath(apk.getAbsolutePath());
                activity.runOnUiThread(() -> {
                    progress.dismiss();
                    requestInstallPermissionOrLaunch(activity, apk);
                });
            } catch (Exception error) {
                clearDownloadedUpdate();
                activity.runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(activity, text(R.string.app_update_download_failed), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private File downloadAndVerifyBlocking(AppUpdateRelease release, AppUpdateClient.ProgressCallback callback) throws Exception {
        File directory = new File(context.getCacheDir(), "app-updates");
        File destination = new File(directory, "Church-Prayers-" + release.versionName + ".apk");
        client.downloadApk(release, destination, callback);
        AppUpdateVerifier.verify(context, destination, release);
        return destination;
    }

    private void requestInstallPermissionOrLaunch(Activity activity, File apk) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && !context.getPackageManager().canRequestPackageInstalls()) {
            preferences.setDownloadedAppUpdatePath(apk.getAbsolutePath());
            preferences.setPendingAppUpdateInstall(true);
            new AlertDialog.Builder(activity)
                    .setTitle(text(R.string.app_update_permission_title))
                    .setMessage(text(R.string.app_update_permission_message))
                    .setPositiveButton(text(R.string.app_update_open_settings), (dialog, which) -> {
                        Intent intent = new Intent(
                                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                Uri.parse("package:" + context.getPackageName())
                        );
                        activity.startActivity(intent);
                    })
                    .setNegativeButton(text(R.string.app_update_later), null)
                    .show();
            return;
        }
        launchInstaller(activity, apk);
    }

    private void launchInstaller(Activity activity, File apk) {
        try {
            preferences.setPendingAppUpdateInstall(false);
            Uri uri = FileProvider.getUriForFile(
                    context,
                    context.getPackageName() + ".fileprovider",
                    apk
            );
            Intent install = new Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            activity.startActivity(install);
            cancelUpdateNotification();
        } catch (Exception error) {
            Toast.makeText(activity, text(R.string.app_update_install_open_failed), Toast.LENGTH_LONG).show();
        }
    }

    private void notifyUpdate(AppUpdateRelease release, boolean readyToInstall) {
        if (Build.VERSION.SDK_INT >= 33
                && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        Intent intent = new Intent(context, MainActivity.class)
                .putExtra(MainActivity.EXTRA_SCREEN, "settings_section")
                .putExtra(MainActivity.EXTRA_ARGUMENT, "update_data")
                .putExtra(EXTRA_APP_UPDATE_ACTION, readyToInstall ? ACTION_INSTALL : ACTION_SHOW)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                context,
                NOTIFICATION_ID,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        String body = readyToInstall
                ? format(R.string.app_update_notification_ready, release.versionName)
                : format(R.string.app_update_notification_available, release.versionName);
        Notification notification = new Notification.Builder(context, NOTIFICATION_CHANNEL)
                .setSmallIcon(R.drawable.ic_church_prayers_notification)
                .setContentTitle(text(R.string.app_update_available_title))
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .setOnlyAlertOnce(true)
                .build();
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager != null) manager.notify(NOTIFICATION_ID, notification);
    }

    private void createNotificationChannel() {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return;
        NotificationChannel channel = new NotificationChannel(
                NOTIFICATION_CHANNEL,
                text(R.string.app_update_channel_name),
                NotificationManager.IMPORTANCE_DEFAULT
        );
        channel.setDescription(text(R.string.app_update_channel_description));
        manager.createNotificationChannel(channel);
    }

    private void cancelUpdateNotification() {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager != null) manager.cancel(NOTIFICATION_ID);
    }

    private boolean isActiveNetworkMetered() {
        ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
        return manager == null || manager.isActiveNetworkMetered();
    }

    private AppUpdateRelease savedRelease() {
        String value = preferences.availableAppUpdateJson();
        if (value.isEmpty()) return null;
        try {
            return AppUpdateRelease.fromJson(value);
        } catch (Exception ignored) {
            preferences.setAvailableAppUpdateJson("");
            return null;
        }
    }

    private File cachedApk() {
        String path = preferences.downloadedAppUpdatePath();
        if (path.isEmpty()) return null;
        File file = new File(path);
        File allowedDirectory = new File(context.getCacheDir(), "app-updates");
        try {
            String allowed = allowedDirectory.getCanonicalPath() + File.separator;
            if (!file.getCanonicalPath().startsWith(allowed) || !file.isFile()) return null;
        } catch (Exception ignored) {
            return null;
        }
        return file;
    }

    private void clearDownloadedUpdate() {
        File cached = cachedApk();
        if (cached != null) cached.delete();
        preferences.setDownloadedAppUpdatePath("");
        preferences.setPendingAppUpdateInstall(false);
    }

    private String text(int resourceId) {
        return LocalizedResources.get(context, preferences.effectiveLanguage(), resourceId);
    }

    private String format(int resourceId, Object... arguments) {
        return LocalizedResources.format(context, preferences.effectiveLanguage(), resourceId, arguments);
    }

    private static String humanSize(long bytes) {
        double megabytes = bytes / (1024.0 * 1024.0);
        return new DecimalFormat(megabytes >= 10.0 ? "0" : "0.0").format(megabytes) + " MB";
    }

    private interface CheckCallback {
        void onComplete(AppUpdateRelease release, Exception error);
    }
}
