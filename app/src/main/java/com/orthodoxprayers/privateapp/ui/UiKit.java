package com.orthodoxprayers.privateapp.ui;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.AppPreferences;

public final class UiKit {
    public static final class Page {
        public final ScrollView scroll;
        public final LinearLayout root;
        private Page(ScrollView scroll, LinearLayout root) { this.scroll = scroll; this.root = root; }
    }

    private final Activity activity;
    private final AppPreferences preferences;
    private ThemePalette palette;

    public UiKit(Activity activity, AppPreferences preferences) {
        this.activity = activity;
        this.preferences = preferences;
        refreshTheme();
    }

    public void refreshTheme() { palette = new ThemePalette(preferences); }
    public ThemePalette colors() { return palette; }
    public AppPreferences preferences() { return preferences; }

    public Page page() {
        ScrollView scroll = new ScrollView(activity);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(palette.background());
        LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setLayoutDirection(preferences.isRtl() ? View.LAYOUT_DIRECTION_RTL : View.LAYOUT_DIRECTION_LTR);
        root.setPadding(dp(14), 0, dp(14), dp(18));
        scroll.addView(root, new ScrollView.LayoutParams(-1, -2));
        return new Page(scroll, root);
    }

    public LinearLayout header(String title, boolean showBack, Runnable backAction) {
        LinearLayout box = new LinearLayout(activity);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setPadding(dp(16), dp(10), dp(16), dp(16));
        box.setBackground(gradient(ThemePalette.NAVY, ThemePalette.NAVY_2, 0, 0));
        if (showBack) {
            LinearLayout navigationRow = row();
            navigationRow.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            navigationRow.addView(backArrow(backAction), new LinearLayout.LayoutParams(dp(48), dp(48)));
            box.addView(navigationRow, new LinearLayout.LayoutParams(-1, -2));
        }
        TextView cross = text("☦", 34, ThemePalette.GOLD, true);
        cross.setGravity(Gravity.CENTER);
        cross.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_orthodox_cross_8e65fdfc));
        box.addView(cross);
        TextView heading = text(title, 24, ThemePalette.GOLD, true);
        heading.setGravity(Gravity.CENTER);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) heading.setAccessibilityHeading(true);
        box.addView(heading);
        return box;
    }

    /**
     * A compact, system-like back affordance. The arrow mirrors in RTL while
     * keeping a full 48dp touch target and an accessible spoken label.
     */
    public TextView backArrow(Runnable backAction) {
        TextView back = text(preferences.isRtl() ? "→" : "←", 25, ThemePalette.GOLD, true);
        back.setGravity(Gravity.CENTER);
        back.setMinWidth(dp(48));
        back.setMinimumWidth(dp(48));
        back.setMinHeight(dp(48));
        back.setMinimumHeight(dp(48));
        back.setClickable(true);
        back.setFocusable(true);
        back.setBackground(round(ThemePalette.NAVY_2, ThemePalette.GOLD, 12));
        back.setContentDescription(local(com.orthodoxprayers.privateapp.R.string.ui_return_to_the_previous_screen_adc27814));
        back.setOnClickListener(v -> backAction.run());
        return back;
    }

    public TextView sectionTitle(String title) {
        TextView view = text("✥  " + title + "  ✥", 20, palette.primaryText(), true);
        view.setGravity(Gravity.CENTER);
        view.setPadding(0, dp(14), 0, dp(7));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) view.setAccessibilityHeading(true);
        return view;
    }

    public LinearLayout card() { return card(palette.card(), palette.border(), 14); }

    /**
     * Compact two-column shortcut card for the home screen. Unlike a plain
     * button, the complete card surface remains tappable and accessible.
     */
    public LinearLayout shortcutCard(int iconResource, String title) {
        LinearLayout card = card();
        card.setGravity(Gravity.CENTER);
        card.setClickable(true);
        card.setFocusable(true);
        card.setMinimumHeight(dp(104));

        ImageView icon = new ImageView(activity);
        icon.setImageResource(iconResource);
        icon.setImageTintList(ColorStateList.valueOf(palette.accentText()));
        icon.setContentDescription(null);
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(dp(32), dp(32));
        iconParams.gravity = Gravity.CENTER_HORIZONTAL;
        card.addView(icon, iconParams);

        TextView label = text(title, 15, palette.primaryText(), true);
        label.setGravity(Gravity.CENTER);
        label.setMaxLines(2);
        card.addView(label, margins(-1, -2, 0, 8, 0, 0));
        card.setContentDescription(title);
        return card;
    }

    public LinearLayout actionCard(int iconResource, String title, String subtitle) {
        LinearLayout card = card();
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setClickable(true);
        card.setFocusable(true);
        card.setMinimumHeight(dp(82));

        ImageView icon = new ImageView(activity);
        icon.setImageResource(iconResource);
        icon.setImageTintList(ColorStateList.valueOf(palette.accentText()));
        icon.setContentDescription(null);
        card.addView(icon, new LinearLayout.LayoutParams(dp(34), dp(34)));

        LinearLayout labels = new LinearLayout(activity);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setGravity(preferences.isRtl() ? Gravity.RIGHT : Gravity.LEFT);
        labels.setPadding(dp(12), 0, dp(12), 0);
        TextView heading = text(title, 18, palette.primaryText(), true);
        heading.setGravity(preferences.isRtl() ? Gravity.RIGHT : Gravity.LEFT);
        labels.addView(heading, new LinearLayout.LayoutParams(-1, -2));
        String safeSubtitle = subtitle == null ? "" : subtitle.trim();
        if (!safeSubtitle.isEmpty()) {
            TextView detail = text(safeSubtitle, 13, palette.secondaryText(), false);
            detail.setGravity(preferences.isRtl() ? Gravity.RIGHT : Gravity.LEFT);
            detail.setMaxLines(2);
            labels.addView(detail, margins(-1, -2, 0, 3, 0, 0));
        }
        card.addView(labels, new LinearLayout.LayoutParams(0, -2, 1f));

        TextView arrow = text(preferences.isRtl() ? "‹" : "›", 28, palette.accentText(), true);
        arrow.setGravity(Gravity.CENTER);
        arrow.setContentDescription(null);
        card.addView(arrow, new LinearLayout.LayoutParams(dp(24), -1));
        card.setContentDescription(title + (safeSubtitle.isEmpty() ? "" : ". " + safeSubtitle));
        return card;
    }

    public LinearLayout card(int color, int stroke, int radius) {
        LinearLayout value = new LinearLayout(activity);
        value.setOrientation(LinearLayout.VERTICAL);
        value.setBackground(round(color, stroke, radius));
        value.setPadding(dp(12), dp(11), dp(12), dp(11));
        return value;
    }

    public Button button(String label, boolean active) {
        Button button = new Button(activity);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(14 * preferences.fontScale());
        button.setGravity(Gravity.CENTER);
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setTextColor(active ? android.graphics.Color.WHITE : palette.primaryText());
        button.setBackground(round(active ? ThemePalette.NAVY : palette.card(), ThemePalette.GOLD, 14));
        applyTextDirection(button, label);
        button.setContentDescription(label.replace('\n', ' '));
        return button;
    }

    public Button smallButton(String label, boolean active) {
        Button button = button(label, active);
        button.setTextSize(13 * preferences.fontScale());
        return button;
    }

    public Button smallIconButton(int iconResource, String label, boolean active) {
        Button button = smallButton(label, active);
        Drawable icon = activity.getDrawable(iconResource);
        if (icon != null) {
            icon = icon.mutate();
            icon.setTint(active ? android.graphics.Color.WHITE : palette.accentText());
            int size = dp(18);
            icon.setBounds(0, 0, size, size);
            button.setCompoundDrawablesRelative(icon, null, null, null);
            button.setCompoundDrawablePadding(dp(7));
        }
        return button;
    }

    public Button iconButton(int iconResource, String label, boolean active) {
        Button button = button(label, active);
        Drawable icon = activity.getDrawable(iconResource);
        if (icon != null) {
            icon = icon.mutate();
            icon.setTint(active ? android.graphics.Color.WHITE : palette.accentText());
            button.setCompoundDrawablesWithIntrinsicBounds(null, icon, null, null);
            button.setCompoundDrawablePadding(dp(7));
        }
        button.setPadding(dp(8), dp(9), dp(8), dp(9));
        button.setMinHeight(dp(76));
        button.setMinimumHeight(dp(76));
        return button;
    }

    public TextView text(String value, float sp, int color, boolean bold) {
        TextView view = new TextView(activity);
        view.setText(value == null ? "" : value);
        view.setTextSize(sp * preferences.fontScale());
        view.setTextColor(color);
        view.setIncludeFontPadding(true);
        Typeface base;
        if ("serif".equals(preferences.fontFamily())) base = Typeface.SERIF;
        else if ("monospace".equals(preferences.fontFamily())) base = Typeface.MONOSPACE;
        else base = Typeface.SANS_SERIF;
        view.setTypeface(base, bold ? Typeface.BOLD : Typeface.NORMAL);
        applyTextDirection(view, value);
        return view;
    }

    public TextView body(String value, boolean rubric) {
        TextView view = text(value, rubric ? 15 : 18, rubric ? palette.secondaryText() : palette.primaryText(), false);
        if (rubric) view.setTypeface(view.getTypeface(), Typeface.ITALIC);
        view.setLineSpacing(dp(4), preferences.lineSpacingMultiplier());
        view.setTextIsSelectable(true);
        return view;
    }

    public TextView badge(String value, boolean positive) {
        TextView badge = text(value, 12, positive ? palette.success() : palette.warning(), true);
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(8), dp(5), dp(8), dp(5));
        badge.setBackground(round(palette.cardAlt(), positive ? palette.success() : palette.warning(), 12));
        return badge;
    }

    public TextView infoBadge(String value) {
        TextView badge = text(value, 12, palette.accentText(), true);
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(8), dp(5), dp(8), dp(5));
        badge.setBackground(round(palette.cardAlt(), ThemePalette.NAVY_2, 12));
        return badge;
    }

    public LinearLayout row() {
        LinearLayout row = new LinearLayout(activity);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setLayoutDirection(preferences.isRtl() ? View.LAYOUT_DIRECTION_RTL : View.LAYOUT_DIRECTION_LTR);
        return row;
    }

    public LinearLayout.LayoutParams weight(int minimumHeightDp) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        params.setMargins(dp(4), dp(4), dp(4), dp(4));
        params.gravity = Gravity.FILL_VERTICAL;
        return params;
    }

    public LinearLayout.LayoutParams margins(int width, int height, int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(width, height);
        params.setMargins(dp(left), dp(top), dp(right), dp(bottom));
        return params;
    }

    public GradientDrawable round(int color, int stroke, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(dp(radiusDp));
        drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    public GradientDrawable gradient(int start, int end, int stroke, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, new int[]{start, end});
        drawable.setCornerRadius(dp(radiusDp));
        if (stroke != 0) drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    public int dp(int value) { return (int) (value * activity.getResources().getDisplayMetrics().density + 0.5f); }

    public String local(int resourceId) {
        return LocalizedResources.get(activity, preferences.effectiveLanguage(), resourceId);
    }

    public String localFormat(int resourceId, Object... arguments) {
        return LocalizedResources.format(activity, preferences.effectiveLanguage(), resourceId, arguments);
    }

    public void applyTextDirection(TextView view, String value) {
        boolean rtl = containsArabic(value) || ((value == null || value.trim().isEmpty()) && preferences.isRtl());
        view.setLayoutDirection(rtl ? View.LAYOUT_DIRECTION_RTL : View.LAYOUT_DIRECTION_LTR);
        view.setTextDirection(rtl ? View.TEXT_DIRECTION_RTL : View.TEXT_DIRECTION_LTR);
        view.setTextAlignment(View.TEXT_ALIGNMENT_GRAVITY);
    }

    public static boolean containsArabic(String value) {
        if (value == null) return false;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if ((c >= '\u0600' && c <= '\u06FF') || (c >= '\u0750' && c <= '\u077F') || (c >= '\u08A0' && c <= '\u08FF')) return true;
        }
        return false;
    }
}
