package com.orthodoxprayers.privateapp.ui;

import android.graphics.Color;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.data.DataRepository;
import com.orthodoxprayers.privateapp.data.TranslationCoverage;
import com.orthodoxprayers.privateapp.model.LocalizedValue;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;
import java.util.List;

public final class ReaderAdapter extends RecyclerView.Adapter<ReaderAdapter.Holder> {
    private static final int SECTION = 1;
    private static final int TEXT = 2;
    private static final int NOTE = 3;

    private final UiKit ui;
    private final DataRepository data;
    private final AppPreferences preferences;
    private final String sourceLanguage;
    private final ArrayList<JSONObject> segments = new ArrayList<>();
    private final ArrayList<Integer> sectionPositions = new ArrayList<>();
    private final Set<Integer> expandedNotes = new HashSet<>();
    private final Set<Integer> collapsedNotes = new HashSet<>();

    public ReaderAdapter(UiKit ui, DataRepository data, AppPreferences preferences, JSONArray input, String sourceLanguage) {
        this.ui = ui;
        this.data = data;
        this.preferences = preferences;
        this.sourceLanguage = sourceLanguage == null ? "ar" : sourceLanguage;
        if (input != null) {
            for (int i = 0; i < input.length(); i++) {
                JSONObject segment = input.optJSONObject(i);
                if (segment != null) {
                    if ("section".equals(segment.optString("type"))) sectionPositions.add(segments.size());
                    segments.add(segment);
                }
            }
        }
        setHasStableIds(true);
    }

    @Override
    public long getItemId(int position) { return (((long) position) << 32) ^ segments.get(position).toString().hashCode(); }

    @Override
    public int getItemViewType(int position) {
        String type = segments.get(position).optString("type", "text");
        if ("section".equals(type)) return SECTION;
        if ("note".equals(type) || "rubric".equals(type)) return NOTE;
        return TEXT;
    }

    @NonNull
    @Override
    public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        LinearLayout container = new LinearLayout(parent.getContext());
        container.setOrientation(LinearLayout.VERTICAL);
        RecyclerView.LayoutParams params = new RecyclerView.LayoutParams(-1, -2);
        params.setMargins(ui.dp(14), ui.dp(3), ui.dp(14), ui.dp(7));
        container.setLayoutParams(params);
        return new Holder(container);
    }

    @Override
    public void onBindViewHolder(@NonNull Holder holder, int position) {
        holder.container.removeAllViews();
        JSONObject segment = segments.get(position);
        int type = getItemViewType(position);
        if (type == SECTION) bindSection(holder.container, segment);
        else if (type == NOTE) bindNote(holder.container, segment, position);
        else bindText(holder.container, segment, false);
    }

    private void bindSection(LinearLayout container, JSONObject segment) {
        LinearLayout card = ui.card(ThemePalette.NAVY, ThemePalette.GOLD, 14);
        String title = data.localized(segment.optJSONObject("title"), data.localized(segment.optJSONObject("text"), ""));
        TextView heading = ui.text("✥  " + title + "  ✥", 19, ThemePalette.GOLD, true);
        heading.setGravity(Gravity.CENTER);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) heading.setAccessibilityHeading(true);
        card.addView(heading);
        card.setContentDescription(title);
        container.addView(card, new LinearLayout.LayoutParams(-1, -2));
    }

    private void bindNote(LinearLayout container, JSONObject segment, int position) {
        LinearLayout card = ui.card();
        String label = data.localized(segment.optJSONObject("speaker"), data.local("ملاحظة اختيارية", "Optional note", "Προαιρετικὴ σημείωση"));
        boolean defaultCollapsed = segment.optBoolean("collapsed_by_default", true);
        boolean expanded = defaultCollapsed ? expandedNotes.contains(position) : !collapsedNotes.contains(position);
        Button toggle = ui.smallButton((expanded ? "▾  " : "▸  ") + label, false);
        toggle.setContentDescription(label + ". " + (expanded
                ? data.local("اضغط للإخفاء", "Tap to collapse", "Πατήστε γιὰ σύμπτυξη")
                : data.local("اضغط للعرض", "Tap to expand", "Πατήστε γιὰ ἀνάπτυξη")));
        toggle.setOnClickListener(v -> {
            if (defaultCollapsed) {
                if (expandedNotes.contains(position)) expandedNotes.remove(position);
                else expandedNotes.add(position);
            } else {
                if (collapsedNotes.contains(position)) collapsedNotes.remove(position);
                else collapsedNotes.add(position);
            }
            notifyItemChanged(position);
        });
        card.addView(toggle);
        if (expanded) {
            LocalizedValue value = data.localizedValue(segment.optJSONObject("text"), "");
            TextView body = ui.body(value.text, true);
            card.addView(body, ui.margins(-1, -2, 0, 6, 0, 0));
            if (value.translationUnavailable) {
                card.addView(ui.badge(data.local(
                        "النص الأصلي المعتمد بهذه اللغة غير متوفر لهذا المقطع",
                        "Official native text unavailable for this section",
                        "Τὸ ἐπίσημο πρωτότυπο κείμενο δὲν εἶναι διαθέσιμο γιὰ αὐτὸ τὸ τμήμα"
                ), false));
            }
        }
        container.addView(card, new LinearLayout.LayoutParams(-1, -2));
    }

    private void bindText(LinearLayout container, JSONObject segment, boolean rubric) {
        LinearLayout card = ui.card();
        String speaker = data.localized(segment.optJSONObject("speaker"), "");
        if (!speaker.isEmpty()) {
            TextView speakerView = ui.text(speaker, 14, ThemePalette.GOLD, true);
            card.addView(speakerView);
        }
        LocalizedValue value = data.localizedValue(segment.optJSONObject("text"), "");
        TextView body = ui.body(value.text, rubric);
        card.addView(body, ui.margins(-1, -2, 0, speaker.isEmpty() ? 0 : 3, 0, 0));

        if (value.translationUnavailable) {
            card.addView(ui.badge(data.local(
                    "النص الأصلي المعتمد بهذه اللغة غير متوفر لهذا المقطع",
                    "Official native text unavailable for this section",
                    "Τὸ ἐπίσημο πρωτότυπο κείμενο δὲν εἶναι διαθέσιμο γιὰ αὐτὸ τὸ τμήμα"
            ), false), ui.margins(-1, -2, 0, 7, 0, 0));
        }

        if (preferences.showOriginal()) {
            JSONObject textObject = segment.optJSONObject("text");
            String original = originalText(textObject);
            if (!original.isEmpty() && !original.equals(value.text)) {
                TextView originalView = ui.text("— " + data.local("النص الأصلي", "Source text", "Πρωτότυπο") + " —\n" + original,
                        15, ui.colors().secondaryText(), false);
                originalView.setLineSpacing(ui.dp(3), 1.12f);
                originalView.setTextIsSelectable(true);
                card.addView(originalView, ui.margins(-1, -2, 0, 8, 0, 0));
            }
        }
        card.setContentDescription((speaker.isEmpty() ? "" : speaker + ". ") + value.text);
        container.addView(card, new LinearLayout.LayoutParams(-1, -2));
    }

    private String originalText(JSONObject object) {
        if (object == null) return "";
        // A source view may repeat only the service's own registered language.
        // It must never fall back to Arabic, English, or Greek from another lane.
        if (!"ar".equals(sourceLanguage) && !"en".equals(sourceLanguage) && !"el".equals(sourceLanguage)) return "";
        return object.optString(sourceLanguage, "").trim();
    }

    @Override
    public int getItemCount() { return segments.size(); }

    public List<Integer> sectionPositions() { return new ArrayList<>(sectionPositions); }

    public int findPosition(String... needles) {
        for (int i = 0; i < segments.size(); i++) {
            JSONObject segment = segments.get(i);
            String text = allLanguages(segment.optJSONObject("title")) + " " + allLanguages(segment.optJSONObject("text"));
            for (String needle : needles) {
                if (needle != null && !needle.isEmpty() && text.toLowerCase().contains(needle.toLowerCase())) return i;
            }
        }
        return -1;
    }

    private static String allLanguages(JSONObject object) {
        if (object == null) return "";
        return object.optString("ar", "") + " " + object.optString("en", "") + " " + object.optString("el", "");
    }

    static final class Holder extends RecyclerView.ViewHolder {
        final LinearLayout container;
        Holder(@NonNull LinearLayout itemView) {
            super(itemView);
            container = itemView;
        }
    }
}
