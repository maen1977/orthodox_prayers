package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.util.List;

public final class HistoryScreen extends BaseScreen {
    public HistoryScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_reading_history_6bdb8e55), true);
        List<String> recent = preferences.recentServices();
        if (recent.isEmpty()) {
            TextView empty = centered(local(com.orthodoxprayers.privateapp.R.string.ui_your_20_most_recently_opened_texts_will_appear_h_d0013f51), 16, ui.colors().secondaryText(), false);
            add(page.root, empty, 30, 30);
            return page.scroll;
        }
        Button clear = ui.smallButton(local(com.orthodoxprayers.privateapp.R.string.ui_clear_history_0e69bce2), false);
        clear.setOnClickListener(v -> {
            preferences.clearRecentServices();
            host.navigate("history", null);
        });
        add(page.root, clear, 10, 10);
        for (String id : recent) {
            JSONObject service = data.findService(id);
            if (service != null) add(page.root, serviceCard(service), 2, 7);
        }
        return page.scroll;
    }
}
