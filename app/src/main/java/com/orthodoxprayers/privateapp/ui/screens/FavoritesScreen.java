package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.util.Set;

public final class FavoritesScreen extends BaseScreen {
    public FavoritesScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local("المفضلة", "Favorites", "Ἀγαπημένα"), true);
        Set<String> favorites = preferences.favorites();
        if (favorites.isEmpty()) {
            TextView empty = centered(local("لا توجد صلوات محفوظة بعد. افتح أي صلاة واضغط زر النجمة.",
                    "No favorites yet. Open a prayer and press the star.",
                    "Δεν υπάρχουν ἀγαπημένα."), 16, ui.colors().secondaryText(), false);
            add(page.root, empty, 30, 30);
        } else {
            for (String id : favorites) {
                JSONObject service = data.findService(id);
                if (service != null) add(page.root, serviceCard(service), 3, 8);
            }
        }
        return page.scroll;
    }
}
