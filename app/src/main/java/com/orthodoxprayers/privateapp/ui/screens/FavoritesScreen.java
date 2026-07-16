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
        UiKit.Page page = page(local("المفضلة", "Favorites", "Ἀγαπημένα"), true);
        List<String> favorites = preferences.favoriteOrder();
        if (favorites.isEmpty()) {
            TextView empty = centered(local(
                    "لا توجد صلوات محفوظة بعد. افتح أي صلاة واضغط زر النجمة.",
                    "No favorites yet. Open a prayer and press the star.",
                    "Δεν υπάρχουν ἀγαπημένα."
            ), 16, ui.colors().secondaryText(), false);
            add(page.root, empty, 30, 30);
            return page.scroll;
        }

        add(page.root, ui.infoBadge(local(
                "يمكنك تثبيت النص في الأعلى، نقله للأعلى أو للأسفل، ووضعه في مجموعة يومية أو طقسية أو شخصية.",
                "Pin items, reorder them, and place them in Daily, Liturgy or Personal collections.",
                "Μπορεῖς νὰ καρφιτσώσεις, νὰ ταξινομήσεις καὶ νὰ ὁμαδοποιήσεις τὰ κείμενα."
        )), 10, 10);

        addFolder(page.root, favorites, "pinned", local("مثبتة", "Pinned", "Καρφιτσωμένα"));
        addFolder(page.root, favorites, "daily", local("يومية", "Daily", "Καθημερινά"));
        addFolder(page.root, favorites, "liturgy", local("الخدمات والقداس", "Services and Liturgy", "Ἀκολουθίες καὶ Λειτουργία"));
        addFolder(page.root, favorites, "personal", local("شخصية", "Personal", "Προσωπικά"));
        addFolder(page.root, favorites, "default", local("غير مصنفة", "Unsorted", "Χωρὶς κατηγορία"));
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
        up.setContentDescription(local("نقل للأعلى", "Move up", "Μετακίνηση πάνω"));
        up.setOnClickListener(v -> { preferences.moveFavorite(id, -1); host.navigate("favorites", null); });
        row.addView(up, ui.weight(42));
        Button down = ui.smallButton("↓", false);
        down.setContentDescription(local("نقل للأسفل", "Move down", "Μετακίνηση κάτω"));
        down.setOnClickListener(v -> { preferences.moveFavorite(id, 1); host.navigate("favorites", null); });
        row.addView(down, ui.weight(42));

        Button pin = ui.smallButton(preferences.isPinned(id)
                ? local("إلغاء التثبيت", "Unpin", "Ξεκαρφίτσωμα")
                : local("تثبيت", "Pin", "Καρφίτσωμα"), preferences.isPinned(id));
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
        if ("daily".equals(folder)) return local("يومية", "Daily", "Καθημερινά");
        if ("liturgy".equals(folder)) return local("طقسية", "Liturgy", "Λειτουργικά");
        if ("personal".equals(folder)) return local("شخصية", "Personal", "Προσωπικά");
        return local("مجموعة", "Collection", "Συλλογή");
    }
}
