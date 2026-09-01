package com.orthodoxprayers.privateapp.data;

import org.json.JSONObject;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.Locale;

/**
 * Calendar-driven home notice for the nearest meaningful Orthodox fast.
 *
 * <p>The engine never hard-codes civil dates. It reads the embedded church
 * calendar (2026-2050), groups the four major fasting seasons across their
 * changing daily food rules, and falls back to an actually-applicable
 * Wednesday/Friday fast. This keeps the home notice correct in future years
 * and through movable seasons such as Great Lent and the Apostles' Fast.</p>
 */
public final class FastingNoticeEngine {
    public static final int MAJOR_FAST_LOOKAHEAD_DAYS = 30;
    public static final int WEEKLY_FAST_LOOKAHEAD_DAYS = 7;
    private static final int MAJOR_FAST_BOUNDARY_SCAN_DAYS = 80;

    private FastingNoticeEngine() {}

    public interface DayProvider {
        JSONObject day(String isoDate);
    }

    public enum Kind {
        CURRENT_MAJOR_FAST,
        UPCOMING_MAJOR_FAST,
        UPCOMING_WEEKLY_FAST,
        NONE
    }

    public enum Family {
        DORMITION,
        NATIVITY,
        GREAT_LENT,
        APOSTLES,
        NONE
    }

    public static final class Notice {
        public final Kind kind;
        public final Family family;
        public final LocalDate targetDate;
        public final LocalDate startDate;
        public final LocalDate endDate;
        public final int daysUntilStart;
        public final int dayNumber;
        public final int daysRemaining;
        public final int totalDays;
        /** True when the selected day is the feast after a major fast, not a fast-season day. */
        public final boolean feastDay;
        public final DayOfWeek weekday;

        private Notice(
                Kind kind,
                Family family,
                LocalDate targetDate,
                LocalDate startDate,
                LocalDate endDate,
                int daysUntilStart,
                int dayNumber,
                int daysRemaining,
                int totalDays,
                boolean feastDay,
                DayOfWeek weekday
        ) {
            this.kind = kind;
            this.family = family;
            this.targetDate = targetDate;
            this.startDate = startDate;
            this.endDate = endDate;
            this.daysUntilStart = daysUntilStart;
            this.dayNumber = dayNumber;
            this.daysRemaining = daysRemaining;
            this.totalDays = totalDays;
            this.feastDay = feastDay;
            this.weekday = weekday;
        }

        public static Notice none(LocalDate today) {
            return new Notice(
                    Kind.NONE,
                    Family.NONE,
                    today,
                    null,
                    null,
                    -1,
                    0,
                    0,
                    0,
                    false,
                    today == null ? null : today.getDayOfWeek()
            );
        }
    }

    public static Notice evaluate(LocalDate today, DayProvider provider) {
        if (today == null || provider == null) return Notice.none(today);

        JSONObject currentDay = provider.day(today.toString());
        Family currentFamily = majorFamily(currentDay);
        if (currentFamily != Family.NONE) {
            boolean feastDay = !isMajorSeasonDay(currentDay, currentFamily);
            LocalDate seasonAnchor = feastDay ? today.minusDays(1) : today;
            LocalDate start = findBoundary(seasonAnchor, provider, currentFamily, -1);
            LocalDate end = feastDay ? seasonAnchor : findBoundary(today, provider, currentFamily, 1);
            int total = inclusiveDays(start, end);
            int dayNumber = feastDay ? total : (int) ChronoUnit.DAYS.between(start, today) + 1;
            int remaining = feastDay ? 0 : (int) ChronoUnit.DAYS.between(today, end);
            return new Notice(
                    Kind.CURRENT_MAJOR_FAST,
                    currentFamily,
                    today,
                    start,
                    end,
                    0,
                    Math.max(1, dayNumber),
                    Math.max(0, remaining),
                    Math.max(1, total),
                    feastDay,
                    today.getDayOfWeek()
            );
        }

        for (int offset = 1; offset <= MAJOR_FAST_LOOKAHEAD_DAYS; offset++) {
            LocalDate candidate = today.plusDays(offset);
            Family family = majorFamily(provider.day(candidate.toString()));
            if (family == Family.NONE) continue;
            Family previous = majorFamily(provider.day(candidate.minusDays(1).toString()));
            if (previous == family) continue;
            LocalDate end = findBoundary(candidate, provider, family, 1);
            return new Notice(
                    Kind.UPCOMING_MAJOR_FAST,
                    family,
                    candidate,
                    candidate,
                    end,
                    offset,
                    0,
                    (int) ChronoUnit.DAYS.between(candidate, end),
                    inclusiveDays(candidate, end),
                    false,
                    candidate.getDayOfWeek()
            );
        }

        for (int offset = 1; offset <= WEEKLY_FAST_LOOKAHEAD_DAYS; offset++) {
            LocalDate candidate = today.plusDays(offset);
            JSONObject day = provider.day(candidate.toString());
            if (!isWeeklyFast(day, candidate.getDayOfWeek())) continue;
            return new Notice(
                    Kind.UPCOMING_WEEKLY_FAST,
                    Family.NONE,
                    candidate,
                    candidate,
                    candidate,
                    offset,
                    0,
                    0,
                    1,
                    false,
                    candidate.getDayOfWeek()
            );
        }

        return Notice.none(today);
    }

    private static boolean isMajorSeasonDay(JSONObject day, Family family) {
        if (day == null || family == Family.NONE) return false;
        JSONObject fasting = day.optJSONObject("fasting");
        if (fasting == null || !fasting.optBoolean("is_fast", false)) return false;
        JSONObject verification = fasting.optJSONObject("verification");
        String rule = verification == null ? "" : verification.optString("rule", "").trim();
        if (family == Family.DORMITION && rule.startsWith("dormition_feast_")) return false;
        return majorFamily(day) == family;
    }

    private static LocalDate findBoundary(
            LocalDate anchor,
            DayProvider provider,
            Family family,
            int direction
    ) {
        LocalDate boundary = anchor;
        for (int i = 0; i < MAJOR_FAST_BOUNDARY_SCAN_DAYS; i++) {
            LocalDate next = boundary.plusDays(direction);
            if (!isMajorSeasonDay(provider.day(next.toString()), family)) break;
            boundary = next;
        }
        return boundary;
    }

    private static int inclusiveDays(LocalDate start, LocalDate end) {
        if (start == null || end == null) return 0;
        return (int) ChronoUnit.DAYS.between(start, end) + 1;
    }

    private static boolean isWeeklyFast(JSONObject day, DayOfWeek weekday) {
        if (day == null || (weekday != DayOfWeek.WEDNESDAY && weekday != DayOfWeek.FRIDAY)) {
            return false;
        }
        JSONObject fasting = day.optJSONObject("fasting");
        if (fasting == null || !fasting.optBoolean("is_fast", false)) return false;
        // The calendar's fasting profile is authoritative here. A weekly fast
        // may be a local allowance (for example, fish permitted after the
        // Dormition Fast) and therefore need not contain a generic Wednesday /
        // Friday phrase in its title. Major seasons are checked first by
        // evaluate(), so this fallback is reserved for the applicable weekly
        // day and its explicit fasting profile.
        return true;
    }

    private static Family majorFamily(JSONObject day) {
        if (day == null) return Family.NONE;
        JSONObject fasting = day.optJSONObject("fasting");
        if (fasting == null || !fasting.optBoolean("is_fast", false)) return Family.NONE;
        JSONObject verification = fasting.optJSONObject("verification");
        String rule = verification == null ? "" : verification.optString("rule", "").trim();
        // This local fish allowance is after the fourteen-day Dormition Fast.
        // Its title mentions the feast, so exclude it before family detection.
        if ("post_dormition_week_fish".equals(rule)) return Family.NONE;
        String text = fastingSearchText(day);
        if (containsAny(text,
                "dormition fast",
                "dormition feast",
                "صوم السيدة والدة الإله",
                "صوم رقاد",
                "عيد رقاد",
                "νηστεία τῆς κοιμήσεως",
                "νηστεια της κοιμησεως",
                "ἑορτὴ τῆς κοιμήσεως",
                "εορτη της κοιμησεως")) {
            return Family.DORMITION;
        }
        if (containsAny(text,
                "nativity fast",
                "صوم الميلاد",
                "νηστεία τῶν χριστουγέννων",
                "νηστεια των χριστουγεννων")) {
            return Family.NATIVITY;
        }
        if (containsAny(text,
                "apostles’ fast",
                "apostles' fast",
                "apostles fast",
                "صوم الرسل",
                "νηστεία τῶν ἁγίων ἀποστόλων",
                "νηστεια των αγιων αποστολων")) {
            return Family.APOSTLES;
        }
        if (containsAny(text,
                "great lent",
                "holy week",
                "الصوم الكبير",
                "الأسبوع العظيم",
                "الاسبوع العظيم",
                "μεγάλη τεσσαρακοστή",
                "μεγαλη τεσσαρακοστη",
                "μεγάλη ἑβδομάδα",
                "μεγαλη εβδομαδα")) {
            return Family.GREAT_LENT;
        }
        return Family.NONE;
    }

    private static String fastingSearchText(JSONObject day) {
        StringBuilder out = new StringBuilder();
        JSONObject fasting = day.optJSONObject("fasting");
        appendLocalized(out, fasting == null ? null : fasting.optJSONObject("title"));
        appendLocalized(out, fasting == null ? null : fasting.optJSONObject("season"));
        appendLocalized(out, day.optJSONObject("fast"));
        appendLocalized(out, day.optJSONObject("status"));
        return out.toString().toLowerCase(Locale.ROOT);
    }

    private static void appendLocalized(StringBuilder out, JSONObject localized) {
        if (localized == null) return;
        for (String language : new String[]{"ar", "en", "el"}) {
            String value = localized.optString(language, "").trim();
            if (value.isEmpty()) continue;
            if (out.length() > 0) out.append(' ');
            out.append(value);
        }
    }

    private static boolean containsAny(String haystack, String... needles) {
        if (haystack == null || haystack.isEmpty()) return false;
        for (String needle : needles) {
            if (haystack.contains(needle)) return true;
        }
        return false;
    }
}
