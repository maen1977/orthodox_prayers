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
        UiKit.Page page = page(local("آخر ما قرأت", "Reading history", "Ἱστορικὸ ἀναγνώσεως"), true);
        List<String> recent = preferences.recentServices();
        if (recent.isEmpty()) {
            TextView empty = centered(local(
                    "سيظهر هنا آخر 20 نصًا فتحته.",
                    "Your 20 most recently opened texts will appear here.",
                    "Ἐδῶ θὰ φαίνονται τὰ 20 πρόσφατα κείμενα."
            ), 16, ui.colors().secondaryText(), false);
            add(page.root, empty, 30, 30);
            return page.scroll;
        }
        Button clear = ui.smallButton(local("مسح السجل", "Clear history", "Διαγραφὴ ἱστορικοῦ"), false);
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
