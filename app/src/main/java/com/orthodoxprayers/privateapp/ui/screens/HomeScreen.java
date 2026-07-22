package com.orthodoxprayers.privateapp.ui.screens;

import android.graphics.Color;
import android.view.View;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.ThemePalette;

// R15_THEME_PALETTE_IMPORT: compatibility marker retained for release-pipeline verification.
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

public final class HomeScreen extends BaseScreen {
    public HomeScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(
                localized(data.library().optJSONObject("app_name"), local("الصلوات الكنسية", "Church Prayers", "Ἐκκλησιαστικὲς Προσευχές")),
                false
        );
        addUpdateBanner(page.root);
        if (!data.hasDisplayableData()) {
            addEmptyState(page.root);
            addQuickAccess(page.root);
            return page.scroll;
        }
        addDateCard(page.root);
        addContinueReading(page.root);
        addQuickAccess(page.root);
        addUpcoming(page.root);
        addNextSunday(page.root);
        return page.scroll;
    }

    private void addUpdateBanner(LinearLayout root) {
        if (data.isRefreshing() && !data.hasUsableCurrentData()) {
            add(root, ui.infoBadge(data.userFacingRefreshStatus()), 12, 2);
            return;
        }
        if (!data.hasUsableCurrentData()) add(root, ui.badge(data.userFacingRefreshStatus(), false), 12, 2);
    }

    private void addEmptyState(LinearLayout root) {
        LinearLayout card = ui.elevatedCard();
        String title = data.isRefreshing()
                ? local("جارٍ تحميل بيانات اليوم…", "Loading today’s data…", "Φόρτωση σημερινῶν δεδομένων…")
                : local("لا توجد بيانات يومية سليمة قابلة للعرض", "No valid daily data is available", "Δὲν ὑπάρχουν ἔγκυρα σημερινὰ δεδομένα");
        card.addView(centered(title, 19, ui.colors().primaryText(), true));
        String detail = data.isRefreshing()
                ? local("ستتحدث الشاشة تلقائيًا بعد اكتمال التنزيل والتحقق.", "The screen will update automatically after download and validation.", "Ἡ ὀθόνη θὰ ἐνημερωθεῖ αὐτόματα.")
                : local("سيحاول التطبيق التحديث تلقائيًا، ويمكنك إعادة المحاولة الآن.", "The app will retry automatically, or you can retry now.", "Ἡ ἐφαρμογὴ θὰ προσπαθήσει ξανά.");
        card.addView(centered(detail, 14, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 10, 0, 8));
        if (!data.isRefreshing()) {
            Button retry = ui.button(local("إعادة محاولة التحديث", "Retry update", "Νέα προσπάθεια"), true);
            retry.setOnClickListener(v -> host.refreshData());
            card.addView(retry, ui.margins(-1, -2, 0, 8, 0, 0));
        }
        add(root, card, 16, 12);
    }

    private void addDateCard(LinearLayout root) {
        JSONObject today = data.today();
        LinearLayout card = ui.elevatedCard();
        card.setBackground(ui.gradient(ThemePalette.NAVY, ThemePalette.NAVY_2, 0, 20));
        card.setPadding(ui.dp(20), ui.dp(20), ui.dp(20), ui.dp(20));

        String dateValue = localized(today.optJSONObject("date_label"), data.dataDate());
        TextView date = centered(dateValue, 23, Color.WHITE, true);
        card.addView(date);

        String calendarValue = localized(today.optJSONObject("calendar_label"), "");
        if (!calendarValue.isEmpty()) {
            card.addView(centered(calendarValue, 13, Color.rgb(220, 228, 238), false), ui.margins(-1, -2, 0, 5, 0, 0));
        }

        String fastingValue = fastingValue(today);
        card.addView(centered(fastingValue, 18, ThemePalette.GOLD, true), ui.margins(-1, -2, 0, 11, 0, 0));

        if (!data.isTodayCurrent()) {
            String staleText = local(
                    "تظهر آخر نسخة موثوقة بتاريخ " + data.dataDate() + "، ويطلب التطبيق بيانات اليوم تلقائيًا.",
                    "Showing the last trusted copy dated " + data.dataDate() + "; today’s data is requested automatically.",
                    "Προβάλλεται ἡ τελευταία ἔγκυρη ἔκδοση " + data.dataDate() + "."
            );
            TextView stale = ui.text(staleText, 12, Color.WHITE, true);
            stale.setGravity(android.view.Gravity.CENTER);
            stale.setPadding(ui.dp(10), ui.dp(8), ui.dp(10), ui.dp(8));
            stale.setBackground(ui.round(Color.rgb(26, 68, 104), Color.TRANSPARENT, 12));
            card.addView(stale, ui.margins(-1, -2, 0, 12, 0, 0));
        }
        add(root, card, 16, 12);
    }

    private String fastingValue(JSONObject today) {
        String value = localized(today.optJSONObject("fast"), "");
        if (!value.isEmpty()) return value;
        JSONObject fasting = today.optJSONObject("fasting");
        if (fasting != null) value = localized(fasting.optJSONObject("title"), "");
        return value.isEmpty() ? local("غير متوفر", "Unavailable", "Μὴ διαθέσιμο") : value;
    }

    private void addContinueReading(LinearLayout root) {
        List<String> recent = preferences.recentServices();
        if (recent.isEmpty()) return;
        JSONObject service = data.findService(recent.get(0));
        if (service == null) return;
        String id = service.optString("id", "");
        if (id.isEmpty()) return;

        root.addView(ui.sectionTitle(local("متابعة القراءة", "Continue reading", "Συνέχεια ἀναγνώσεως")));
        LinearLayout card = ui.card();
        card.setClickable(true);
        card.setFocusable(true);
        card.setBackground(ui.ripple(ui.colors().card(), ui.colors().border(), 18, ui.colors().ripple()));
        String title = localized(service.optJSONObject("title"), local("النص الأخير", "Last text", "Τελευταῖο κείμενο"));
        card.addView(ui.text(title, 17, ui.colors().primaryText(), true));
        int position = preferences.readerPosition(id);
        int count = service.optJSONArray("segments") == null ? 0 : service.optJSONArray("segments").length();
        int percent = count <= 0 ? 0 : Math.max(0, Math.min(100, Math.round((position * 100f) / count)));
        card.addView(ui.text(local("موضع القراءة المحفوظ: ", "Saved reading position: ", "Αποθηκευμένη θέση: ") + percent + "%",
                13, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 6, 0, 0));
        card.setOnClickListener(v -> host.navigate("reader", id));
        card.setContentDescription(local("متابعة ", "Continue ", "Συνέχεια ") + title);
        add(root, card, 0, 10);
    }

    private void addQuickAccess(LinearLayout root) {
        root.addView(ui.sectionTitle(local("الوصول السريع", "Quick access", "Γρήγορη πρόσβαση")));
        Button liturgy = ui.shortcutButton(local("القداس الإلهي الكامل", "Full Divine Liturgy", "Πλήρης Θεία Λειτουργία"), R.drawable.ic_action_liturgy, true);
        liturgy.setTextSize(16 * preferences.fontScale());
        liturgy.setOnClickListener(v -> host.navigate("reader", "divine_liturgy"));
        add(root, liturgy, 2, 8);

        LinearLayout first = ui.row();
        addShortcut(first, R.drawable.ic_action_readings, local("القراءات", "Readings", "Ἀναγνώσματα"), "readings", null);
        addShortcut(first, R.drawable.ic_action_prayers, local("الصلوات", "Prayers", "Προσευχές"), "prayers", null);
        addShortcut(first, R.drawable.ic_action_history, local("آخر قراءة", "History", "Ἱστορικό"), "history", null);
        add(root, first, 0, 0);

        LinearLayout second = ui.row();
        addShortcut(second, R.drawable.ic_action_calendar, local("الأيام القادمة", "Upcoming", "Ἐπόμενες"), "upcoming", null);
        addShortcut(second, R.drawable.ic_action_live, local("البث المباشر", "Live services", "Ζωντανὰ"), "churches", null);
        addShortcut(second, R.drawable.ic_action_settings, local("الإعدادات", "Settings", "Ρυθμίσεις"), "settings", null);
        add(root, second, 0, 12);

        if (!preferences.pinnedServices().isEmpty()) {
            root.addView(ui.sectionTitle(local("النصوص المثبتة", "Pinned texts", "Καρφιτσωμένα κείμενα")));
            int shown = 0;
            for (String id : preferences.pinnedServices()) {
                JSONObject service = data.findService(id);
                if (service != null) {
                    add(root, serviceCard(service), 2, 7);
                    if (++shown >= 3) break;
                }
            }
        }
    }

    private void addShortcut(LinearLayout row, int icon, String title, String screen, String argument) {
        Button button = ui.shortcutButton(title, icon, false);
        button.setOnClickListener(v -> host.navigate(screen, argument));
        row.addView(button, ui.weight(88));
    }

    private void addUpcoming(LinearLayout root) {
        JSONArray upcoming = data.today().optJSONArray("upcoming");
        if (upcoming == null || upcoming.length() == 0) return;
        root.addView(ui.sectionTitle(local("الأيام القادمة", "Upcoming days", "Ἐπόμενες ἡμέρες")));
        HorizontalScrollView scroller = new HorizontalScrollView(host.activity());
        scroller.setHorizontalScrollBarEnabled(false);
        LinearLayout strip = ui.row();
        scroller.addView(strip, new HorizontalScrollView.LayoutParams(-2, -2));
        for (int i = 0; i < upcoming.length(); i++) {
            JSONObject item = upcoming.optJSONObject(i);
            if (item != null) strip.addView(upcomingCard(item), ui.margins(ui.dp(170), -2, 4, 2, 4, 2));
        }
        add(root, scroller, 0, 5);
        Button details = ui.smallButton(local("عرض تفاصيل الأيام السبعة", "Show seven-day details", "Λεπτομέρειες 7 ἡμερῶν"), false);
        details.setOnClickListener(v -> host.navigate("upcoming", null));
        add(root, details, 0, 10);
    }

    private LinearLayout upcomingCard(JSONObject item) {
        LinearLayout card = ui.card();
        card.setPadding(ui.dp(12), ui.dp(12), ui.dp(12), ui.dp(12));
        TextView day = centered(localized(item.optJSONObject("day"), item.optString("date", "")), 13, ui.colors().primaryText(), true);
        day.setMaxLines(2);
        card.addView(day);
        TextView status = centered(localized(item.optJSONObject("status"), ""), 12, ui.colors().accentText(), true);
        status.setMaxLines(3);
        card.addView(status, ui.margins(-1, -2, 0, 7, 0, 0));
        JSONObject fasting = item.optJSONObject("fasting");
        String foodRules = addCompactFastingItems(card, fasting);
        TextView feast = centered(localized(item.optJSONObject("feast"), localized(item.optJSONObject("note"), "")), 11, ui.colors().secondaryText(), false);
        feast.setMaxLines(3);
        card.addView(feast);
        card.setContentDescription(day.getText() + ". " + status.getText() + (foodRules.isEmpty() ? "" : ". " + foodRules) + ". " + feast.getText());
        return card;
    }

    private void addNextSunday(LinearLayout root) {
        JSONObject sunday = data.today().optJSONObject("next_sunday");
        if (sunday == null || sunday.length() == 0) return;
        root.addView(ui.sectionTitle(local("الأحد القادم", "Next Sunday", "Ἡ ἐπόμενη Κυριακή")));
        LinearLayout card = ui.card(ThemePalette.NAVY, Color.TRANSPARENT, 20);
        card.setElevation(ui.dp(2));
        card.setClickable(true);
        card.setFocusable(true);
        card.setBackground(ui.ripple(ThemePalette.NAVY, Color.TRANSPARENT, 20, 0x33FFFFFF));
        card.setOnClickListener(v -> host.navigate("reader", sunday.optString("service_id", "next_sunday_full_liturgy")));
        TextView day = centered(localized(sunday.optJSONObject("day"), sunday.optString("date_iso", "")), 18, ThemePalette.GOLD, true);
        card.addView(day);
        card.addView(centered(localized(sunday.optJSONObject("feast"), ""), 14, Color.WHITE, true), ui.margins(-1, -2, 0, 5, 0, 0));
        card.addView(centered(localized(sunday.optJSONObject("fast"), ""), 13, ThemePalette.GOLD, true), ui.margins(-1, -2, 0, 4, 0, 0));
        TextView open = centered(local("فتح خدمة الأحد كاملة", "Open the full Sunday service", "Ἄνοιγμα πλήρους ἀκολουθίας"), 12, Color.WHITE, true);
        card.addView(open, ui.margins(-1, -2, 0, 10, 0, 0));
        card.setContentDescription(day.getText() + ". " + open.getText());
        add(root, card, 0, 20);
    }
}
