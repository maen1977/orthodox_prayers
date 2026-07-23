package com.orthodoxprayers.privateapp.ui;

import android.graphics.Color;

import com.orthodoxprayers.privateapp.AppPreferences;

public final class ThemePalette {
    public static final int NAVY = Color.rgb(6, 43, 79);
    public static final int NAVY_2 = Color.rgb(9, 58, 105);
    public static final int GOLD = Color.rgb(201, 154, 58);
    private final boolean dark;

    public ThemePalette(AppPreferences preferences) { dark = preferences.darkMode(); }

    public int background() { return dark ? Color.rgb(12, 18, 28) : Color.rgb(255, 248, 234); }
    public int card() { return dark ? Color.rgb(30, 39, 54) : Color.WHITE; }
    public int cardAlt() { return dark ? Color.rgb(38, 49, 66) : Color.rgb(250, 244, 231); }
    public int primaryText() { return dark ? Color.WHITE : Color.rgb(8, 32, 61); }
    public int secondaryText() { return dark ? Color.rgb(215, 220, 230) : Color.rgb(72, 72, 72); }
    public int accentText() { return dark ? GOLD : NAVY; }
    public int border() { return dark ? Color.rgb(117, 103, 72) : Color.rgb(225, 204, 158); }
    public int warning() { return dark ? Color.rgb(255, 190, 140) : Color.rgb(176, 0, 32); }
    public int success() { return dark ? Color.rgb(155, 224, 173) : Color.rgb(25, 110, 55); }
    public int navBackground() { return dark ? Color.rgb(7, 32, 58) : NAVY; }
    public int selectedNavBackground() { return dark ? Color.rgb(44, 65, 89) : Color.rgb(22, 67, 106); }
    public boolean isDark() { return dark; }
}
