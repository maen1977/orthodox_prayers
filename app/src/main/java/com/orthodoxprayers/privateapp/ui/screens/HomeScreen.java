package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.ThemePalette;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class HomeScreen extends BaseScreen {
    // R14_HOME_COMPACT: duplicate home cards hidden; internal routes remain available.
    // R15_THEME_PALETTE_IMPORT: Sunday card colors use the shared palette with an explicit Java import.
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
        addQuickAccess(page.root);
        addUpcoming(page.root);
        return page.scroll;
    }

    private void addUpdateBanner(LinearLayout root) {
        if (data.isRefreshing() && !data.hasUsableCurrentData()) {
            add(root, ui.infoBadge(data.userFacingRefreshStatus()), 10, 2);
            return;
        }
        if (!data.hasUsableCurrentData()) {
            add(root, ui.badge(data.userFacingRefreshStatus(), false), 10, 2);
        }
    }

    private void addEmptyState(LinearLayout root) {
        LinearLayout card = ui.card();
        String title = data.isRefreshing()
                ? local("جارٍ تحميل بيانات اليوم…", "Loading today’s data…", "Φόρτωση σημερινῶν δεδομένων…")
                : local("لا توجد بيانات يومية سليمة قابلة للعرض", "No valid daily data is available", "Δὲν ὑπάρχουν ἔγκυρα σημερινὰ δεδομένα");
        card.addView(centered(title, 19, ui.colors().primaryText(), true));
        String detail = data.isRefreshing()
                ? local("سيتم تحديث الشاشة تلقائيًا فور اكتمال التنزيل وفحص البيانات.",
                        "The screen will update automatically after download and data validation.",
                        "Ἡ ὀθόνη θὰ ἐνημερωθεῖ αὐτόματα.")
                : local("سيحاول التطبيق التحديث تلقائيًا. يمكنك أيضًا إعادة المحاولة من الزر أدناه.",
                        "The app will retry automatically. You can also retry below.",
                        "Ἡ ἐφαρμογὴ θὰ προσπαθήσει ξανά αὐτόματα.");
        card.addView(centered(detail, 14, ui.colors().secondaryText(), false), ui.margins(-1, -2, 0, 8, 0, 8));
        if (!data.isRefreshing()) {
            Button retry = ui.button(local("إعادة محاولة التحديث", "Retry update", "Νέα προσπάθεια"), true);
            retry.setOnClickListener(v -> host.refreshData());
            card.addView(retry, ui.margins(-1, -2, 0, 6, 0, 0));
        }
        add(root, card, 12, 12);
    }

    private void addDateCard(LinearLayout root) {
        JSONObject today = data.today();
        LinearLayout card = ui.card();
        String dateValue = localized(today.optJSONObject("date_label"), data.dataDate());
        TextView date = centered(dateValue, 22, ui.colors().primaryText(), true);
        card.addView(date);

        String calendarValue = localized(today.optJSONObject("calendar_label"), "");
        if (!calendarValue.isEmpty()) {
            TextView calendar = centered(calendarValue, 14, ui.colors().secondaryText(), false);
            card.addView(calendar, ui.margins(-1, -2, 0, 4, 0, 0));
        }

        String fastingValue = fastingValue(today);
        TextView fast = centered(fastingValue, 18, ui.colors().accentText(), true);
        card.addView(fast, ui.margins(-1, -2, 0, 8, 0, 0));

        if (!data.isTodayCurrent()) {
            String staleText = local(
                    "تظهر آخر نسخة موثوقة بتاريخ " + data.dataDate() + "، ويجري طلب بيانات اليوم تلقائيًا.",
                    "Showing the last trusted copy dated " + data.dataDate() + "; today’s data is requested automatically.",
                    "Προβάλλεται ἡ τελευταία ἔγκυρη ἔκδοση " + data.dataDate() + "."
            );
            card.addView(ui.badge(staleText, false), ui.margins(-1, -2, 0, 10, 0, 0));
        }
        add(root, card, 12, 10);
    }

    private String fastingValue(JSONObject today) {
        String value = localized(today.optJSONObject("fast"), "");
        if (!value.isEmpty()) return value;
        JSONObject fasting = today.optJSONObject("fasting");
        if (fasting != null) value = localized(fasting.optJSONObject("title"), "");
        return value.isEmpty() ? local("غير متوفر", "Unavailable", "Μὴ διαθέσιμο") : value;
    }

    private void addQuickAccess(LinearLayout root) {
        root.addView(ui.sectionTitle(local("الوصول السريع", "Quick access", "Γρήγορη πρόσβαση")));
        Button liturgy = ui.button("⛪\n" + local(
                "قداس اليوم الكامل — من الاستعداد إلى الختام",
                "Full Liturgy Today — preparation to dismissal",
                "Πλήρης σημερινὴ Θεία Λειτουργία — ἀπὸ τὴν προετοιμασία ἕως τὴν ἀπόλυση"
        ), true);
        liturgy.setTextSize(17 * preferences.fontScale());
        liturgy.setOnClickListener(v -> host.navigate("reader", "divine_liturgy"));
        add(root, liturgy, 2, 8);

        LinearLayout first = ui.row();
        addShortcut(first, "📖", local("القراءات اليومية", "Daily readings", "Ἡμερήσια ἀναγνώσματα"), "readings", null);
        addShortcut(first, "🙏", local("الصلوات اليومية", "Daily prayers", "Καθημερινὲς προσευχές"), "prayers", null);
        add(root, first, 0, 0);

        LinearLayout second = ui.row();
        addShortcut(second, "📅", local("التقويم والصيام", "Calendar and fasting", "Ἡμερολόγιο καὶ νηστεία"), "calendar", null);
        addShortcut(second, "🗓", local("الأيام السبعة القادمة", "Next seven days", "Ἑπόμενες ἑπτὰ ἡμέρες"), "upcoming", null);
        add(root, second, 0, 0);

        LinearLayout third = ui.row();
        addShortcut(third, "▶", local("الكنائس والبث المباشر", "Churches and live services", "Ναοὶ καὶ ζωντανὲς μεταδόσεις"), "churches", null);
        addShortcut(third, "🔎", local("البحث", "Search", "Ἀναζήτηση"), "search", null);
        add(root, third, 0, 0);

        LinearLayout fourth = ui.row();
        addShortcut(fourth, "⭐", local("المفضلة", "Favorites", "Ἀγαπημένα"), "favorites", null);
        addShortcut(fourth, "🕘", local("آخر قراءة", "Reading history", "Ἱστορικὸ ἀναγνώσεως"), "history", null);
        add(root, fourth, 0, 0);

        LinearLayout fifth = ui.row();
        addShortcut(fifth, "🌐", local("اللغات", "Languages", "Γλῶσσες"), "language_packs", null);
        addShortcut(fifth, "⚙", local("الإعدادات", "Settings", "Ρυθμίσεις"), "settings", null);
        add(root, fifth, 0, 10);

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

    private void addShortcut(LinearLayout row, String icon, String title, String screen, String argument) {
        Button button = ui.button(icon + "\n" + title, false);
        button.setOnClickListener(v -> host.navigate(screen, argument));
        row.addView(button, ui.weight(76));
    }

    private void addUpcoming(LinearLayout root) {
        JSONArray upcoming = data.today().optJSONArray("upcoming");
        if (upcoming == null || upcoming.length() == 0) return;

        root.addView(ui.sectionTitle(local(
                "جدول الصيام للأيام السبعة",
                "Seven-day fasting table",
                "Πίνακας νηστείας ἑπτὰ ἡμερῶν"
        )));
        LinearLayout table = ui.card();

        LinearLayout header = ui.row();
        header.setPadding(ui.dp(8), ui.dp(4), ui.dp(8), ui.dp(6));
        TextView dayHeader = ui.text(
                local("اليوم والمناسبة", "Day and commemoration", "Ἡμέρα καὶ μνήμη"),
                13,
                ui.colors().primaryText(),
                true
        );
        TextView fastingHeader = ui.text(
                local("الصيام", "Fasting", "Νηστεία"),
                13,
                ui.colors().accentText(),
                true
        );
        fastingHeader.setGravity(android.view.Gravity.CENTER);
        header.addView(dayHeader, new LinearLayout.LayoutParams(0, -2, 2f));
        header.addView(fastingHeader, new LinearLayout.LayoutParams(0, -2, 1f));
        table.addView(header);

        int dayCount = Math.min(7, upcoming.length());
        for (int i = 0; i < dayCount; i++) {
            JSONObject item = upcoming.optJSONObject(i);
            if (item == null) continue;
            String date = item.optString("date", "");
            String day = localized(item.optJSONObject("day"), date);
            String feast = localized(item.optJSONObject("feast"), localized(item.optJSONObject("note"), ""));
            String status = localized(item.optJSONObject("status"), localized(item.optJSONObject("fast"), ""));
            JSONObject fasting = item.optJSONObject("fasting");
            if (status.isEmpty() && fasting != null) {
                status = localized(fasting.optJSONObject("title"), "");
            }
            if (status.isEmpty()) {
                status = local("غير متوفر", "Unavailable", "Μὴ διαθέσιμο");
            }

            LinearLayout row = ui.row();
            row.setPadding(ui.dp(8), ui.dp(7), ui.dp(8), ui.dp(7));
            row.setClickable(!date.isEmpty());
            row.setFocusable(!date.isEmpty());
            String dayAndFeast = "📅  " + day + (feast.isEmpty() ? "" : "\n" + feast);
            TextView dayView = ui.text(dayAndFeast, 13, ui.colors().secondaryText(), false);
            dayView.setMaxLines(3);
            TextView statusView = ui.text(status, 13, ui.colors().accentText(), true);
            statusView.setGravity(android.view.Gravity.CENTER);
            statusView.setMaxLines(3);
            row.addView(dayView, new LinearLayout.LayoutParams(0, -2, 2f));
            row.addView(statusView, new LinearLayout.LayoutParams(0, -2, 1f));
            row.setContentDescription(day + ". " + status + (feast.isEmpty() ? "" : ". " + feast));
            if (!date.isEmpty()) {
                row.setOnClickListener(v -> host.navigate("calendar_day", date));
            }
            table.addView(row);

            if (i + 1 < dayCount) {
                View divider = new View(host.activity());
                divider.setBackgroundColor(ui.colors().secondaryText());
                divider.setAlpha(0.16f);
                table.addView(divider, new LinearLayout.LayoutParams(-1, ui.dp(1)));
            }
        }
        add(root, table, 0, 6);

        Button details = ui.smallButton(local("عرض تفاصيل الأيام السبعة", "Show seven-day details", "Λεπτομέρειες 7 ἡμερῶν"), false);
        details.setOnClickListener(v -> host.navigate("upcoming", null));
        add(root, details, 0, 12);
    }

    private void addNextSunday(LinearLayout root) {
        JSONObject sunday = data.today().optJSONObject("next_sunday");
        if (sunday == null || sunday.length() == 0) return;
        root.addView(ui.sectionTitle(local("الأحد القادم", "Next Sunday", "Ἡ ἐπόμενη Κυριακή")));
        LinearLayout card = ui.card(ThemePalette.NAVY, ThemePalette.GOLD, 14);
        card.setClickable(true);
        card.setFocusable(true);
        card.setOnClickListener(v -> host.navigate("reader", sunday.optString("service_id", "next_sunday_full_liturgy")));
        TextView day = centered("☦  " + localized(sunday.optJSONObject("day"), sunday.optString("date_iso", "")), 18, ThemePalette.GOLD, true);
        card.addView(day);
        card.addView(centered(localized(sunday.optJSONObject("feast"), ""), 14, android.graphics.Color.WHITE, true));
        card.addView(centered(localized(sunday.optJSONObject("fast"), ""), 13, ThemePalette.GOLD, true));
        TextView open = centered(local("اضغط لفتح خدمة الأحد كاملة", "Open the full Sunday service", "Ἄνοιγμα πλήρους ἀκολουθίας"), 12, ThemePalette.GOLD, true);
        card.addView(open, ui.margins(-1, -2, 0, 6, 0, 0));
        card.setContentDescription(day.getText() + ". " + open.getText());
        add(root, card, 0, 16);
    }
}
