package com.orthodoxprayers.privateapp;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;

import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.appupdate.AppUpdateManager;
import com.orthodoxprayers.privateapp.reminder.ReminderScheduler;
import com.orthodoxprayers.privateapp.ui.AppScreen;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.ThemePalette;
import com.orthodoxprayers.privateapp.ui.UiKit;
import com.orthodoxprayers.privateapp.ui.screens.BibleScreen;
import com.orthodoxprayers.privateapp.ui.screens.BibleTestamentScreen;
import com.orthodoxprayers.privateapp.ui.screens.BibleBookScreen;
import com.orthodoxprayers.privateapp.ui.screens.BibleChapterScreen;
import com.orthodoxprayers.privateapp.ui.screens.FavoritesScreen;
import com.orthodoxprayers.privateapp.ui.screens.FastingSummaryScreen;
import com.orthodoxprayers.privateapp.ui.screens.CalendarScreen;
import com.orthodoxprayers.privateapp.ui.screens.ChurchesScreen;
import com.orthodoxprayers.privateapp.ui.screens.CalendarDayScreen;
import com.orthodoxprayers.privateapp.ui.screens.HistoryScreen;
import com.orthodoxprayers.privateapp.ui.screens.LanguagePacksScreen;
import com.orthodoxprayers.privateapp.ui.screens.LiturgyHubScreen;
import com.orthodoxprayers.privateapp.ui.screens.HomeScreen;
import com.orthodoxprayers.privateapp.ui.screens.PrayerHubScreen;
import com.orthodoxprayers.privateapp.ui.screens.ServiceListScreen;
import com.orthodoxprayers.privateapp.ui.screens.ReaderScreen;
import com.orthodoxprayers.privateapp.ui.screens.ReadingDetailScreen;
import com.orthodoxprayers.privateapp.ui.screens.ReadingsScreen;
import com.orthodoxprayers.privateapp.ui.screens.SearchScreen;
import com.orthodoxprayers.privateapp.ui.screens.SettingsScreen;
import com.orthodoxprayers.privateapp.ui.screens.SourcesScreen;
import com.orthodoxprayers.privateapp.ui.screens.UpcomingScreen;
import com.orthodoxprayers.privateapp.update.UpdateCoordinator;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.Duration;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.concurrent.TimeUnit;

public final class MainActivity extends ComponentActivity implements ScreenHost {
    private static final String TAG = "OrthodoxNavigation";
    private static final String STATE_STACK = "screen_stack";
    public static final String EXTRA_SCREEN = "com.orthodoxprayers.privateapp.extra.SCREEN";
    public static final String EXTRA_ARGUMENT = "com.orthodoxprayers.privateapp.extra.ARGUMENT";
    private static final ZoneId AMMAN_ZONE = ZoneId.of("Asia/Amman");
    private static final long MIN_DAY_WATCH_DELAY_MS = 1_000L;
    private static final long AUTOMATIC_OPEN_BUSY_RETRY_DELAY_MS = 1_000L;
    private static final long AUTOMATIC_OPEN_RETRY_DELAY_MS = TimeUnit.MINUTES.toMillis(15);
    private static final long RESUME_MAINTENANCE_DELAY_MS = 350L;

    private AppPreferences preferences;
    private DataRepository repository;
    private UpdateCoordinator updateCoordinator;
    private AppUpdateManager appUpdateManager;
    private UiKit uiKit;
    private LinearLayout shell;
    private FrameLayout contentHost;
    private LinearLayout bottomNav;
    private final Deque<ScreenEntry> backStack = new ArrayDeque<>();
    private AppScreen visibleScreen;
    private String observedAmmanDate;
    private final Handler dayChangeHandler = new Handler(Looper.getMainLooper());
    private final Handler automaticUpdateHandler = new Handler(Looper.getMainLooper());
    private boolean dayChangeWatcherRunning;
    private boolean automaticOpenRefreshPending;
    private final Runnable dayChangeCheck = new Runnable() {
        @Override
        public void run() {
            if (!dayChangeWatcherRunning) return;
            evaluateForegroundRefresh(false);
            scheduleNextAmmanDayCheck();
        }
    };
    private final Runnable automaticOpenRefreshCheck = new Runnable() {
        @Override
        public void run() {
            if (!automaticOpenRefreshPending || !dayChangeWatcherRunning) return;
            if (!updateCoordinator.shouldCheckRemoteOnAppOpen()) {
                automaticUpdateHandler.postDelayed(
                        this,
                        AUTOMATIC_OPEN_BUSY_RETRY_DELAY_MS
                );
                return;
            }
            String currentDate = repository.currentAmmanDate();
            boolean dayChanged = observedAmmanDate != null && !observedAmmanDate.equals(currentDate);
            observedAmmanDate = currentDate;
            if (!updateCoordinator.shouldRefresh(dayChanged, true)) {
                automaticOpenRefreshPending = false;
                return;
            }
            automaticOpenRefreshPending = false;
            requestDataRefresh(
                    false,
                    dayChanged || !repository.hasUsableCurrentData(),
                    true
            );
        }
    };
    private final Runnable resumeMaintenance = new Runnable() {
        @Override
        public void run() {
            if (!dayChangeWatcherRunning || isFinishing()) return;
            ((OrthodoxPrayersApp) getApplication()).refreshShortcuts();
            updateCoordinator.scheduleDailyRefresh();
            appUpdateManager.schedulePeriodicChecks();
            boolean resumingAppUpdateInstall = appUpdateManager.resumePendingInstall(MainActivity.this);
            if (!resumingAppUpdateInstall) appUpdateManager.checkOnAppOpen(MainActivity.this);
        }
    };
    private int bottomNavBaseHeight;
    private int bottomNavBaseLeftPadding;
    private int bottomNavBaseTopPadding;
    private int bottomNavBaseRightPadding;
    private int bottomNavBaseBottomPadding;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        OrthodoxPrayersApp app = (OrthodoxPrayersApp) getApplication();
        preferences = app.preferences();
        repository = app.repository();
        updateCoordinator = app.updateCoordinator();
        appUpdateManager = app.appUpdateManager();
        uiKit = new UiKit(this, preferences);
        configureWindow();
        buildShell();
        if (savedInstanceState != null && savedInstanceState.containsKey(STATE_STACK)) {
            restoreStack(savedInstanceState.getString(STATE_STACK, ""));
        }
        if (backStack.isEmpty()) backStack.addLast(new ScreenEntry("home", null, null));
        applyLaunchIntent(getIntent(), false);
        show(backStack.peekLast());
        appUpdateManager.handleLaunchIntent(this, getIntent());
        observedAmmanDate = repository.currentAmmanDate();
        // Do not leave a freshly installed or day-stale build on the dated
        // snapshot while the user is already opening Liturgy or Readings. The
        // rebuild is local and asynchronous, so it starts immediately after the
        // first frame and rebinds the visible screen when today's package is ready.
        if (!repository.hasUsableCurrentData()) {
            requestDataRefresh(false, true, true);
        }
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                goBack();
            }
        });
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        applyLaunchIntent(intent, true);
        appUpdateManager.handleLaunchIntent(this, intent);
    }

    private void applyLaunchIntent(Intent intent, boolean render) {
        if (intent == null) return;
        String screen = intent.getStringExtra(EXTRA_SCREEN);
        if (screen == null || screen.trim().isEmpty()) return;
        String argument = intent.getStringExtra(EXTRA_ARGUMENT);
        backStack.clear();
        backStack.addLast(new ScreenEntry("home", null, null));
        if (!"home".equals(screen)) backStack.addLast(new ScreenEntry(screen, argument, null));
        intent.removeExtra(EXTRA_SCREEN);
        intent.removeExtra(EXTRA_ARGUMENT);
        if (render) show(backStack.peekLast());
    }

    @Override
    protected void onStart() {
        super.onStart();
        startDayChangeWatcher();
        automaticOpenRefreshPending = true;
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Draw the restored screen first. Launcher shortcuts, WorkManager and the
        // APK update check are useful maintenance, but none belongs on the path
        // that must complete before the first visible frame.
        automaticUpdateHandler.removeCallbacks(resumeMaintenance);
        automaticUpdateHandler.postDelayed(resumeMaintenance, RESUME_MAINTENANCE_DELAY_MS);
        if (automaticOpenRefreshPending) {
            automaticUpdateHandler.removeCallbacks(automaticOpenRefreshCheck);
            automaticUpdateHandler.post(automaticOpenRefreshCheck);
        } else {
            evaluateForegroundRefresh(true);
        }
    }

    @Override
    protected void onStop() {
        automaticOpenRefreshPending = false;
        automaticUpdateHandler.removeCallbacks(automaticOpenRefreshCheck);
        automaticUpdateHandler.removeCallbacks(resumeMaintenance);
        stopDayChangeWatcher();
        super.onStop();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != ReminderScheduler.NOTIFICATION_PERMISSION_REQUEST) return;
        String kind = preferences.pendingReminderKind();
        preferences.clearPendingReminderKind();
        if (kind.isEmpty()) return;
        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        preferences.setRemindersEnabled(kind, granted);
        ReminderScheduler scheduler = new ReminderScheduler(this, preferences);
        if (granted) scheduler.schedule(kind); else scheduler.cancel(kind);
        Toast.makeText(
                this,
                granted
                        ? repository.local(com.orthodoxprayers.privateapp.R.string.ui_reminder_enabled_f21995e2)
                        : repository.local(com.orthodoxprayers.privateapp.R.string.ui_the_reminder_was_not_enabled_because_notificatio_a2a9d4b5),
                Toast.LENGTH_SHORT
        ).show();
        ScreenEntry current = backStack.peekLast();
        if (current != null && ("settings".equals(current.screenId) || "settings_section".equals(current.screenId))) show(current);
    }


    private void configureWindow() {
        getWindow().setStatusBarColor(ThemePalette.NAVY);
        getWindow().setNavigationBarColor(ThemePalette.NAVY);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            getWindow().setNavigationBarContrastEnforced(false);
            getWindow().setStatusBarContrastEnforced(false);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            getWindow().setDecorFitsSystemWindows(false);
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            );
        }
    }

    private void buildShell() {
        shell = new LinearLayout(this);
        shell.setOrientation(LinearLayout.VERTICAL);
        shell.setBackgroundColor(uiKit.colors().background());

        FrameLayout contentFrame = new FrameLayout(this);
        contentFrame.setBackgroundColor(uiKit.colors().background());
        contentHost = new FrameLayout(this);
        int contentWidth = getResources().getConfiguration().smallestScreenWidthDp >= 600
                ? uiKit.dp(840)
                : -1;
        FrameLayout.LayoutParams contentParams = new FrameLayout.LayoutParams(contentWidth, -1);
        contentParams.gravity = Gravity.CENTER_HORIZONTAL;
        contentFrame.addView(contentHost, contentParams);
        shell.addView(contentFrame, new LinearLayout.LayoutParams(-1, 0, 1f));

        bottomNav = new LinearLayout(this);
        bottomNav.setOrientation(LinearLayout.HORIZONTAL);
        bottomNav.setGravity(Gravity.CENTER);
        bottomNavBaseLeftPadding = uiKit.dp(4);
        bottomNavBaseTopPadding = uiKit.dp(5);
        bottomNavBaseRightPadding = uiKit.dp(4);
        bottomNavBaseBottomPadding = uiKit.dp(5);
        bottomNavBaseHeight = uiKit.dp(70);
        bottomNav.setPadding(
                bottomNavBaseLeftPadding,
                bottomNavBaseTopPadding,
                bottomNavBaseRightPadding,
                bottomNavBaseBottomPadding
        );
        bottomNav.setBackgroundColor(uiKit.colors().navBackground());
        shell.addView(bottomNav, new LinearLayout.LayoutParams(-1, bottomNavBaseHeight));

        setContentView(shell);
        installSystemInsets();
    }

    private void installSystemInsets() {
        shell.setOnApplyWindowInsetsListener((view, windowInsets) -> {
            int left = Math.max(windowInsets.getSystemWindowInsetLeft(), windowInsets.getStableInsetLeft());
            int top = Math.max(windowInsets.getSystemWindowInsetTop(), windowInsets.getStableInsetTop());
            int right = Math.max(windowInsets.getSystemWindowInsetRight(), windowInsets.getStableInsetRight());
            int navigationBottom = Math.max(windowInsets.getSystemWindowInsetBottom(), windowInsets.getStableInsetBottom());
            shell.setPadding(left, top, right, 0);

            bottomNav.setPadding(
                    bottomNavBaseLeftPadding,
                    bottomNavBaseTopPadding,
                    bottomNavBaseRightPadding,
                    bottomNavBaseBottomPadding + navigationBottom
            );
            LinearLayout.LayoutParams params = (LinearLayout.LayoutParams) bottomNav.getLayoutParams();
            int requiredHeight = bottomNavBaseHeight + navigationBottom;
            if (params.height != requiredHeight) {
                params.height = requiredHeight;
                bottomNav.setLayoutParams(params);
            }
            return windowInsets;
        });
        shell.requestApplyInsets();
    }

    @Override
    public void navigate(String screenId, String argument) {
        captureCurrentScrollPosition();
        ScreenEntry current = backStack.peekLast();
        if (current != null && current.matches(screenId, argument)) {
            show(current);
            return;
        }
        ScreenEntry next = new ScreenEntry(screenId, argument, null);
        if (isTopLevel(screenId)) backStack.clear();
        backStack.addLast(next);
        show(next);
    }

    @Override
    public void openReading(JSONObject reading) {
        captureCurrentScrollPosition();
        ScreenEntry next = new ScreenEntry("reading_detail", null, reading == null ? null : reading.toString());
        backStack.addLast(next);
        show(next);
    }

    @Override
    public void goBack() {
        captureCurrentScrollPosition();
        if (backStack.size() > 1) {
            backStack.removeLast();
            show(backStack.peekLast());
        } else if (!"home".equals(currentScreenId())) {
            backStack.clear();
            backStack.addLast(new ScreenEntry("home", null, null));
            show(backStack.peekLast());
        } else {
            finish();
        }
    }


    @Override
    protected void onSaveInstanceState(Bundle outState) {
        captureCurrentScrollPosition();
        super.onSaveInstanceState(outState);
        JSONArray array = new JSONArray();
        for (ScreenEntry entry : backStack) array.put(entry.toJson());
        outState.putString(STATE_STACK, array.toString());
    }

    @Override
    protected void onDestroy() {
        automaticUpdateHandler.removeCallbacks(automaticOpenRefreshCheck);
        stopDayChangeWatcher();
        if (visibleScreen != null) visibleScreen.onHidden();
        super.onDestroy();
    }

    private void restoreStack(String serialized) {
        try {
            JSONArray array = new JSONArray(serialized);
            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.optJSONObject(i);
                if (item != null) backStack.addLast(ScreenEntry.fromJson(item));
            }
        } catch (Exception error) {
            Log.w(TAG, "Could not restore navigation state", error);
            backStack.clear();
        }
    }

    private void captureCurrentScrollPosition() {
        ScreenEntry current = backStack.peekLast();
        if (current == null || contentHost == null || contentHost.getChildCount() == 0) return;
        View view = contentHost.getChildAt(0);
        if (view instanceof ScrollView) {
            current.scrollY = Math.max(0, view.getScrollY());
        }
    }

    private void restoreEntryScrollPosition(ScreenEntry entry, View view) {
        if (!(view instanceof ScrollView) || entry.scrollY <= 0) return;
        view.post(() -> ((ScrollView) view).scrollTo(0, entry.scrollY));
    }

    private void show(ScreenEntry entry) {
        if (entry == null || isFinishing()) return;
        if (visibleScreen != null) visibleScreen.onHidden();
        uiKit.refreshTheme();
        contentHost.setBackgroundColor(uiKit.colors().background());
        bottomNav.setBackgroundColor(uiKit.colors().navBackground());
        visibleScreen = createScreen(entry);
        View view = visibleScreen.createView();
        contentHost.removeAllViews();
        contentHost.addView(view, new FrameLayout.LayoutParams(-1, -1));
        restoreEntryScrollPosition(entry, view);
        rebuildBottomNav(entry);
        visibleScreen.onVisible();
    }

    private AppScreen createScreen(ScreenEntry entry) {
        switch (entry.screenId) {
            case "home": return new HomeScreen(this);
            case "prayers": return new PrayerHubScreen(this);
            case "prayer_category": return new ServiceListScreen(this, entry.argument, prayerCategoryTitle(entry.argument));
            case "liturgy": return canOpenTodayLiturgyDirectly()
                    ? new ReaderScreen(this, "divine_liturgy")
                    : new LiturgyHubScreen(this);
            case "readings": return new ReadingsScreen(this);
            case "bible": return new BibleScreen(this);
            case "bible_testament": return new BibleTestamentScreen(this, entry.argument);
            case "bible_book": return new BibleBookScreen(this, entry.argument);
            case "bible_chapter": return new BibleChapterScreen(this, entry.argument);
            case "upcoming": return new UpcomingScreen(this);
            case "search": return new SearchScreen(this);
            case "favorites": return new FavoritesScreen(this);
            case "history": return new HistoryScreen(this);
            case "calendar": return new CalendarScreen(this, entry.argument);
            case "calendar_day": return new CalendarDayScreen(this, entry.argument);
            case "fasting_summary": return new FastingSummaryScreen(this, entry.argument);
            case "language_packs": return new LanguagePacksScreen(this);
            case "settings": return new SettingsScreen(this);
            case "settings_section": return new SettingsScreen(this, entry.argument);
            case "sources": return new SourcesScreen(this);
            case "churches": return new ChurchesScreen(this);
            case "reader": return new ReaderScreen(this, entry.argument);
            case "reading_detail":
                try { return new ReadingDetailScreen(this, entry.payload == null ? null : new JSONObject(entry.payload)); }
                catch (Exception error) {
                    Log.w(TAG, "Could not restore reading detail", error);
                    return new ReadingDetailScreen(this, null);
                }
            default: return new HomeScreen(this);
        }
    }

    private boolean canOpenTodayLiturgyDirectly() {
        if (!repository.isTodayCurrent()) return false;
        JSONObject selection = repository.today().optJSONObject("liturgy_service_selection");
        if (selection == null || !selection.optBoolean("displayable", false)) return false;
        String type = selection.optString("service_type", "").trim();
        if ("no_divine_liturgy".equals(type) || "typikon_override_required".equals(type)) return false;
        String serviceId = selection.optString("service_id", "divine_liturgy").trim();
        return serviceId.isEmpty() || "divine_liturgy".equals(serviceId);
    }

    private void rebuildBottomNav(ScreenEntry entry) {
        bottomNav.removeAllViews();
        String active = activeNav(entry);
        addNav(R.drawable.ic_nav_home, repository.local(com.orthodoxprayers.privateapp.R.string.ui_home_535f9515), "home", active);
        addNav(R.drawable.ic_nav_prayers, repository.local(com.orthodoxprayers.privateapp.R.string.ui_prayers_3a9327c4), "prayers", active);
        addNav(R.drawable.ic_nav_liturgy, repository.local(com.orthodoxprayers.privateapp.R.string.ui_liturgy_cdfaf7bd), "liturgy", active);
        addNav(R.drawable.ic_nav_settings, repository.local(com.orthodoxprayers.privateapp.R.string.ui_settings_25169a1d), "settings", active);
    }

    private void addNav(int iconResource, String label, String target, String active) {
        LinearLayout item = new LinearLayout(this);
        item.setOrientation(LinearLayout.VERTICAL);
        item.setGravity(Gravity.CENTER);
        item.setClickable(true);
        item.setFocusable(true);
        item.setSelected(target.equals(active));
        item.setPadding(uiKit.dp(3), uiKit.dp(3), uiKit.dp(3), uiKit.dp(3));
        item.setBackground(uiKit.round(
                target.equals(active) ? uiKit.colors().selectedNavBackground() : Color.TRANSPARENT,
                target.equals(active) ? ThemePalette.GOLD : Color.TRANSPARENT,
                13
        ));
        ImageView iconView = new ImageView(this);
        iconView.setImageResource(iconResource);
        iconView.setImageTintList(ColorStateList.valueOf(target.equals(active) ? ThemePalette.GOLD : Color.WHITE));
        iconView.setContentDescription(null);
        item.addView(iconView, new LinearLayout.LayoutParams(uiKit.dp(25), uiKit.dp(25)));
        TextView labelView = uiKit.text(label, 11, target.equals(active) ? ThemePalette.GOLD : Color.WHITE, true);
        labelView.setGravity(Gravity.CENTER);
        item.addView(labelView);
        item.setContentDescription(label + (target.equals(active) ? repository.local(com.orthodoxprayers.privateapp.R.string.ui_selected_5eb77fb2) : ""));
        item.setOnClickListener(v -> navigate(target, null));
        bottomNav.addView(item, new LinearLayout.LayoutParams(0, -1, 1f));
    }

    private String activeNav(ScreenEntry entry) {
        if (entry == null) return "home";
        if ("settings".equals(entry.screenId) || "settings_section".equals(entry.screenId)
                || "sources".equals(entry.screenId) || "churches".equals(entry.screenId)) return "settings";
        if ("prayers".equals(entry.screenId) || "prayer_category".equals(entry.screenId)) return "prayers";
        if ("liturgy".equals(entry.screenId)) return "liturgy";
        if ("reader".equals(entry.screenId)) {
            JSONObject service = repository.findService(entry.argument);
            if (service != null && "liturgy".equals(service.optString("category"))) return "liturgy";
            return "prayers";
        }
        return "home";
    }

    private String prayerCategoryTitle(String category) {
        if ("daily".equals(category)) {
            return repository.local(com.orthodoxprayers.privateapp.R.string.ui_daily_prayers_ef97d9fd);
        }
        if ("communion".equals(category)) {
            return repository.local(com.orthodoxprayers.privateapp.R.string.ui_holy_communion_prayers_e14c166c);
        }
        if ("church_service".equals(category)) {
            return repository.local(com.orthodoxprayers.privateapp.R.string.ui_church_service_section);
        }
        return repository.local(com.orthodoxprayers.privateapp.R.string.ui_basic_prayers_6f2ed521);
    }

    private boolean isTopLevel(String id) {
        return "home".equals(id) || "prayers".equals(id) || "liturgy".equals(id) || "settings".equals(id);
    }

    @Override
    public void refreshData() {
        requestDataRefresh(true, true);
    }

    private void requestDataRefresh(boolean manual, boolean forceFullDownload) {
        requestDataRefresh(manual, forceFullDownload, false);
    }

    private void requestDataRefresh(
            boolean manual,
            boolean forceFullDownload,
            boolean automaticAppOpen
    ) {
        if (repository.isRefreshing()) {
            if (automaticAppOpen && dayChangeWatcherRunning) {
                automaticOpenRefreshPending = true;
                automaticUpdateHandler.removeCallbacks(automaticOpenRefreshCheck);
                automaticUpdateHandler.postDelayed(
                        automaticOpenRefreshCheck,
                        AUTOMATIC_OPEN_BUSY_RETRY_DELAY_MS
                );
            }
            if (manual) {
                Toast.makeText(this, repository.local(com.orthodoxprayers.privateapp.R.string.ui_an_update_is_already_in_progress_0afb7ec0), Toast.LENGTH_SHORT).show();
            }
            return;
        }

        if (manual) {
            Toast.makeText(this, repository.local(com.orthodoxprayers.privateapp.R.string.ui_downloading_and_validating_today_s_data_f519f853), Toast.LENGTH_SHORT).show();
        }
        updateCoordinator.refreshForeground(forceFullDownload, (result, message) -> {
            boolean retryableOpenFailure = automaticAppOpen
                    && result == DataRepository.RefreshResult.FAILED
                    && DataRepository.isRetryableRefreshMessage(message);
            if (retryableOpenFailure) {
                // A retryable compatibility-channel failure may be retried in the
                // background, but the normal local daily engine never needs this path.
                updateCoordinator.enqueueImmediateBackgroundRefresh(false);
            }

            if (isFinishing() || (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1 && isDestroyed())) return;

            if (retryableOpenFailure && dayChangeWatcherRunning) {
                automaticOpenRefreshPending = true;
                automaticUpdateHandler.removeCallbacks(automaticOpenRefreshCheck);
                automaticUpdateHandler.postDelayed(
                        automaticOpenRefreshCheck,
                        AUTOMATIC_OPEN_RETRY_DELAY_MS
                );
            }

            // A manual failure should be diagnosable without asking the user to reproduce it.
            // Keep the technical panel expanded and show the stable classifier code in the toast.
            if (manual && result == DataRepository.RefreshResult.FAILED) {
                preferences.setAdvancedDiagnosticsExpanded(true);
            }

            // Every data-backed screen must reflect a newly accepted snapshot. Reader
            // screens persist their RecyclerView position in onHidden(); ScrollViews are
            // restored explicitly below.
            if (result == DataRepository.RefreshResult.UPDATED
                    || manual
                    || (automaticAppOpen && result != DataRepository.RefreshResult.FAILED)) {
                refreshVisibleScreenPreservingScroll();
            }

            if (manual) {
                String messageForUser = repository.userFacingRefreshStatus();
                if (result == DataRepository.RefreshResult.FAILED) {
                    messageForUser += "\n"
                            + repository.local(com.orthodoxprayers.privateapp.R.string.ui_update_diagnostic_code_400000df)
                            + repository.refreshDiagnosticCode();
                }
                Toast.makeText(
                        this,
                        messageForUser,
                        result == DataRepository.RefreshResult.FAILED ? Toast.LENGTH_LONG : Toast.LENGTH_SHORT
                ).show();
            } else if (result == DataRepository.RefreshResult.FAILED && !repository.hasDisplayableData()) {
                Toast.makeText(this, repository.userFacingRefreshStatus(), Toast.LENGTH_LONG).show();
            }
        });
    }

    private void evaluateForegroundRefresh(boolean resumeEvent) {
        String currentDate = repository.currentAmmanDate();
        boolean dayChanged = observedAmmanDate != null && !observedAmmanDate.equals(currentDate);
        observedAmmanDate = currentDate;

        if (updateCoordinator.shouldRefresh(dayChanged, resumeEvent)) {
            requestDataRefresh(false, dayChanged || !repository.hasUsableCurrentData());
        }
    }

    private void startDayChangeWatcher() {
        if (dayChangeWatcherRunning) return;
        dayChangeWatcherRunning = true;
        scheduleNextAmmanDayCheck();
    }

    private void stopDayChangeWatcher() {
        dayChangeWatcherRunning = false;
        dayChangeHandler.removeCallbacks(dayChangeCheck);
    }

    private void scheduleNextAmmanDayCheck() {
        if (!dayChangeWatcherRunning) return;
        dayChangeHandler.removeCallbacks(dayChangeCheck);
        ZonedDateTime now = ZonedDateTime.now(AMMAN_ZONE);
        ZonedDateTime nextDay = now.toLocalDate().plusDays(1).atStartOfDay(AMMAN_ZONE).plusSeconds(2);
        long delay = Math.max(MIN_DAY_WATCH_DELAY_MS, Duration.between(now, nextDay).toMillis());
        dayChangeHandler.postDelayed(dayChangeCheck, delay);
    }

    private void refreshVisibleScreenPreservingScroll() {
        ScreenEntry current = backStack.peekLast();
        if (current == null) return;
        ScreenEntry rebound = rebindEntryToCurrentData(current);
        if (rebound != current) {
            backStack.removeLast();
            backStack.addLast(rebound);
            current = rebound;
        }

        int scrollX = 0;
        int scrollY = 0;
        View oldView = contentHost.getChildCount() == 0 ? null : contentHost.getChildAt(0);
        if (oldView instanceof ScrollView) {
            scrollX = oldView.getScrollX();
            scrollY = oldView.getScrollY();
        }

        show(current);

        View newView = contentHost.getChildCount() == 0 ? null : contentHost.getChildAt(0);
        if (newView instanceof ScrollView) {
            final int restoreX = scrollX;
            final int restoreY = scrollY;
            newView.post(() -> newView.scrollTo(restoreX, restoreY));
        }
    }

    private ScreenEntry rebindEntryToCurrentData(ScreenEntry entry) {
        if (!"reading_detail".equals(entry.screenId) || entry.payload == null) return entry;
        try {
            JSONObject previous = new JSONObject(entry.payload);
            JSONObject replacement = findCurrentReading(previous);
            return replacement == null ? entry : new ScreenEntry("reading_detail", null, replacement.toString(), entry.scrollY);
        } catch (Exception error) {
            Log.w(TAG, "Could not rebind reading detail after data refresh", error);
            return entry;
        }
    }

    private JSONObject findCurrentReading(JSONObject previous) {
        JSONArray readings = repository.currentReadings();
        if (readings == null) return null;
        String kind = previous.optString("kind", "");
        JSONObject previousIntegrity = previous.optJSONObject("integrity");
        String canonical = previousIntegrity == null ? "" : previousIntegrity.optString("canonical_reference", "");
        JSONObject previousReference = previous.optJSONObject("reference");
        String arabicReference = previousReference == null ? "" : previousReference.optString("ar", "");
        for (int i = 0; i < readings.length(); i++) {
            JSONObject candidate = readings.optJSONObject(i);
            if (candidate == null || !kind.equals(candidate.optString("kind", ""))) continue;
            JSONObject integrity = candidate.optJSONObject("integrity");
            String candidateCanonical = integrity == null ? "" : integrity.optString("canonical_reference", "");
            JSONObject reference = candidate.optJSONObject("reference");
            String candidateArabic = reference == null ? "" : reference.optString("ar", "");
            if ((!canonical.isEmpty() && canonical.equals(candidateCanonical))
                    || (!arabicReference.isEmpty() && arabicReference.equals(candidateArabic))) {
                return candidate;
            }
        }
        return null;
    }

    @Override public Activity activity() { return this; }
    @Override public UiKit ui() { return uiKit; }
    @Override public DataRepository data() { return repository; }
    @Override public AppPreferences preferences() { return preferences; }
    @Override public String currentScreenId() {
        ScreenEntry entry = backStack.peekLast();
        return entry == null ? "home" : entry.screenId;
    }

    private static final class ScreenEntry {
        final String screenId;
        final String argument;
        final String payload;
        int scrollY;

        ScreenEntry(String screenId, String argument, String payload) {
            this(screenId, argument, payload, 0);
        }

        ScreenEntry(String screenId, String argument, String payload, int scrollY) {
            this.screenId = screenId == null ? "home" : screenId;
            this.argument = argument;
            this.payload = payload;
            this.scrollY = Math.max(0, scrollY);
        }

        boolean matches(String screen, String arg) {
            if (!screenId.equals(screen)) return false;
            if (argument == null) return arg == null;
            return argument.equals(arg);
        }

        JSONObject toJson() {
            JSONObject object = new JSONObject();
            try {
                object.put("screen", screenId);
                if (argument != null) object.put("argument", argument);
                if (payload != null) object.put("payload", payload);
                object.put("scroll_y", scrollY);
            } catch (Exception error) {
                Log.w(TAG, "Could not serialize navigation entry", error);
            }
            return object;
        }

        static ScreenEntry fromJson(JSONObject object) {
            return new ScreenEntry(
                    object.optString("screen", "home"),
                    object.has("argument") ? object.optString("argument", null) : null,
                    object.has("payload") ? object.optString("payload", null) : null,
                    object.optInt("scroll_y", 0)
            );
        }
    }
}
