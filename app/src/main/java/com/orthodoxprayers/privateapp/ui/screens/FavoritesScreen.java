package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public final class FavoritesScreen extends BaseScreen {
    public FavoritesScreen(ScreenHost host) { super(host); }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_favorites_8eb8984d), true);
        List<String> favorites = preferences.favoriteOrder();
        if (favorites.isEmpty()) {
            TextView empty = centered(local(com.orthodoxprayers.privateapp.R.string.ui_no_favorites_yet_open_a_prayer_and_press_the_sta_3ddef562), 16, ui.colors().secondaryText(), false);
            add(page.root, empty, 30, 30);
            return page.scroll;
        }

        add(page.root, ui.infoBadge(local(com.orthodoxprayers.privateapp.R.string.ui_pin_items_reorder_them_and_place_them_in_daily_l_1901ea8a)), 10, 10);

        addFolder(page.root, favorites, "pinned", local(com.orthodoxprayers.privateapp.R.string.ui_pinned_413a9c52));
        addFolder(page.root, favorites, "daily", local(com.orthodoxprayers.privateapp.R.string.ui_daily_a469bee1));
        addFolder(page.root, favorites, "liturgy", local(com.orthodoxprayers.privateapp.R.string.ui_services_and_liturgy_0e5a1fe9));
        addFolder(page.root, favorites, "personal", local(com.orthodoxprayers.privateapp.R.string.ui_personal_28997b7b));
        addFolder(page.root, favorites, "default", local(com.orthodoxprayers.privateapp.R.string.ui_unsorted_5539c6cd));
        return page.scroll;
    }

    private void addFolder(LinearLayout root, List<String> all, String folder, String title) {
        ArrayList<String> items = new ArrayList<>();
        for (String id : all) {
            if ("pinned".equals(folder)) {
                if (preferences.isPinned(id)) items.add(id);
            } else if (!preferences.isPinned(id) && folder.equals(preferences.favoriteFolder(id))) {
                items.add(id);
            }
        }
        if (items.isEmpty()) return;
        root.addView(ui.sectionTitle(title));
        for (String id : items) {
            JSONObject service = data.findService(id);
            if (service != null) add(root, favoriteCard(service, id), 2, 8);
        }
    }

    private LinearLayout favoriteCard(JSONObject service, String id) {
        LinearLayout wrapper = ui.card();
        LinearLayout open = serviceCard(service);
        wrapper.addView(open, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout row = ui.row();
        Button up = ui.smallButton("↑", false);
        up.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_move_up_12875d17));
        up.setOnClickListener(v -> { preferences.moveFavorite(id, -1); host.navigate("favorites", null); });
        row.addView(up, ui.weight(42));
        Button down = ui.smallButton("↓", false);
        down.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_move_down_12468f91));
        down.setOnClickListener(v -> { preferences.moveFavorite(id, 1); host.navigate("favorites", null); });
        row.addView(down, ui.weight(42));

        Button pin = ui.smallButton(preferences.isPinned(id)
                ? local(com.orthodoxprayers.privateapp.R.string.ui_unpin_8711604f)
                : local(com.orthodoxprayers.privateapp.R.string.ui_pin_d4bc9c4f), preferences.isPinned(id));
        pin.setOnClickListener(v -> { preferences.togglePinned(id); host.navigate("favorites", null); });
        row.addView(pin, ui.weight(42));

        Button folder = ui.smallButton(folderLabel(preferences.favoriteFolder(id)), false);
        folder.setOnClickListener(v -> {
            preferences.setFavoriteFolder(id, nextFolder(preferences.favoriteFolder(id)));
            host.navigate("favorites", null);
        });
        row.addView(folder, ui.weight(42));
        wrapper.addView(row, ui.margins(-1, -2, 0, 7, 0, 0));
        return wrapper;
    }

    private String nextFolder(String current) {
        if ("daily".equals(current)) return "liturgy";
        if ("liturgy".equals(current)) return "personal";
        if ("personal".equals(current)) return "default";
        return "daily";
    }

    private String folderLabel(String folder) {
        if ("daily".equals(folder)) return local(com.orthodoxprayers.privateapp.R.string.ui_daily_a469bee1);
        if ("liturgy".equals(folder)) return local(com.orthodoxprayers.privateapp.R.string.ui_liturgy_8ff5e178);
        if ("personal".equals(folder)) return local(com.orthodoxprayers.privateapp.R.string.ui_personal_28997b7b);
        return local(com.orthodoxprayers.privateapp.R.string.ui_collection_56e98b45);
    }
}
