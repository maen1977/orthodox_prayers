package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

public final class LanguagePacksScreen extends BaseScreen {
    public LanguagePacksScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_active_languages_79779885), true);
        add(page.root, ui.infoBadge(local(com.orthodoxprayers.privateapp.R.string.ui_base_texts_for_all_three_languages_are_embedded__06372176)), 10, 10);
        addPack(page.root, "ar", local(com.orthodoxprayers.privateapp.R.string.ui_language_arabic_name));
        addPack(page.root, "en", local(com.orthodoxprayers.privateapp.R.string.ui_language_english_name));
        addPack(page.root, "el", local(com.orthodoxprayers.privateapp.R.string.ui_language_greek_name));
        return page.scroll;
    }

    private void addPack(LinearLayout root, String language, String title) {
        LinearLayout card = ui.card();
        TextView heading = ui.text(
                title + " — " + data.religiousCompleteServiceCount(language)
                        + "/" + data.religiousRequiredServiceCount(),
                18,
                ui.colors().primaryText(),
                true
        );
        card.addView(heading);
        boolean enabled = preferences.offlineLanguageEnabled(language);
        boolean selected = language.equals(preferences.effectiveLanguage());
        Button toggle = ui.button(selected
                ? local(com.orthodoxprayers.privateapp.R.string.ui_currently_selected_14c25dc4)
                : enabled
                    ? local(com.orthodoxprayers.privateapp.R.string.ui_hide_from_language_selector_47d8e927)
                    : local(com.orthodoxprayers.privateapp.R.string.ui_show_in_language_selector_575c5fa6), enabled);
        toggle.setEnabled(!selected);
        toggle.setAlpha(selected ? 0.7f : 1f);
        toggle.setOnClickListener(v -> {
            preferences.setOfflineLanguageEnabled(language, !enabled);
            host.navigate("language_packs", null);
        });
        card.addView(toggle, ui.margins(-1, -2, 0, 8, 0, 0));
        add(root, card, 2, 8);
    }
}
