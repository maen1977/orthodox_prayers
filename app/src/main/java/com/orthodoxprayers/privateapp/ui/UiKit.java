package com.orthodoxprayers.privateapp.ui;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.os.Build;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Space;
import android.widget.TextView;

import com.orthodoxprayers.privateapp.AppPreferences;
import com.orthodoxprayers.privateapp.R;

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
        scroll.setClipToPadding(false);
        LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setLayoutDirection(preferences.isRtl() ? View.LAYOUT_DIRECTION_RTL : View.LAYOUT_DIRECTION_LTR);
        root.setPadding(dp(16), 0, dp(16), dp(28));
        scroll.addView(root, new ScrollView.LayoutParams(-1, -2));
        return new Page(scroll, root);
    }

    /** Compact app bar used by every standard screen. */
    public LinearLayout header(String title, boolean showBack, Runnable backAction) {
        LinearLayout box = row();
        box.setGravity(Gravity.CENTER_VERTICAL);
        box.setMinimumHeight(dp(64));
        box.setPadding(dp(8), dp(6), dp(8), dp(6));
        box.setBackground(gradient(ThemePalette.NAVY, ThemePalette.NAVY_2, 0, 0));
        box.setElevation(dp(3));

        if (showBack) {
            ImageButton back = iconButton(R.drawable.ic_arrow_back, local("رجوع", "Back", "Πίσω"), false);
            back.setRotation(preferences.isRtl() ? 180f : 0f);
            back.setOnClickListener(v -> backAction.run());
            box.addView(back, new LinearLayout.LayoutParams(dp(48), dp(48)));
        } else {
            box.addView(new Space(activity), new LinearLayout.LayoutParams(dp(48), dp(48)));
        }

        TextView heading = text(title, 20, Color.WHITE, true);
        heading.setGravity(Gravity.CENTER);
        heading.setMaxLines(2);
        heading.setEllipsize(TextUtils.TruncateAt.END);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) heading.setAccessibilityHeading(true);
        LinearLayout.LayoutParams headingParams = new LinearLayout.LayoutParams(0, -2, 1f);
        headingParams.setMargins(dp(8), 0, dp(8), 0);
        box.addView(heading, headingParams);

        ImageView cross = new ImageView(activity);
        cross.setImageResource(R.drawable.orthodox_cross_icon);
        cross.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        cross.setContentDescription(local("الصليب الأرثوذكسي", "Orthodox cross", "Ὀρθόδοξος σταυρός"));
        box.addView(cross, new LinearLayout.LayoutParams(dp(40), dp(40)));
        return box;
    }

    public TextView sectionTitle(String title) {
        TextView view = text(title, 18, palette.accentText(), true);
        view.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        view.setPadding(dp(2), dp(22), dp(2), dp(9));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) view.setAccessibilityHeading(true);
        return view;
    }

    public View divider() {
        View view = new View(activity);
        view.setBackgroundColor(palette.divider());
        return view;
    }

    public LinearLayout card() { return card(palette.card(), palette.border(), 18); }

    public LinearLayout elevatedCard() {
        LinearLayout value = card(palette.card(), Color.TRANSPARENT, 20);
        value.setElevation(dp(2));
        return value;
    }

    public LinearLayout card(int color, int stroke, int radius) {
        LinearLayout value = new LinearLayout(activity);
        value.setOrientation(LinearLayout.VERTICAL);
        value.setBackground(round(color, stroke, radius));
        value.setPadding(dp(16), dp(14), dp(16), dp(14));
        value.setClipToOutline(true);
        return value;
    }

    public Button button(String label, boolean active) {
        Button button = new Button(activity);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(14 * preferences.fontScale());
        button.setGravity(Gravity.CENTER);
        button.setMinHeight(dp(52));
        button.setMinimumHeight(dp(52));
        button.setPadding(dp(14), dp(8), dp(14), dp(8));
        button.setTextColor(active ? Color.WHITE : palette.primaryText());
        int fill = active ? ThemePalette.NAVY : palette.cardAlt();
        int stroke = active ? ThemePalette.NAVY : palette.buttonBorder();
        button.setBackground(ripple(fill, stroke, 16, active ? 0x33FFFFFF : palette.ripple()));
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        button.setStateListAnimator(null);
        if (active) button.setElevation(dp(2));
        applyTextDirection(button, label);
        button.setContentDescription(label == null ? "" : label.replace('\n', ' '));
        return button;
    }

    public Button smallButton(String label, boolean active) {
        Button button = button(label, active);
        button.setTextSize(13 * preferences.fontScale());
        button.setMinHeight(dp(44));
        button.setMinimumHeight(dp(44));
        button.setPadding(dp(10), dp(6), dp(10), dp(6));
        return button;
    }

    public Button shortcutButton(String label, int iconResource, boolean active) {
        Button button = button(label, active);
        Drawable icon = activity.getDrawable(iconResource);
        if (icon != null) {
            icon.setTint(active ? Color.WHITE : palette.accentText());
            int size = dp(27);
            icon.setBounds(0, 0, size, size);
            button.setCompoundDrawables(null, icon, null, null);
            button.setCompoundDrawablePadding(dp(8));
        }
        button.setMinHeight(dp(92));
        button.setMinimumHeight(dp(92));
        button.setTextSize(13 * preferences.fontScale());
        return button;
    }

    public ImageButton iconButton(int iconResource, String description, boolean active) {
        ImageButton button = new ImageButton(activity);
        button.setImageResource(iconResource);
        button.setImageTintList(ColorStateList.valueOf(active ? ThemePalette.GOLD : Color.WHITE));
        button.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        button.setPadding(dp(12), dp(12), dp(12), dp(12));
        button.setBackground(ripple(Color.TRANSPARENT, Color.TRANSPARENT, 24, 0x33FFFFFF));
        button.setContentDescription(description);
        button.setFocusable(true);
        button.setClickable(true);
        return button;
    }

    public TextView text(String value, float sp, int color, boolean bold) {
        TextView view = new TextView(activity);
        view.setText(value == null ? "" : value);
        view.setTextSize(sp * preferences.fontScale());
        view.setTextColor(color);
        view.setIncludeFontPadding(false);
        Typeface base;
        if ("serif".equals(preferences.fontFamily())) base = Typeface.create("serif", Typeface.NORMAL);
        else base = Typeface.create("sans-serif", Typeface.NORMAL);
        view.setTypeface(base, bold ? Typeface.BOLD : Typeface.NORMAL);
        applyTextDirection(view, value);
        return view;
    }

    public TextView body(String value, boolean rubric) {
        TextView view = text(value, rubric ? 15 : 18, rubric ? palette.secondaryText() : palette.primaryText(), false);
        if (rubric) view.setTypeface(view.getTypeface(), Typeface.ITALIC);
        view.setLineSpacing(dp(5), preferences.lineSpacingMultiplier());
        view.setTextIsSelectable(true);
        return view;
    }

    public TextView badge(String value, boolean positive) {
        TextView badge = text(value, 12, positive ? palette.success() : palette.warning(), true);
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(10), dp(7), dp(10), dp(7));
        badge.setBackground(round(palette.cardAlt(), positive ? palette.successMuted() : palette.warningMuted(), 12));
        return badge;
    }

    public TextView infoBadge(String value) {
        TextView badge = text(value, 12, palette.accentText(), true);
        badge.setGravity(Gravity.CENTER);
        badge.setPadding(dp(10), dp(7), dp(10), dp(7));
        badge.setBackground(round(palette.cardAlt(), palette.buttonBorder(), 12));
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
        if (stroke != Color.TRANSPARENT && stroke != 0) drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    public GradientDrawable gradient(int start, int end, int stroke, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, new int[]{start, end});
        drawable.setCornerRadius(dp(radiusDp));
        if (stroke != Color.TRANSPARENT && stroke != 0) drawable.setStroke(dp(1), stroke);
        return drawable;
    }

    public Drawable ripple(int fill, int stroke, int radiusDp, int rippleColor) {
        GradientDrawable content = round(fill, stroke, radiusDp);
        GradientDrawable mask = round(Color.WHITE, Color.TRANSPARENT, radiusDp);
        return new RippleDrawable(ColorStateList.valueOf(rippleColor), content, mask);
    }

    public int dp(int value) { return (int) (value * activity.getResources().getDisplayMetrics().density + 0.5f); }

    public String local(String ar, String en, String el) {
        String language = preferences.effectiveLanguage();
        if ("en".equals(language)) return en;
        if ("el".equals(language)) return el;
        return ar;
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
