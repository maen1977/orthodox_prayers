package com.orthodoxprayers.privateapp.ui;

import android.graphics.Color;

import com.orthodoxprayers.privateapp.AppPreferences;

public final class ThemePalette {
    public static final int NAVY = Color.rgb(6, 43, 79);
    public static final int NAVY_2 = Color.rgb(9, 58, 105);
    public static final int GOLD = Color.rgb(201, 154, 58);
    private final boolean dark;

    public ThemePalette(AppPreferences preferences) { dark = preferences.darkMode(); }

    public int background() { return dark ? Color.rgb(12, 18, 28) : Color.rgb(248, 246, 240); }
    public int card() { return dark ? Color.rgb(25, 34, 48) : Color.WHITE; }
    public int cardAlt() { return dark ? Color.rgb(34, 45, 61) : Color.rgb(244, 241, 233); }
    public int primaryText() { return dark ? Color.rgb(245, 247, 250) : Color.rgb(17, 37, 61); }
    public int secondaryText() { return dark ? Color.rgb(190, 199, 211) : Color.rgb(82, 86, 92); }
    public int accentText() { return dark ? Color.rgb(229, 190, 106) : NAVY; }
    public int border() { return dark ? Color.rgb(57, 69, 86) : Color.rgb(224, 221, 213); }
    public int buttonBorder() { return dark ? Color.rgb(76, 91, 112) : Color.rgb(211, 208, 199); }
    public int divider() { return dark ? Color.rgb(53, 64, 79) : Color.rgb(229, 226, 218); }
    public int ripple() { return dark ? 0x28FFFFFF : 0x18062B4F; }
    public int warning() { return dark ? Color.rgb(255, 190, 140) : Color.rgb(164, 32, 45); }
    public int warningMuted() { return dark ? Color.rgb(116, 78, 65) : Color.rgb(235, 199, 203); }
    public int success() { return dark ? Color.rgb(159, 221, 177) : Color.rgb(31, 112, 62); }
    public int successMuted() { return dark ? Color.rgb(63, 96, 75) : Color.rgb(190, 224, 200); }
    public int navBackground() { return dark ? Color.rgb(7, 28, 51) : NAVY; }
    public int selectedNavBackground() { return dark ? Color.rgb(40, 61, 84) : Color.rgb(22, 67, 106); }
    public boolean isDark() { return dark; }
}
