package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Intent;
import android.net.Uri;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONArray;
import org.json.JSONObject;

public final class SourcesScreen extends BaseScreen {
    public SourcesScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local("المصادر والمراجع", "Sources and references", "Πηγὲς καὶ παραπομπές"), true);
        String policy = localized(data.sourceRegistry().optJSONObject("policy"), "");
        if (!policy.isEmpty()) add(page.root, ui.infoBadge(policy), 10, 10);

        JSONObject healthSummary = data.sourceHealth().optJSONObject("summary");
        if (healthSummary != null) {
            String monitor = local("موصلات الرصد: ", "Monitored connectors: ", "Παρακολουθούμενες συνδέσεις: ")
                    + healthSummary.optInt("connector_count", 0)
                    + local("، القابلة للاستخدام: ", ", usable: ", ", διαθέσιμες: ")
                    + healthSummary.optInt("usable_connector_count", 0);
            add(page.root, ui.badge(monitor, healthSummary.optInt("usable_connector_count", 0) > 0), 0, 9);
        }

        JSONArray sources = data.registeredSources();
        for (int i = 0; i < sources.length(); i++) {
            JSONObject source = sources.optJSONObject(i);
            if (source != null) add(page.root, sourceCard(source), 2, 9);
        }
        if (sources.length() == 0) {
            add(page.root, ui.badge(local(
                    "تعذر تحميل سجل المصادر من حزمة التطبيق.",
                    "The packaged source registry could not be loaded.",
                    "Δὲν φορτώθηκε τὸ μητρῷο πηγῶν."
            ), false), 18, 18);
        }
        return page.scroll;
    }

    private LinearLayout sourceCard(JSONObject source) {
        LinearLayout card = ui.card();
        String id = source.optString("id", "");
        String name = localized(source.optJSONObject("name"), id);
        TextView heading = ui.text((source.optBoolean("official", false) ? "✓ " : "• ") + name,
                17, ui.colors().primaryText(), true);
        card.addView(heading);

        String use = localized(source.optJSONObject("used_for"), "");
        if (!use.isEmpty()) card.addView(ui.text(use, 13, ui.colors().secondaryText(), false),
                ui.margins(-1, -2, 0, 5, 0, 0));

        JSONObject health = data.sourceHealthById(id);
        if (health != null) {
            String healthText = local("حالة الرصد: ", "Monitor status: ", "Κατάσταση ἐλέγχου: ")
                    + health.optString("status", "unknown")
                    + local(" — الثقة: ", " — confidence: ", " — βεβαιότητα: ")
                    + Math.round(health.optDouble("confidence", 0.0) * 100) + "%";
            card.addView(ui.badge(healthText, "current".equals(health.optString("status")) || "available".equals(health.optString("status"))),
                    ui.margins(-1, -2, 0, 5, 0, 4));
        }

        String languages = join(source.optJSONArray("languages"));
        String rights = source.optString("rights", "").trim();
        String verified = source.optString("last_verified", "").trim();
        String details = local("المعرّف: ", "ID: ", "ID: ") + id;
        int tier = source.optInt("authority_tier", 0);
        if (tier > 0) details += "\n" + local("درجة السلطة: ", "Authority tier: ", "Βαθμίδα ἀρχῆς: ") + tier;
        int connectorCount = source.optInt("connector_count", 0);
        if (connectorCount > 0) details += "\n" + local("الموصلات النشطة: ", "Active connectors: ", "Ἐνεργὲς συνδέσεις: ") + connectorCount;
        if (!languages.isEmpty()) details += "\n" + local("اللغات: ", "Languages: ", "Γλῶσσες: ") + languages;
        if (!verified.isEmpty()) details += "\n" + local("آخر تحقق مسجل: ", "Last recorded verification: ", "Τελευταῖος ἔλεγχος: ") + verified;
        if (!rights.isEmpty()) details += "\n" + local("الحقوق/الترخيص: ", "Rights/license: ", "Δικαιώματα: ") + rights;
        card.addView(ui.text(details, 12, ui.colors().secondaryText(), false),
                ui.margins(-1, -2, 0, 5, 0, 0));

        String hash = source.optString("content_sha256", "").trim();
        if (!hash.isEmpty()) {
            String shortHash = hash.length() <= 18 ? hash : hash.substring(0, 18) + "…";
            card.addView(ui.text(local("بصمة النص: ", "Content hash: ", "Ἀποτύπωμα: ") + shortHash,
                    11, ui.colors().secondaryText(), false));
        }

        String url = source.optString("url", "").trim();
        if (!url.isEmpty()) {
            Button open = ui.button(local("فتح المصدر الرسمي", "Open source", "Ἄνοιγμα πηγῆς"), false);
            open.setOnClickListener(v -> openUrl(url));
            card.addView(open, ui.margins(-1, -2, 0, 8, 0, 0));
        }
        return card;
    }

    private String join(JSONArray values) {
        if (values == null) return "";
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < values.length(); i++) {
            String value = values.optString(i, "").trim();
            if (value.isEmpty()) continue;
            if (out.length() > 0) out.append(", ");
            out.append(value);
        }
        return out.toString();
    }

    private void openUrl(String url) {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            host.activity().startActivity(intent);
        } catch (Exception error) {
            Toast.makeText(host.activity(), local(
                    "تعذر فتح هذا الرابط على الجهاز.",
                    "This link could not be opened on the device.",
                    "Δὲν ἄνοιξε ὁ σύνδεσμος."
            ), Toast.LENGTH_LONG).show();
        }
    }
}
