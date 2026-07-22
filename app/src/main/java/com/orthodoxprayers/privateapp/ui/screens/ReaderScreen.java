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
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.model.LocalizedValue;
import com.orthodoxprayers.privateapp.ui.ReaderAdapter;
import com.orthodoxprayers.privateapp.ui.ReaderControlsPolicy;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.ThemePalette;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

public final class ReaderScreen extends BaseScreen {
    private static final int READER_LAYOUT_VERSION = 2;
    private static final int AUTO_COLLAPSE_DISTANCE_DP = 64;
    private static final int AUTO_EXPAND_DISTANCE_DP = 84;

    private final String serviceId;
    private RecyclerView recycler;
    private LinearLayoutManager layoutManager;
    private ReaderAdapter adapter;
    private JSONObject service;
    private LinearLayout controlsPanel;
    private LinearLayout provenancePanel;
    private LinearLayout liturgyNavigationPanel;
    private TextView controlsHandle;
    private Button provenanceToggle;
    private Button liturgyNavigationToggle;
    private boolean controlsExpanded;
    private boolean ignoreScrollUntilIdle;
    private ReaderControlsPolicy controlsPolicy;
    private int currentScrollState = RecyclerView.SCROLL_STATE_IDLE;
    private final Handler autoScrollHandler = new Handler(Looper.getMainLooper());
    private boolean autoScrollActive;
    private Button autoScrollButton;
    private ProgressBar readerProgressBar;
    private TextView readerProgressLabel;
    private LinearLayout relatedServicesPanel;
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
        if (service == null) return errorView(local(
                "تعذر العثور على النص المطلوب داخل بيانات التطبيق.",
                "The requested text was not found in the app data.",
                "Τὸ ζητούμενο κείμενο δὲν βρέθηκε στὰ δεδομένα."
        ));

        preferences.recordRecentService(serviceId);
        JSONArray segments = service.optJSONArray("segments");
        if (segments == null || segments.length() == 0) {
            return errorView(local(
                    "هذا النص موجود في الفهرس، لكن محتواه فارغ. تم منع فتح صفحة بيضاء.",
                    "This item exists in the index, but its content is empty. A blank reader was blocked.",
                    "Τὸ στοιχεῖο ὑπάρχει, ἀλλὰ τὸ περιεχόμενο εἶναι κενό."
            ));
        }

        preferences.migrateReaderLayoutState(READER_LAYOUT_VERSION);
        controlsExpanded = preferences.readerControlsExpanded();
        controlsPolicy = new ReaderControlsPolicy(
                ui.dp(AUTO_COLLAPSE_DISTANCE_DP),
                ui.dp(AUTO_EXPAND_DISTANCE_DP),
                controlsExpanded
        );
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
        root.addView(controlsPanel, new LinearLayout.LayoutParams(-1, -2));

        controlsHandle = ui.infoBadge("");
        controlsHandle.setGravity(Gravity.CENTER);
        controlsHandle.setMinHeight(ui.dp(36));
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
        recycler.setContentDescription(local(
                "نص الصلاة. اسحب للأعلى أو للأسفل للقراءة.",
                "Prayer text. Swipe up or down to read.",
                "Κείμενο προσευχῆς. Σύρετε πάνω ἢ κάτω."
        ));
        recycler.addOnScrollListener(new RecyclerView.OnScrollListener() {
            @Override
            public void onScrolled(RecyclerView rv, int dx, int dy) {
                handleReaderScroll(dy);
                updateReaderProgress();
            }

            @Override
            public void onScrollStateChanged(RecyclerView rv, int newState) {
                currentScrollState = newState;
                if (newState == RecyclerView.SCROLL_STATE_DRAGGING && autoScrollActive) stopAutoScroll(false);
                if (newState == RecyclerView.SCROLL_STATE_IDLE) {
                    ignoreScrollUntilIdle = false;
                    if (controlsPolicy != null) controlsPolicy.resetGesture();
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

        if (isLiturgy()) {
            liturgyNavigationPanel = jumpBar();
            liturgyNavigationPanel.setVisibility(View.GONE);
            panel.addView(liturgyNavigationPanel, new LinearLayout.LayoutParams(-1, -2));
        }

        relatedServicesPanel = relatedServicesBox();
        if (relatedServicesPanel != null) {
            relatedServicesPanel.setVisibility(View.GONE);
            panel.addView(relatedServicesPanel, ui.margins(-1, -2, 12, 4, 12, 5));
        }

        provenancePanel = provenanceBox();
        provenancePanel.setVisibility(View.GONE);
        panel.addView(provenancePanel, ui.margins(-1, -2, 12, 4, 12, 5));
        return panel;
    }

    private LinearLayout compactHeader() {
        LinearLayout header = ui.row();
        header.setPadding(ui.dp(8), ui.dp(6), ui.dp(8), ui.dp(6));
        header.setMinimumHeight(ui.dp(62));
        header.setBackground(ui.gradient(ThemePalette.NAVY, ThemePalette.NAVY_2, 0, 0));

        ImageButton back = ui.iconButton(R.drawable.ic_arrow_back,
                local("رجوع", "Back", "Πίσω"), false);
        back.setRotation(preferences.isRtl() ? 180f : 0f);
        back.setOnClickListener(v -> host.goBack());
        header.addView(back, new LinearLayout.LayoutParams(ui.dp(48), ui.dp(48)));

        String title = localized(service.optJSONObject("title"), local("النص", "Text", "Κείμενο"));
        TextView titleView = ui.text(title, 18, Color.WHITE, true);
        titleView.setGravity(Gravity.CENTER);
        titleView.setMaxLines(2);
        titleView.setEllipsize(TextUtils.TruncateAt.END);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) titleView.setAccessibilityHeading(true);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(0, -2, 1f);
        titleParams.setMargins(ui.dp(6), ui.dp(2), ui.dp(6), ui.dp(2));
        header.addView(titleView, titleParams);

        boolean saved = preferences.isFavorite(serviceId);
        ImageButton favorite = ui.iconButton(R.drawable.ic_favorite,
                saved ? local("إزالة من المفضلة", "Remove from favorites", "Ἀφαίρεση ἀπὸ ἀγαπημένα")
                        : local("إضافة إلى المفضلة", "Add to favorites", "Προσθήκη στὰ ἀγαπημένα"), saved);
        favorite.setOnClickListener(v -> {
            saveReaderPosition();
            boolean wasFavorite = preferences.isFavorite(serviceId);
            preferences.toggleFavorite(serviceId);
            if (!wasFavorite && preferences.isFavorite(serviceId)) {
                preferences.setFavoriteFolder(serviceId, "liturgy".equals(service.optString("category")) ? "liturgy" : "daily");
            }
            host.navigate("reader", serviceId);
        });
        header.addView(favorite, new LinearLayout.LayoutParams(ui.dp(48), ui.dp(48)));
        return header;
    }

    private void toggleProvenance() {
        if (provenancePanel == null) return;
        boolean show = provenancePanel.getVisibility() != View.VISIBLE;
        provenancePanel.setVisibility(show ? View.VISIBLE : View.GONE);
        if (provenanceToggle != null) {
            provenanceToggle.setText(show
                    ? local("إخفاء معلومات المصدر", "Hide source information", "Κρύψε πληροφορίες")
                    : local("معلومات المصدر", "Source information", "Πληροφορίες πηγῆς"));
        }
    }

    private void toggleLiturgyNavigation() {
        if (liturgyNavigationPanel == null) return;
        boolean show = liturgyNavigationPanel.getVisibility() != View.VISIBLE;
        liturgyNavigationPanel.setVisibility(show ? View.VISIBLE : View.GONE);
        if (liturgyNavigationToggle != null) {
            liturgyNavigationToggle.setText(show
                    ? local("إخفاء أقسام القداس", "Hide liturgy sections", "Κρύψε ἐνότητες")
                    : local("أقسام القداس", "Liturgy sections", "Ἐνότητες Λειτουργίας"));
        }
    }

    private void restoreReaderPosition() {
        if (layoutManager == null || adapter == null || recycler == null) return;
        int count = adapter.getItemCount();
        if (count <= 0) return;
        int position = Math.max(0, Math.min(preferences.readerPosition(serviceId), count - 1));
        int offset = preferences.readerOffset(serviceId);
        ignoreScrollUntilIdle = true;
        layoutManager.scrollToPositionWithOffset(position, offset);
        recycler.post(() -> ignoreScrollUntilIdle = false);
    }

    private void handleReaderScroll(int dy) {
        if (dy == 0 || ignoreScrollUntilIdle || controlsPolicy == null) return;
        ReaderControlsPolicy.Action action = controlsPolicy.onScroll(
                dy,
                currentScrollState == RecyclerView.SCROLL_STATE_DRAGGING,
                recycler != null && recycler.canScrollVertically(-1)
        );
        if (action == ReaderControlsPolicy.Action.COLLAPSE) {
            setControlsExpanded(false, false);
        } else if (action == ReaderControlsPolicy.Action.EXPAND) {
            setControlsExpanded(true, false);
        }
    }

    private void setControlsExpanded(boolean expanded, boolean userInitiated) {
        if (controlsPanel == null || controlsExpanded == expanded) return;
        saveReaderPosition();
        controlsExpanded = expanded;
        preferences.setReaderControlsExpanded(expanded);
        if (controlsPolicy != null) controlsPolicy.setExpanded(expanded);
        ignoreScrollUntilIdle = true;
        applyControlsVisibility(userInitiated);
        if (recycler != null) {
            recycler.post(() -> {
                restoreReaderPosition();
                if (userInitiated) recycler.requestFocus();
            });
        }
    }

    private void applyControlsVisibility(boolean announce) {
        if (controlsPanel == null) return;
        controlsPanel.clearAnimation();
        controlsPanel.setVisibility(controlsExpanded ? View.VISIBLE : View.GONE);
        updateControlsHandle();
        if (announce && controlsHandle != null) {
            controlsHandle.announceForAccessibility(controlsHandle.getText());
        }
    }

    private void updateControlsHandle() {
        if (controlsHandle == null) return;
        String label = controlsExpanded
                ? local(
                        "إخفاء أدوات القراءة",
                        "Hide reading tools",
                        "Κρύψε τὰ ἐργαλεῖα"
                )
                : local(
                        "إظهار أدوات القراءة",
                        "Show reading tools",
                        "Ἐμφάνιση ἐργαλείων"
                );
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
    }

    private View errorView(String detail) {
        com.orthodoxprayers.privateapp.ui.UiKit.Page page = page(
                local("تعذر فتح النص", "Unable to open text", "Ἀδυναμία ἀνοίγματος"),
                true
        );
        TextView message = centered(detail, 16, ui.colors().warning(), true);
        add(page.root, message, 30, 30);
        return page.scroll;
    }

    private LinearLayout toolBar() {
        LinearLayout box = new LinearLayout(host.activity());
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(ui.dp(10), ui.dp(5), ui.dp(10), ui.dp(5));

        LinearLayout primary = ui.row();
        Button smaller = ui.smallButton("A−", false);
        smaller.setContentDescription(local("تصغير الخط", "Decrease text size", "Μείωση γραμματοσειρᾶς"));
        smaller.setOnClickListener(v -> {
            saveReaderPosition();
            preferences.setFontScale(preferences.fontScale() - 0.1f);
            host.navigate("reader", serviceId);
        });
        primary.addView(smaller, ui.weight(44));

        Button larger = ui.smallButton("A+", false);
        larger.setContentDescription(local("تكبير الخط", "Increase text size", "Αὔξηση γραμματοσειρᾶς"));
        larger.setOnClickListener(v -> {
            saveReaderPosition();
            preferences.setFontScale(preferences.fontScale() + 0.1f);
            host.navigate("reader", serviceId);
        });
        primary.addView(larger, ui.weight(44));

        Button source = ui.smallButton(preferences.showOriginal()
                ? local("إخفاء الأصل", "Hide source", "Κρύψε πρωτότυπο")
                : local("إظهار الأصل", "Show source", "Πρωτότυπο"), preferences.showOriginal());
        source.setOnClickListener(v -> {
            saveReaderPosition();
            preferences.setShowOriginal(!preferences.showOriginal());
            host.navigate("reader", serviceId);
        });
        primary.addView(source, ui.weight(56));

        Button tools = ui.smallButton(local("الأدوات", "Tools", "Ἐργαλεῖα"), false);
        android.graphics.drawable.Drawable more = host.activity().getDrawable(R.drawable.ic_more);
        if (more != null) {
            more.setTint(ui.colors().accentText());
            int size = ui.dp(21);
            more.setBounds(0, 0, size, size);
            tools.setCompoundDrawablesRelative(more, null, null, null);
            tools.setCompoundDrawablePadding(ui.dp(5));
        }
        tools.setOnClickListener(this::showReaderToolsMenu);
        primary.addView(tools, ui.weight(56));
        box.addView(primary, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout progressRow = ui.row();
        progressRow.setPadding(ui.dp(4), ui.dp(3), ui.dp(4), 0);
        readerProgressBar = new ProgressBar(host.activity(), null, android.R.attr.progressBarStyleHorizontal);
        readerProgressBar.setMax(100);
        readerProgressBar.setProgressTintList(android.content.res.ColorStateList.valueOf(ThemePalette.GOLD));
        readerProgressBar.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(ui.colors().divider()));
        LinearLayout.LayoutParams progressParams = new LinearLayout.LayoutParams(0, ui.dp(5), 1f);
        progressParams.setMargins(0, 0, ui.dp(10), 0);
        progressRow.addView(readerProgressBar, progressParams);
        readerProgressLabel = ui.text("0%", 12, ui.colors().secondaryText(), true);
        readerProgressLabel.setGravity(Gravity.CENTER);
        progressRow.addView(readerProgressLabel, new LinearLayout.LayoutParams(ui.dp(48), -2));
        box.addView(progressRow, new LinearLayout.LayoutParams(-1, -2));
        return box;
    }

    private void showReaderToolsMenu(View anchor) {
        PopupMenu popup = new PopupMenu(host.activity(), anchor);
        popup.getMenu().add(0, 1, 0, preferences.isPinned(serviceId)
                ? local("إلغاء التثبيت", "Unpin", "Ἀφαίρεση καρφιτσώματος")
                : local("تثبيت في الرئيسية", "Pin to home", "Καρφίτσωμα στὴν ἀρχική"));
        popup.getMenu().add(0, 2, 1, autoScrollLabel());
        popup.getMenu().add(0, 3, 2, local("تباعد الأسطر: ", "Line spacing: ", "Διάστιχο: ")
                + String.format(java.util.Locale.US, "%.2f", preferences.lineSpacingMultiplier()));
        popup.getMenu().add(0, 4, 3, local("سطوع القارئ: ", "Reader brightness: ", "Φωτεινότητα: ") + preferences.readerBrightnessPercent() + "%");
        popup.getMenu().add(0, 5, 4, local("ثيم القارئ: ", "Reader theme: ", "Θέμα: ") + readerThemeLabel());
        popup.getMenu().add(0, 6, 5, preferences.serviceNote(serviceId).isEmpty()
                ? local("إضافة ملاحظة شخصية", "Add private note", "Προσθήκη σημειώσεως")
                : local("تعديل الملاحظة الشخصية", "Edit private note", "Ἐπεξεργασία σημειώσεως"));
        popup.getMenu().add(0, 7, 6, local("مشاركة المقطع الظاهر", "Share visible passage", "Κοινοποίηση κειμένου"));
        if (isLiturgy()) popup.getMenu().add(0, 8, 7, local("أقسام القداس", "Liturgy sections", "Ἐνότητες Λειτουργίας"));
        popup.getMenu().add(0, 9, 8, local("معلومات المصدر", "Source information", "Πληροφορίες πηγῆς"));
        if (relatedServicesPanel != null) popup.getMenu().add(0, 10, 9, local("صلوات مرتبطة", "Related prayers", "Σχετικὲς προσευχές"));
        popup.setOnMenuItemClickListener(item -> {
            switch (item.getItemId()) {
                case 1:
                    preferences.togglePinned(serviceId);
                    Toast.makeText(host.activity(), preferences.isPinned(serviceId)
                            ? local("تم تثبيت النص في الرئيسية", "Pinned to the home screen", "Καρφιτσώθηκε")
                            : local("تم إلغاء تثبيت النص", "Text unpinned", "Ἀφαιρέθηκε"), Toast.LENGTH_SHORT).show();
                    return true;
                case 2:
                    cycleAutoScroll();
                    return true;
                case 3:
                    preferences.setLineSpacingMultiplier(preferences.lineSpacingMultiplier() >= 1.55f ? 1.0f : preferences.lineSpacingMultiplier() + 0.15f);
                    saveReaderPosition();
                    host.navigate("reader", serviceId);
                    return true;
                case 4:
                    cycleBrightness();
                    return true;
                case 5:
                    cycleReaderTheme();
                    return true;
                case 6:
                    showNoteDialog();
                    return true;
                case 7:
                    shareCurrentSegment();
                    return true;
                case 8:
                    toggleLiturgyNavigation();
                    return true;
                case 9:
                    toggleProvenance();
                    return true;
                case 10:
                    boolean show = relatedServicesPanel.getVisibility() != View.VISIBLE;
                    relatedServicesPanel.setVisibility(show ? View.VISIBLE : View.GONE);
                    return true;
                default:
                    return false;
            }
        });
        popup.show();
    }

    private void cycleBrightness() {
        int current = preferences.readerBrightnessPercent();
        int next = current > 80 ? 80 : current > 60 ? 60 : current > 40 ? 40 : current > 20 ? 20 : 100;
        preferences.setReaderBrightnessPercent(next);
        applyReaderWindowPreferences();
        host.navigate("reader", serviceId);
    }

    private String readerThemeLabel() {
        String theme = preferences.readerTheme();
        if ("sepia".equals(theme)) return local("ورقي", "Sepia", "Σέπια");
        if ("night".equals(theme)) return local("ليلي", "Night", "Νύχτα");
        return local("ثيم النظام", "System theme", "Θέμα συστήματος");
    }

    private void cycleReaderTheme() {
        String current = preferences.readerTheme();
        preferences.setReaderTheme("system".equals(current) ? "sepia" : "sepia".equals(current) ? "night" : "system");
        saveReaderPosition();
        host.navigate("reader", serviceId);
    }

    private void showNoteDialog() {
        EditText input = new EditText(host.activity());
        input.setText(preferences.serviceNote(serviceId));
        input.setMinLines(4);
        input.setGravity(Gravity.TOP | (preferences.isRtl() ? Gravity.RIGHT : Gravity.LEFT));
        input.setHint(local("اكتب ملاحظة شخصية تحفظ على هذا الجهاز فقط", "Write a private note stored only on this device", "Γράψε προσωπικὴ σημείωση"));
        int padding = ui.dp(18);
        LinearLayout wrapper = new LinearLayout(host.activity());
        wrapper.setPadding(padding, ui.dp(8), padding, 0);
        wrapper.addView(input, new LinearLayout.LayoutParams(-1, -2));
        new AlertDialog.Builder(host.activity())
                .setTitle(local("ملاحظة شخصية", "Private note", "Προσωπικὴ σημείωση"))
                .setView(wrapper)
                .setPositiveButton(local("حفظ", "Save", "Ἀποθήκευση"), (dialog, which) -> {
                    preferences.setServiceNote(serviceId, input.getText().toString());
                    Toast.makeText(host.activity(), local("تم حفظ الملاحظة محليًا", "Note saved locally", "Ἡ σημείωση ἀποθηκεύτηκε"), Toast.LENGTH_SHORT).show();
                    host.navigate("reader", serviceId);
                })
                .setNeutralButton(local("حذف", "Delete", "Διαγραφή"), (dialog, which) -> {
                    preferences.setServiceNote(serviceId, "");
                    host.navigate("reader", serviceId);
                })
                .setNegativeButton(local("إلغاء", "Cancel", "Ἀκύρωση"), null)
                .show();
    }

    private void shareCurrentSegment() {
        if (adapter == null || layoutManager == null) return;
        int position = Math.max(0, layoutManager.findFirstVisibleItemPosition());
        String excerpt = adapter.shareTextAt(position);
        if (excerpt.isEmpty()) {
            Toast.makeText(host.activity(), local("لا يوجد مقطع قابل للمشاركة هنا", "No shareable passage is visible", "Δὲν ὑπάρχει κείμενο γιὰ κοινοποίηση"), Toast.LENGTH_SHORT).show();
            return;
        }
        String title = localized(service.optJSONObject("title"), local("نص كنسي", "Orthodox text", "Ὀρθόδοξο κείμενο"));
        String source = data.selectedOfficialSource();
        String footer = "\n\n— " + title + "\n"
                + local("تاريخ البيانات: ", "Data date: ", "Ἡμερομηνία: ") + data.dataDate();
        if (source != null && !source.trim().isEmpty()) {
            footer += "\n" + local("المصدر الموثق: ", "Verified source: ", "Ἐπαληθευμένη πηγή: ") + source;
        }
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.setType("text/plain");
        intent.putExtra(Intent.EXTRA_SUBJECT, title);
        intent.putExtra(Intent.EXTRA_TEXT, excerpt + footer);
        host.activity().startActivity(Intent.createChooser(intent, local("مشاركة النص", "Share text", "Κοινοποίηση κειμένου")));
    }

    private void updateReaderProgress() {
        if (readerProgressBar == null || readerProgressLabel == null || layoutManager == null || adapter == null || adapter.getItemCount() == 0) return;
        int last = layoutManager.findLastVisibleItemPosition();
        int percent = Math.max(0, Math.min(100, Math.round(((last + 1) * 100f) / adapter.getItemCount())));
        readerProgressBar.setProgress(percent);
        readerProgressLabel.setText(percent + "%");
        readerProgressLabel.setContentDescription(local("تقدم القراءة ", "Reading progress ", "Πρόοδος ") + percent + "%");
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
        if (speed <= 0) return local("التمرير التلقائي", "Auto-scroll", "Αὐτόματη κύλιση");
        return local("سرعة التمرير ", "Scroll speed ", "Ταχύτητα κύλισης ") + speed;
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
            badge = local(
                    "قطع اليوم والنصوص الكتابية اجتازت تحقق المصادر والتوقيع",
                    "Daily propers and Scripture passed source and signature verification",
                    "Τὰ ἡμερήσια κείμενα ἐπαληθεύθηκαν"
            );
        } else if (officialStatic) {
            badge = local(
                    "نص عربي كامل مثبت من مصدر مطرانية الأردن الرسمي ومحمي ببصمة",
                    "Complete Arabic text pinned from an official Orthodox Jordan source and hash-protected",
                    "Πλήρες ἀραβικὸ κείμενο ἀπὸ ἐπίσημη πηγή"
            );
        } else if (pinnedStatic) {
            badge = local(
                    "نص ثابت مثبت ببصمة؛ لا تتغير قطعه اليومية إلا بعد التحقق الرسمي",
                    "Pinned fixed text; daily variables change only after official verification",
                    "Σταθερὸ κείμενο μὲ ψηφιακὸ ἀποτύπωμα"
            );
        } else {
            badge = local(
                    "حالة المصدر غير مكتملة؛ لا تُستخدم قطع يومية غير موثقة",
                    "Source state is incomplete; unverified daily text is not inserted",
                    "Ἡ κατάσταση πηγῆς εἶναι ἐλλιπής"
            );
        }
        box.addView(ui.badge(badge, dailyVerified || officialStatic || pinnedStatic),
                ui.margins(-1, -2, 0, notice.isEmpty() ? 0 : 7, 0, 0));

        LocalizedValue title = data.localizedValue(service.optJSONObject("title"), "");
        if (title.translationUnavailable) {
            box.addView(ui.badge(local(
                    "النص الموثق بهذه اللغة غير متوفر بعد — استخدم إظهار الأصل",
                    "Verified text in this language is not available yet — use Show source",
                    "Τὸ ἐπαληθευμένο κείμενο δὲν εἶναι διαθέσιμο — δεῖξε τὸ πρωτότυπο"
            ), false), ui.margins(-1, -2, 0, 5, 0, 0));
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
            box.addView(ui.text(local("المصدر المسجل: ", "Registered source: ", "Καταχωρισμένη πηγή: ") + sourceName,
                    13, ui.colors().primaryText(), true), ui.margins(-1, -2, 0, 8, 0, 0));
        }
        if (!sourceUrl.isEmpty()) {
            final String url = sourceUrl;
            Button openSource = ui.smallButton(local("فتح المصدر الرسمي", "Open official source", "Ἄνοιγμα ἐπίσημης πηγῆς"), false);
            openSource.setOnClickListener(v -> {
                try {
                    host.activity().startActivity(new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url)));
                } catch (Exception error) {
                    Toast.makeText(host.activity(), local("تعذر فتح رابط المصدر.", "The source link could not be opened.", "Δὲν ἄνοιξε ὁ σύνδεσμος."), Toast.LENGTH_LONG).show();
                }
            });
            box.addView(openSource, ui.margins(-1, -2, 0, 8, 0, 0));
        }
        Button allSources = ui.smallButton(local("جميع المصادر والمراجع", "All sources and references", "Ὅλες οἱ πηγές"), false);
        allSources.setOnClickListener(v -> host.navigate("sources", null));
        box.addView(allSources, ui.margins(-1, -2, 0, 5, 0, 0));
        return box;
    }

    private LinearLayout relatedServicesBox() {
        JSONArray related = service.optJSONArray("related_services");
        if (related == null || related.length() == 0) return null;
        LinearLayout box = ui.card();
        box.addView(ui.text(local("صلوات مرتبطة بهذه الخدمة", "Prayers related to this service", "Σχετικὲς προσευχές"),
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
        addJump(jumps, local("البروكيمنن", "Prokeimenon", "Προκείμενον"),
                adapter.findPosition("البروكيمنن", "Prokeimenon", "Προκείμενον"));
        addJump(jumps, local("الرسالة", "Epistle", "Ἀπόστολος"),
                adapter.findPosition("الرسالة", "Epistle", "Ἀπόστολος"));
        addJump(jumps, local("الإنجيل", "Gospel", "Εὐαγγέλιον"),
                adapter.findPosition("الإنجيل", "Gospel", "Εὐαγγέλιον"));
        box.addView(jumps);

        LinearLayout sectionNav = ui.row();
        Button previous = ui.smallButton(local("القسم السابق", "Previous section", "Προηγούμενη ἐνότητα"), false);
        previous.setOnClickListener(v -> moveSection(false));
        sectionNav.addView(previous, ui.weight(44));
        Button next = ui.smallButton(local("القسم التالي", "Next section", "Ἑπόμενη ἐνότητα"), false);
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
            Toast.makeText(host.activity(), local(
                    "لم يتم العثور على هذا الموضع",
                    "Section not found",
                    "Ἡ ἐνότητα δὲν βρέθηκε"
            ), Toast.LENGTH_SHORT).show();
            return;
        }
        if (controlsExpanded) {
            setControlsExpanded(false, false);
            recycler.post(() -> performSectionJump(position));
        } else {
            performSectionJump(position);
        }
    }

    private void performSectionJump(int position) {
        if (layoutManager == null || recycler == null) return;
        layoutManager.scrollToPositionWithOffset(position, 0);
        recycler.post(this::saveReaderPosition);
    }

    private boolean isLiturgy() {
        return "divine_liturgy".equals(serviceId) || "next_sunday_full_liturgy".equals(serviceId);
    }

    @Override
    public void onHidden() {
        stopAutoScroll(false);
        saveReaderPosition();
        host.activity().getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        WindowManager.LayoutParams attributes = host.activity().getWindow().getAttributes();
        attributes.screenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;
        host.activity().getWindow().setAttributes(attributes);
    }
}
