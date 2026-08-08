package com.orthodoxprayers.privateapp.ui.screens;

import android.app.AlertDialog;
import android.graphics.Color;
import android.content.Intent;
import android.text.TextUtils;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.orthodoxprayers.privateapp.model.LocalizedValue;
import com.orthodoxprayers.privateapp.ui.ReaderAdapter;
import com.orthodoxprayers.privateapp.ui.ReadingProgressPolicy;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.ThemePalette;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

public final class ReaderScreen extends BaseScreen {
    private static final int READER_LAYOUT_VERSION = 2;

    private final String serviceId;
    private RecyclerView recycler;
    private LinearLayoutManager layoutManager;
    private ReaderAdapter adapter;
    private JSONObject service;
    private LinearLayout controlsPanel;
    private MaxHeightScrollView controlsViewport;
    private LinearLayout provenancePanel;
    private LinearLayout liturgyNavigationPanel;
    private TextView controlsHandle;
    private Button provenanceToggle;
    private Button liturgyNavigationToggle;
    private boolean controlsExpanded;
    private boolean reloadingReader;
    private final Handler autoScrollHandler = new Handler(Looper.getMainLooper());
    private boolean autoScrollActive;
    private Button autoScrollButton;
    private TextView readerProgress;
    private int lastDisplayedProgressPercent = -1;
    private boolean progressUpdateScheduled;
    private String readingProgressPrefix = "";
    private final Runnable autoScrollTick = new Runnable() {
        @Override public void run() {
            if (!autoScrollActive || recycler == null) return;
            int speed = Math.max(1, preferences.autoScrollSpeed());
            recycler.scrollBy(0, ui.dp(speed));
            if (!recycler.canScrollVertically(1)) {
                stopAutoScroll(false);
                return;
            }
            autoScrollHandler.postDelayed(this, 45L);
        }
    };

    public ReaderScreen(ScreenHost host, String serviceId) {
        super(host);
        this.serviceId = serviceId == null ? "" : serviceId;
    }

    @Override
    public View createView() {
        service = data.findService(serviceId);
        if (service == null) return errorView(local(com.orthodoxprayers.privateapp.R.string.ui_the_requested_text_was_not_found_in_the_app_data_97e2becd));

        preferences.recordRecentService(serviceId);
        JSONArray segments = service.optJSONArray("segments");
        if (segments == null || segments.length() == 0) {
            return errorView(local(com.orthodoxprayers.privateapp.R.string.ui_this_item_exists_in_the_index_but_its_content_is_ea12748d));
        }

        preferences.migrateReaderLayoutState(READER_LAYOUT_VERSION);
        controlsExpanded = preferences.readerControlsExpanded();
        adapter = new ReaderAdapter(ui, data, preferences, segments, service.optString("source_language", "ar"));

        applyReaderWindowPreferences();

        if (preferences.keepScreenOn()) {
            host.activity().getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }

        LinearLayout root = new LinearLayout(host.activity());
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(readerBackground());
        root.setLayoutDirection(preferences.isRtl() ? View.LAYOUT_DIRECTION_RTL : View.LAYOUT_DIRECTION_LTR);

        controlsPanel = buildControlsPanel();
        int displayHeight = host.activity().getResources().getDisplayMetrics().heightPixels;
        int maximumControlsHeight = Math.min(
                ui.dp(340),
                Math.max(ui.dp(180), Math.round(displayHeight * 0.38f))
        );
        controlsViewport = new MaxHeightScrollView(host.activity(), maximumControlsHeight);
        controlsViewport.setFillViewport(false);
        controlsViewport.setClipToPadding(false);
        controlsViewport.setVerticalScrollBarEnabled(true);
        controlsViewport.setOverScrollMode(View.OVER_SCROLL_IF_CONTENT_SCROLLS);
        controlsViewport.addView(controlsPanel, new ScrollView.LayoutParams(-1, -2));
        root.addView(controlsViewport, new LinearLayout.LayoutParams(-1, -2));

        controlsHandle = ui.infoBadge("");
        controlsHandle.setGravity(Gravity.CENTER);
        controlsHandle.setMinHeight(ui.dp(48));
        controlsHandle.setMinimumHeight(ui.dp(48));
        controlsHandle.setOnClickListener(v -> setControlsExpanded(!controlsExpanded, true));
        root.addView(controlsHandle, ui.margins(-1, -2, 10, 3, 10, 4));

        recycler = new RecyclerView(host.activity());
        layoutManager = new LinearLayoutManager(host.activity());
        recycler.setLayoutManager(layoutManager);
        recycler.setAdapter(adapter);
        recycler.setItemAnimator(null);
        recycler.setBackgroundColor(readerBackground());
        recycler.setClipToPadding(false);
        recycler.setPadding(0, ui.dp(4), 0, ui.dp(20));
        recycler.setOverScrollMode(View.OVER_SCROLL_IF_CONTENT_SCROLLS);
        recycler.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_prayer_text_swipe_up_or_down_to_read_bd037213));
        recycler.setMinimumHeight(ui.dp(180));
        recycler.addOnScrollListener(new RecyclerView.OnScrollListener() {
            @Override
            public void onScrolled(RecyclerView rv, int dx, int dy) {
                scheduleReaderProgressUpdate();
            }

            @Override
            public void onScrollStateChanged(RecyclerView rv, int newState) {
                if (newState == RecyclerView.SCROLL_STATE_DRAGGING && autoScrollActive) stopAutoScroll(false);
                if (newState == RecyclerView.SCROLL_STATE_IDLE) {
                    saveReaderPosition();
                }
            }
        });
        root.addView(recycler, new LinearLayout.LayoutParams(-1, 0, 1f));

        applyControlsVisibility(false);
        root.post(() -> { restoreReaderPosition(); updateReaderProgress(); });
        return root;
    }

    private LinearLayout buildControlsPanel() {
        LinearLayout panel = new LinearLayout(host.activity());
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setBackgroundColor(ui.colors().background());
        panel.setLayoutDirection(preferences.isRtl() ? View.LAYOUT_DIRECTION_RTL : View.LAYOUT_DIRECTION_LTR);
        panel.setElevation(ui.dp(3));

        panel.addView(compactHeader(), new LinearLayout.LayoutParams(-1, -2));
        panel.addView(toolBar(), new LinearLayout.LayoutParams(-1, -2));

        LinearLayout secondaryActions = ui.row();
        secondaryActions.setPadding(ui.dp(10), 0, ui.dp(10), ui.dp(2));

        if (isLiturgy()) {
            liturgyNavigationToggle = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_liturgy_sections_4caca03a), false);
            liturgyNavigationToggle.setOnClickListener(v -> toggleLiturgyNavigation());
            secondaryActions.addView(liturgyNavigationToggle, ui.weight(44));
        }

        provenanceToggle = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_source_information_a097085c), false);
        provenanceToggle.setOnClickListener(v -> toggleProvenance());
        secondaryActions.addView(provenanceToggle, ui.weight(44));
        panel.addView(secondaryActions, new LinearLayout.LayoutParams(-1, -2));

        if (isLiturgy()) {
            liturgyNavigationPanel = jumpBar();
            liturgyNavigationPanel.setVisibility(View.GONE);
            panel.addView(liturgyNavigationPanel, new LinearLayout.LayoutParams(-1, -2));
        }

        LinearLayout related = isLiturgy() ? null : relatedServicesBox();
        if (related != null) panel.addView(related, ui.margins(-1, -2, 10, 2, 10, 4));

        provenancePanel = provenanceBox();
        provenancePanel.setVisibility(View.GONE);
        panel.addView(provenancePanel, ui.margins(-1, -2, 14, 4, 14, 5));
        return panel;
    }

    private LinearLayout compactHeader() {
        LinearLayout header = ui.row();
        header.setPadding(ui.dp(10), ui.dp(7), ui.dp(10), ui.dp(5));
        header.setBackground(ui.gradient(ThemePalette.NAVY, ThemePalette.NAVY_2, 0, 0));

        TextView back = ui.backArrow(host::goBack);
        LinearLayout.LayoutParams backParams = new LinearLayout.LayoutParams(ui.dp(48), ui.dp(48));
        backParams.setMargins(ui.dp(3), ui.dp(2), ui.dp(3), ui.dp(2));
        header.addView(back, backParams);

        String title = localized(service.optJSONObject("title"), local(com.orthodoxprayers.privateapp.R.string.ui_text_9b77d3f7));
        TextView titleView = ui.text(title, 18, ThemePalette.GOLD, true);
        titleView.setGravity(Gravity.CENTER);
        titleView.setMaxLines(2);
        titleView.setEllipsize(TextUtils.TruncateAt.END);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            titleView.setAccessibilityHeading(true);
        }
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(0, -2, 1f);
        titleParams.setMargins(ui.dp(5), ui.dp(2), ui.dp(5), ui.dp(2));
        header.addView(titleView, titleParams);
        return header;
    }

    private void toggleProvenance() {
        if (provenancePanel == null) return;
        boolean show = provenancePanel.getVisibility() != View.VISIBLE;
        provenancePanel.setVisibility(show ? View.VISIBLE : View.GONE);
        if (provenanceToggle != null) {
            provenanceToggle.setText(show
                    ? local(com.orthodoxprayers.privateapp.R.string.ui_hide_source_information_7690343f)
                    : local(com.orthodoxprayers.privateapp.R.string.ui_source_information_a097085c));
        }
    }

    private void toggleLiturgyNavigation() {
        if (liturgyNavigationPanel == null) return;
        boolean show = liturgyNavigationPanel.getVisibility() != View.VISIBLE;
        liturgyNavigationPanel.setVisibility(show ? View.VISIBLE : View.GONE);
        if (liturgyNavigationToggle != null) {
            liturgyNavigationToggle.setText(show
                    ? local(com.orthodoxprayers.privateapp.R.string.ui_hide_liturgy_sections_10a04266)
                    : local(com.orthodoxprayers.privateapp.R.string.ui_liturgy_sections_4caca03a));
        }
    }

    private void restoreReaderPosition() {
        if (layoutManager == null || adapter == null || recycler == null) return;
        int count = adapter.getItemCount();
        if (count <= 0) return;
        int position = Math.max(0, Math.min(preferences.readerPosition(serviceId), count - 1));
        int offset = preferences.readerOffset(serviceId);
        layoutManager.scrollToPositionWithOffset(position, offset);
    }

    private void setControlsExpanded(boolean expanded, boolean userInitiated) {
        if (controlsPanel == null || controlsExpanded == expanded) return;
        saveReaderPosition();
        controlsExpanded = expanded;
        preferences.setReaderControlsExpanded(expanded);
        applyControlsVisibility(userInitiated);
        if (recycler != null) {
            recycler.post(() -> {
                restoreReaderPosition();
                if (userInitiated) recycler.requestFocus();
            });
        }
    }

    private void applyControlsVisibility(boolean announce) {
        if (controlsViewport == null) return;
        controlsViewport.clearAnimation();
        controlsViewport.setVisibility(controlsExpanded ? View.VISIBLE : View.GONE);
        if (controlsExpanded) {
            controlsViewport.post(() -> {
                controlsViewport.scrollTo(0, 0);
                controlsViewport.requestLayout();
            });
        }
        updateControlsHandle();
        if (announce && controlsHandle != null) {
            controlsHandle.announceForAccessibility(controlsHandle.getText());
        }
    }

    private void updateControlsHandle() {
        if (controlsHandle == null) return;
        String label = controlsExpanded
                ? local(com.orthodoxprayers.privateapp.R.string.ui_hide_reading_controls_3f083a9c)
                : local(com.orthodoxprayers.privateapp.R.string.ui_show_reading_controls_be8aae53);
        controlsHandle.setText(label);
        controlsHandle.setContentDescription(label);
    }

    private void saveReaderPosition() {
        if (layoutManager == null || recycler == null || adapter == null || adapter.getItemCount() == 0) return;
        int position = layoutManager.findFirstVisibleItemPosition();
        if (position == RecyclerView.NO_POSITION) return;
        View first = layoutManager.findViewByPosition(position);
        int offset = first == null ? 0 : first.getTop();
        preferences.setReaderPosition(serviceId, position, offset);
        int last = layoutManager.findLastVisibleItemPosition();
        preferences.setReaderProgressPercent(
                serviceId,
                ReadingProgressPolicy.percentFromLastVisible(last, adapter.getItemCount())
        );
    }

    private View errorView(String detail) {
        com.orthodoxprayers.privateapp.ui.UiKit.Page page = page(
                local(com.orthodoxprayers.privateapp.R.string.ui_unable_to_open_text_7f8e719c),
                true
        );
        TextView message = centered(detail, 16, ui.colors().warning(), true);
        add(page.root, message, 30, 30);
        return page.scroll;
    }

    private LinearLayout toolBar() {
        LinearLayout box = new LinearLayout(host.activity());
        box.setOrientation(LinearLayout.VERTICAL);

        LinearLayout primary = ui.row();
        primary.setPadding(ui.dp(10), ui.dp(3), ui.dp(10), ui.dp(1));
        Button favorite = ui.smallIconButton(
                com.orthodoxprayers.privateapp.R.drawable.ic_favorite,
                preferences.isFavorite(serviceId)
                        ? local(com.orthodoxprayers.privateapp.R.string.ui_saved_cd7c1a66)
                        : local(com.orthodoxprayers.privateapp.R.string.ui_favorite_1d799489),
                preferences.isFavorite(serviceId)
        );
        favorite.setOnClickListener(v -> {
            saveReaderPosition();
            boolean wasFavorite = preferences.isFavorite(serviceId);
            preferences.toggleFavorite(serviceId);
            if (!wasFavorite && preferences.isFavorite(serviceId)) {
                preferences.setFavoriteFolder(serviceId, "liturgy".equals(service.optString("category")) ? "liturgy" : "daily");
            }
            reloadReader();
        });
        primary.addView(favorite, ui.weight(46));

        Button smaller = ui.smallButton("A−", false);
        smaller.setOnClickListener(v -> {
            saveReaderPosition();
            preferences.setFontScale(preferences.fontScale() - 0.1f);
            reloadReader();
        });
        primary.addView(smaller, ui.weight(46));

        Button larger = ui.smallButton("A+", false);
        larger.setOnClickListener(v -> {
            saveReaderPosition();
            preferences.setFontScale(preferences.fontScale() + 0.1f);
            reloadReader();
        });
        primary.addView(larger, ui.weight(46));

        Button source = ui.smallButton(preferences.showOriginal()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_hide_source_b3b18955)
                : local(com.orthodoxprayers.privateapp.R.string.ui_show_source_6b38e880), preferences.showOriginal());
        source.setOnClickListener(v -> {
            saveReaderPosition();
            preferences.setShowOriginal(!preferences.showOriginal());
            reloadReader();
        });
        primary.addView(source, ui.weight(46));
        box.addView(primary, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout secondary = ui.row();
        secondary.setPadding(ui.dp(10), 0, ui.dp(10), ui.dp(2));
        Button pin = ui.smallButton(preferences.isPinned(serviceId)
                ? local(com.orthodoxprayers.privateapp.R.string.ui_pinned_c16bc6c1)
                : local(com.orthodoxprayers.privateapp.R.string.ui_pin_613a1567), preferences.isPinned(serviceId));
        pin.setOnClickListener(v -> {
            preferences.togglePinned(serviceId);
            reloadReader();
        });
        secondary.addView(pin, ui.weight(44));

        autoScrollButton = ui.smallButton(autoScrollLabel(), preferences.autoScrollSpeed() > 0);
        autoScrollButton.setOnClickListener(v -> cycleAutoScroll());
        secondary.addView(autoScrollButton, ui.weight(44));

        Button spacing = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_spacing_6ae53d69) + String.format(java.util.Locale.US, "%.2f", preferences.lineSpacingMultiplier()), false);
        spacing.setOnClickListener(v -> {
            float next = preferences.lineSpacingMultiplier() >= 1.55f ? 1.0f : preferences.lineSpacingMultiplier() + 0.15f;
            preferences.setLineSpacingMultiplier(next);
            saveReaderPosition();
            reloadReader();
        });
        secondary.addView(spacing, ui.weight(44));
        box.addView(secondary, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout readerTools = ui.row();
        readerTools.setPadding(ui.dp(10), 0, ui.dp(10), ui.dp(3));
        Button brightness = ui.smallIconButton(com.orthodoxprayers.privateapp.R.drawable.ic_action_brightness,
                preferences.readerBrightnessPercent() + "%", false);
        brightness.setOnClickListener(v -> cycleBrightness());
        readerTools.addView(brightness, ui.weight(44));

        Button theme = ui.smallButton(readerThemeLabel(), false);
        theme.setOnClickListener(v -> cycleReaderTheme());
        readerTools.addView(theme, ui.weight(44));

        Button note = ui.smallButton(preferences.serviceNote(serviceId).isEmpty()
                ? local(com.orthodoxprayers.privateapp.R.string.ui_note_66183bf4)
                : local(com.orthodoxprayers.privateapp.R.string.ui_edit_note_569b3288), false);
        note.setOnClickListener(v -> showNoteDialog());
        readerTools.addView(note, ui.weight(44));

        Button share = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_share_6b178c11), false);
        share.setOnClickListener(v -> shareCurrentSegment());
        readerTools.addView(share, ui.weight(44));
        box.addView(readerTools, new LinearLayout.LayoutParams(-1, -2));

        readingProgressPrefix = local(com.orthodoxprayers.privateapp.R.string.ui_reading_progress_b21e6b19);
        readerProgress = ui.infoBadge(local(com.orthodoxprayers.privateapp.R.string.ui_reading_progress_0_30d9316d));
        readerProgress.setGravity(Gravity.CENTER);
        box.addView(readerProgress, ui.margins(-1, -2, 10, 0, 10, 3));
        return box;
    }

    private void cycleBrightness() {
        int current = preferences.readerBrightnessPercent();
        int next = current > 80 ? 80 : current > 60 ? 60 : current > 40 ? 40 : current > 20 ? 20 : 100;
        preferences.setReaderBrightnessPercent(next);
        applyReaderWindowPreferences();
        reloadReader();
    }

    private String readerThemeLabel() {
        String theme = preferences.readerTheme();
        if ("sepia".equals(theme)) return local(com.orthodoxprayers.privateapp.R.string.ui_sepia_eea06eb6);
        if ("night".equals(theme)) return local(com.orthodoxprayers.privateapp.R.string.ui_night_e4245684);
        return local(com.orthodoxprayers.privateapp.R.string.ui_system_theme_b1e709b2);
    }

    private void cycleReaderTheme() {
        String current = preferences.readerTheme();
        preferences.setReaderTheme("system".equals(current) ? "sepia" : "sepia".equals(current) ? "night" : "system");
        saveReaderPosition();
        reloadReader();
    }

    private void showNoteDialog() {
        EditText input = new EditText(host.activity());
        input.setText(preferences.serviceNote(serviceId));
        input.setMinLines(4);
        input.setGravity(Gravity.TOP | (preferences.isRtl() ? Gravity.RIGHT : Gravity.LEFT));
        input.setHint(local(com.orthodoxprayers.privateapp.R.string.ui_write_a_private_note_stored_only_on_this_device_f02e467f));
        int padding = ui.dp(18);
        LinearLayout wrapper = new LinearLayout(host.activity());
        wrapper.setPadding(padding, ui.dp(8), padding, 0);
        wrapper.addView(input, new LinearLayout.LayoutParams(-1, -2));
        new AlertDialog.Builder(host.activity())
                .setTitle(local(com.orthodoxprayers.privateapp.R.string.ui_private_note_f993ef09))
                .setView(wrapper)
                .setPositiveButton(local(com.orthodoxprayers.privateapp.R.string.ui_save_d4087fa0), (dialog, which) -> {
                    preferences.setServiceNote(serviceId, input.getText().toString());
                    Toast.makeText(host.activity(), local(com.orthodoxprayers.privateapp.R.string.ui_note_saved_locally_9d17b58c), Toast.LENGTH_SHORT).show();
                    reloadReader();
                })
                .setNeutralButton(local(com.orthodoxprayers.privateapp.R.string.ui_delete_ea349e00), (dialog, which) -> {
                    preferences.setServiceNote(serviceId, "");
                    reloadReader();
                })
                .setNegativeButton(local(com.orthodoxprayers.privateapp.R.string.ui_cancel_1bd7a4b9), null)
                .show();
    }

    private void shareCurrentSegment() {
        if (adapter == null || layoutManager == null) return;
        int position = Math.max(0, layoutManager.findFirstVisibleItemPosition());
        String excerpt = adapter.shareTextAt(position);
        if (excerpt.isEmpty()) {
            Toast.makeText(host.activity(), local(com.orthodoxprayers.privateapp.R.string.ui_no_shareable_passage_is_visible_e0bd031d), Toast.LENGTH_SHORT).show();
            return;
        }
        String title = localized(service.optJSONObject("title"), local(com.orthodoxprayers.privateapp.R.string.ui_orthodox_text_ce84a657));
        String source = data.selectedOfficialSource();
        String footer = "\n\n— " + title + "\n"
                + local(com.orthodoxprayers.privateapp.R.string.ui_data_date_5059f13c) + data.dataDate();
        if (source != null && !source.trim().isEmpty()) {
            footer += "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_verified_source_d8f667a7) + source;
        }
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.setType("text/plain");
        intent.putExtra(Intent.EXTRA_SUBJECT, title);
        intent.putExtra(Intent.EXTRA_TEXT, excerpt + footer);
        host.activity().startActivity(Intent.createChooser(intent, local(com.orthodoxprayers.privateapp.R.string.ui_share_text_4596efcf)));
    }

    private void scheduleReaderProgressUpdate() {
        if (progressUpdateScheduled || recycler == null) return;
        progressUpdateScheduled = true;
        recycler.postOnAnimation(() -> {
            progressUpdateScheduled = false;
            updateReaderProgress();
        });
    }

    private void updateReaderProgress() {
        if (readerProgress == null || layoutManager == null || adapter == null || adapter.getItemCount() == 0) return;
        int last = layoutManager.findLastVisibleItemPosition();
        int percent = ReadingProgressPolicy.percentFromLastVisible(last, adapter.getItemCount());
        if (percent == lastDisplayedProgressPercent) return;
        lastDisplayedProgressPercent = percent;
        readerProgress.setText(readingProgressPrefix + percent + "%");
    }

    private int readerBackground() {
        if ("sepia".equals(preferences.readerTheme())) return Color.rgb(244, 236, 214);
        if ("night".equals(preferences.readerTheme())) return Color.rgb(9, 17, 29);
        return ui.colors().background();
    }

    private void applyReaderWindowPreferences() {
        WindowManager.LayoutParams attributes = host.activity().getWindow().getAttributes();
        attributes.screenBrightness = preferences.readerBrightnessPercent() / 100f;
        host.activity().getWindow().setAttributes(attributes);
    }

    private String autoScrollLabel() {
        int speed = preferences.autoScrollSpeed();
        if (speed <= 0) return local(com.orthodoxprayers.privateapp.R.string.ui_auto_scroll_43606e75);
        return (autoScrollActive ? "⏸ " : "▶ ") + local(com.orthodoxprayers.privateapp.R.string.ui_speed_331b3d1f) + speed;
    }

    private void cycleAutoScroll() {
        int current = preferences.autoScrollSpeed();
        int next;
        if (!autoScrollActive && current > 0) next = current;
        else next = current >= 4 ? 0 : current + 1;
        preferences.setAutoScrollSpeed(next);
        if (next == 0) stopAutoScroll(true); else startAutoScroll();
    }

    private void startAutoScroll() {
        autoScrollActive = preferences.autoScrollSpeed() > 0;
        autoScrollHandler.removeCallbacks(autoScrollTick);
        if (autoScrollActive) autoScrollHandler.postDelayed(autoScrollTick, 350L);
        if (autoScrollButton != null) {
            autoScrollButton.setText(autoScrollLabel());
            autoScrollButton.setAlpha(1f);
        }
    }

    private void stopAutoScroll(boolean clearSpeed) {
        autoScrollActive = false;
        autoScrollHandler.removeCallbacks(autoScrollTick);
        if (clearSpeed) preferences.setAutoScrollSpeed(0);
        if (autoScrollButton != null) autoScrollButton.setText(autoScrollLabel());
    }

    private LinearLayout provenanceBox() {
        LinearLayout box = ui.card();
        String notice = localized(service.optJSONObject("notice"), localized(data.library().optJSONObject("translation_notice"), ""));
        if (!notice.isEmpty()) {
            TextView text = centered(notice, 13, ui.colors().secondaryText(), false);
            box.addView(text);
        }
        JSONObject integrity = service.optJSONObject("integrity");
        JSONObject provenance = service.optJSONObject("source_provenance");
        boolean dailyVerified = integrity != null
                && ("VERIFIED_OFFICIAL_SOURCES".equals(integrity.optString("status"))
                || "VERIFIED_OFFICIAL_EXACT_SCRIPTURE".equals(integrity.optString("status"))
                || "VERIFIED_DYNAMIC_PROPERS_NATIVE_SCRIPTURE_FAIL_CLOSED".equals(integrity.optString("status")));
        boolean officialStatic = provenance != null
                && "OFFICIAL_ARABIC_EXACT_PINNED".equals(provenance.optString("status"));
        boolean pinnedStatic = provenance != null
                && "PINNED_STATIC_TEXT_WITH_OFFICIAL_CATALOG_PROVENANCE".equals(provenance.optString("status"));
        String badge;
        if (dailyVerified) {
            badge = local(com.orthodoxprayers.privateapp.R.string.ui_daily_propers_and_scripture_passed_source_and_si_d42c1070);
        } else if (officialStatic) {
            badge = local(com.orthodoxprayers.privateapp.R.string.ui_complete_arabic_text_pinned_from_an_official_ort_0c91e6fe);
        } else if (pinnedStatic) {
            badge = local(com.orthodoxprayers.privateapp.R.string.ui_pinned_fixed_text_daily_variables_change_only_af_c4a09a90);
        } else {
            badge = local(com.orthodoxprayers.privateapp.R.string.ui_source_state_is_incomplete_unverified_daily_text_0f17ecef);
        }
        box.addView(ui.badge(badge, dailyVerified || officialStatic || pinnedStatic),
                ui.margins(-1, -2, 0, notice.isEmpty() ? 0 : 7, 0, 0));

        LocalizedValue title = data.localizedValue(service.optJSONObject("title"), "");
        if (title.translationUnavailable) {
            box.addView(ui.badge(local(com.orthodoxprayers.privateapp.R.string.ui_verified_text_in_this_language_is_not_available__fc5b9c50), false), ui.margins(-1, -2, 0, 5, 0, 0));
        }

        JSONObject nativeSource = service.optJSONObject("native_source");
        JSONObject audit = service.optJSONObject("legacy_provenance_audit");
        JSONObject effective = provenance != null ? provenance : audit;
        String sourceId = nativeSource == null ? "" : nativeSource.optString("source_id", "").trim();
        if (sourceId.isEmpty() && effective != null) {
            sourceId = effective.optString("source_id", effective.optString("official_catalog_source", "")).trim();
        }
        String sourceUrl = nativeSource == null ? "" : nativeSource.optString("url", "").trim();
        if (sourceUrl.isEmpty() && effective != null) {
            sourceUrl = effective.optString("official_url", effective.optString("official_catalog_url", "")).trim();
        }
        if (sourceUrl.isEmpty() && !sourceId.isEmpty()) sourceUrl = data.sourceUrl(sourceId);
        if (!sourceId.isEmpty()) {
            String sourceName = data.sourceName(sourceId);
            box.addView(ui.text(local(com.orthodoxprayers.privateapp.R.string.ui_registered_source_b7f2bf22) + sourceName,
                    13, ui.colors().primaryText(), true), ui.margins(-1, -2, 0, 8, 0, 0));
        }
        if (!sourceUrl.isEmpty()) {
            final String url = sourceUrl;
            Button openSource = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_open_official_source_7127e1b7), false);
            openSource.setOnClickListener(v -> {
                try {
                    host.activity().startActivity(new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url)));
                } catch (Exception error) {
                    Toast.makeText(host.activity(), local(com.orthodoxprayers.privateapp.R.string.ui_the_source_link_could_not_be_opened_75a90f8a), Toast.LENGTH_LONG).show();
                }
            });
            box.addView(openSource, ui.margins(-1, -2, 0, 8, 0, 0));
        }
        Button allSources = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_all_sources_and_references_5cebd827), false);
        allSources.setOnClickListener(v -> host.navigate("sources", null));
        box.addView(allSources, ui.margins(-1, -2, 0, 5, 0, 0));
        return box;
    }

    private LinearLayout relatedServicesBox() {
        JSONArray related = service.optJSONArray("related_services");
        if (related == null || related.length() == 0) return null;
        LinearLayout box = ui.card();
        box.addView(ui.text(local(com.orthodoxprayers.privateapp.R.string.ui_prayers_related_to_this_service_7ef08ed3),
                13, ui.colors().primaryText(), true));
        for (int i = 0; i < related.length(); i++) {
            JSONObject item = related.optJSONObject(i);
            if (item == null) continue;
            String target = item.optString("service_id", "").trim();
            if (target.isEmpty()) continue;
            String label = localized(item.optJSONObject("label"), target);
            Button button = ui.smallButton(label, false);
            button.setOnClickListener(v -> host.navigate("reader", target));
            box.addView(button, ui.margins(-1, -2, 0, 5, 0, 0));
        }
        return box;
    }

    private LinearLayout jumpBar() {
        LinearLayout box = new LinearLayout(host.activity());
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(ui.dp(10), 0, ui.dp(10), ui.dp(4));

        LinearLayout jumps = ui.row();
        addJump(jumps, local(com.orthodoxprayers.privateapp.R.string.ui_prokeimenon_c8263ee7),
                adapter.findPosition("البروكيمنن", "Prokeimenon", "Προκείμενον"));
        addJump(jumps, local(com.orthodoxprayers.privateapp.R.string.ui_epistle_a17bc087),
                adapter.findPosition("الرسالة", "Epistle", "Ἀπόστολος"));
        addJump(jumps, local(com.orthodoxprayers.privateapp.R.string.ui_gospel_b7b033e7),
                adapter.findPosition("الإنجيل", "Gospel", "Εὐαγγέλιον"));
        box.addView(jumps);

        LinearLayout milestones = ui.row();
        addJump(milestones, local(com.orthodoxprayers.privateapp.R.string.ui_small_entrance_a637021b),
                adapter.findPosition("الدخول الصغير", "THE ENTRANCE", "ΜΙΚΡΑ ΕΙΣΟΔΟΣ"));
        addJump(milestones, local(com.orthodoxprayers.privateapp.R.string.ui_great_entrance_663a8293),
                adapter.findPosition("الدورة الكبرى", "THE GREAT ENTRANCE", "ΜΕΓΑΛΗ ΕΙΣΟΔΟΣ"));
        addJump(milestones, local(com.orthodoxprayers.privateapp.R.string.ui_communion_1cf76e7a),
                adapter.findPosition("المناولة", "HOLY COMMUNION", "ΘΕΙΑ ΜΕΤΑΛΗΨΙΣ"));
        addJump(milestones, local(com.orthodoxprayers.privateapp.R.string.ui_dismissal_715bd095),
                adapter.findPosition("الختام والصرف", "THE DISMISSAL", "ΑΠΟΛΥΣΙΣ"));
        box.addView(milestones);

        LinearLayout sectionNav = ui.row();
        Button previous = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_previous_section_6f025d4d), false);
        previous.setOnClickListener(v -> moveSection(false));
        sectionNav.addView(previous, ui.weight(44));
        Button next = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_next_section_3ecb1f00), false);
        next.setOnClickListener(v -> moveSection(true));
        sectionNav.addView(next, ui.weight(44));
        box.addView(sectionNav);
        return box;
    }

    private void addJump(LinearLayout row, String label, int position) {
        Button button = ui.smallButton(label, false);
        button.setEnabled(position >= 0);
        button.setAlpha(position >= 0 ? 1f : 0.5f);
        button.setOnClickListener(v -> scrollTo(position));
        row.addView(button, ui.weight(44));
    }

    private void moveSection(boolean forward) {
        if (adapter == null || layoutManager == null) return;
        List<Integer> sections = adapter.sectionPositions();
        if (sections.isEmpty()) return;
        int current = Math.max(0, layoutManager.findFirstVisibleItemPosition());
        int target = forward ? -1 : sections.get(0);
        if (forward) {
            for (int position : sections) {
                if (position > current) {
                    target = position;
                    break;
                }
            }
            if (target < 0) target = sections.get(sections.size() - 1);
        } else {
            for (int position : sections) {
                if (position >= current) break;
                target = position;
            }
        }
        scrollTo(target);
    }

    private void scrollTo(int position) {
        if (position < 0 || recycler == null || layoutManager == null) {
            Toast.makeText(host.activity(), local(com.orthodoxprayers.privateapp.R.string.ui_section_not_found_7c261455), Toast.LENGTH_SHORT).show();
            return;
        }
        performSectionJump(position);
    }

    private void performSectionJump(int position) {
        if (layoutManager == null || recycler == null) return;
        layoutManager.scrollToPositionWithOffset(position, 0);
        recycler.post(this::saveReaderPosition);
    }

    private void reloadReader() {
        reloadingReader = true;
        host.navigate("reader", serviceId);
    }

    private boolean isLiturgy() {
        String baseId = serviceId;
        int separator = baseId.indexOf("::");
        if (separator >= 0) baseId = baseId.substring(separator + 2);
        return "divine_liturgy".equals(baseId) || "next_sunday_full_liturgy".equals(baseId);
    }


    private static final class MaxHeightScrollView extends ScrollView {
        private final int maximumHeight;

        MaxHeightScrollView(android.content.Context context, int maximumHeight) {
            super(context);
            this.maximumHeight = Math.max(1, maximumHeight);
        }

        @Override
        protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
            int parentMode = MeasureSpec.getMode(heightMeasureSpec);
            int allowedHeight = maximumHeight;
            if (parentMode != MeasureSpec.UNSPECIFIED) {
                allowedHeight = Math.min(allowedHeight, MeasureSpec.getSize(heightMeasureSpec));
            }
            int cappedHeight = MeasureSpec.makeMeasureSpec(allowedHeight, MeasureSpec.AT_MOST);
            super.onMeasure(widthMeasureSpec, cappedHeight);
        }
    }

    @Override
    public void onHidden() {
        stopAutoScroll(false);
        saveReaderPosition();
        if (!reloadingReader) preferences.setReaderControlsExpanded(false);
        host.activity().getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        WindowManager.LayoutParams attributes = host.activity().getWindow().getAttributes();
        attributes.screenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;
        host.activity().getWindow().setAttributes(attributes);
    }
}
