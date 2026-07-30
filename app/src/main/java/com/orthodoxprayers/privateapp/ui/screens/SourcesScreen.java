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
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_sources_and_references_1a2c2926), true);
        String policy = localized(data.sourceRegistry().optJSONObject("policy"), "");
        if (!policy.isEmpty()) add(page.root, ui.infoBadge(policy), 10, 10);

        JSONObject healthSummary = data.sourceHealth().optJSONObject("summary");
        if (healthSummary != null) {
            String monitor = local(com.orthodoxprayers.privateapp.R.string.ui_monitored_connectors_9c15d2f8)
                    + healthSummary.optInt("connector_count", 0)
                    + local(com.orthodoxprayers.privateapp.R.string.ui_usable_111b1469)
                    + healthSummary.optInt("usable_connector_count", 0);
            add(page.root, ui.badge(monitor, healthSummary.optInt("usable_connector_count", 0) > 0), 0, 9);
        }

        JSONArray sources = data.registeredSources();
        for (int i = 0; i < sources.length(); i++) {
            JSONObject source = sources.optJSONObject(i);
            if (source != null) add(page.root, sourceCard(source), 2, 9);
        }
        if (sources.length() == 0) {
            add(page.root, ui.badge(local(com.orthodoxprayers.privateapp.R.string.ui_the_packaged_source_registry_could_not_be_loaded_fdbc55f4), false), 18, 18);
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
            String healthText = local(com.orthodoxprayers.privateapp.R.string.ui_monitor_status_070900f8)
                    + health.optString("status", "unknown")
                    + local(com.orthodoxprayers.privateapp.R.string.ui_confidence_e698f632)
                    + Math.round(health.optDouble("confidence", 0.0) * 100) + "%";
            card.addView(ui.badge(healthText, "current".equals(health.optString("status")) || "available".equals(health.optString("status"))),
                    ui.margins(-1, -2, 0, 5, 0, 4));
        }

        String languages = join(source.optJSONArray("languages"));
        String rights = source.optString("rights", "").trim();
        String verified = source.optString("last_verified", "").trim();
        String details = local(com.orthodoxprayers.privateapp.R.string.ui_id_8ac50ce2) + id;
        int tier = source.optInt("authority_tier", 0);
        if (tier > 0) details += "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_authority_tier_e909156f) + tier;
        int connectorCount = source.optInt("connector_count", 0);
        if (connectorCount > 0) details += "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_active_connectors_34b93171) + connectorCount;
        if (!languages.isEmpty()) details += "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_languages_96622490) + languages;
        if (!verified.isEmpty()) details += "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_last_recorded_verification_88c33b18) + verified;
        if (!rights.isEmpty()) details += "\n" + local(com.orthodoxprayers.privateapp.R.string.ui_rights_license_9068c5b7) + rights;
        card.addView(ui.text(details, 12, ui.colors().secondaryText(), false),
                ui.margins(-1, -2, 0, 5, 0, 0));

        String hash = source.optString("content_sha256", "").trim();
        if (!hash.isEmpty()) {
            String shortHash = hash.length() <= 18 ? hash : hash.substring(0, 18) + "…";
            card.addView(ui.text(local(com.orthodoxprayers.privateapp.R.string.ui_content_hash_6fb5464c) + shortHash,
                    11, ui.colors().secondaryText(), false));
        }

        String url = source.optString("url", "").trim();
        if (!url.isEmpty()) {
            Button open = ui.button(local(com.orthodoxprayers.privateapp.R.string.ui_open_source_1e0710bf), false);
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
            Toast.makeText(host.activity(), local(com.orthodoxprayers.privateapp.R.string.ui_this_link_could_not_be_opened_on_the_device_9aa42df0), Toast.LENGTH_LONG).show();
        }
    }
}
