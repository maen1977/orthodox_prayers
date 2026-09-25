package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.time.LocalDate;

import org.json.JSONException;
import org.json.JSONObject;
import org.junit.Test;

public final class FastingNoticeEngineTest {
    private static final LocalDate START = LocalDate.of(2026, 8, 14);
    private static final LocalDate END = LocalDate.of(2026, 8, 27);
    private static final LocalDate FEAST = LocalDate.of(2026, 8, 28);

    private static JSONObject calendarDay(String isoDate) {
        LocalDate date = LocalDate.parse(isoDate);
        boolean dormition = !date.isBefore(START) && !date.isAfter(END);
        boolean feast = date.equals(FEAST);
        try {
            JSONObject title = new JSONObject()
                    .put("ar", dormition ? "صوم رقاد السيدة والدة الإله" : feast ? "عيد رقاد والدة الإله بعد صوم أربعة عشر يومًا" : "لا يوجد صوم")
                    .put("en", dormition ? "Dormition Fast" : feast ? "Dormition Feast after the fourteen-day fast" : "No fast")
                    .put("el", dormition ? "Νηστεία τῆς Κοιμήσεως" : feast ? "Ἑορτὴ τῆς Κοιμήσεως μετὰ δεκατετραήμερη νηστεία" : "Χωρὶς νηστεία");
            return new JSONObject().put("fasting", new JSONObject()
                    .put("is_fast", dormition || feast)
                    .put("title", title)
                    .put("verification", new JSONObject().put("rule", feast ? "dormition_feast_fish" : dormition ? "dormition_strict" : "ordinary_fast_free")));
        } catch (JSONException error) {
            throw new AssertionError("Test fixture must create valid fasting JSON", error);
        }
    }

    @Test
    public void dormitionNoticeMovesThroughEveryCompactHomeState() {
        FastingNoticeEngine.DayProvider provider = FastingNoticeEngineTest::calendarDay;

        FastingNoticeEngine.Notice tomorrow = FastingNoticeEngine.evaluate(
                LocalDate.of(2026, 8, 13), provider);
        assertEquals(FastingNoticeEngine.Kind.UPCOMING_MAJOR_FAST, tomorrow.kind);
        assertEquals(1, tomorrow.daysUntilStart);

        FastingNoticeEngine.Notice first = FastingNoticeEngine.evaluate(START, provider);
        assertEquals(FastingNoticeEngine.Kind.CURRENT_MAJOR_FAST, first.kind);
        assertEquals(FastingNoticeEngine.Family.DORMITION, first.family);
        assertEquals(1, first.dayNumber);
        assertEquals(13, first.daysRemaining);

        FastingNoticeEngine.Notice threeDays = FastingNoticeEngine.evaluate(
                LocalDate.of(2026, 8, 24), provider);
        assertEquals(3, threeDays.daysRemaining);

        FastingNoticeEngine.Notice oneDay = FastingNoticeEngine.evaluate(
                LocalDate.of(2026, 8, 26), provider);
        assertEquals(1, oneDay.daysRemaining);

        FastingNoticeEngine.Notice last = FastingNoticeEngine.evaluate(END, provider);
        assertEquals(0, last.daysRemaining);
        assertEquals(14, last.dayNumber);
    }

    @Test
    public void dormitionFeastOnFridayIsOutsideTheFourteenDayPeriod() {
        FastingNoticeEngine.DayProvider provider = FastingNoticeEngineTest::calendarDay;

        FastingNoticeEngine.Notice feast = FastingNoticeEngine.evaluate(FEAST, provider);

        assertEquals(FastingNoticeEngine.Kind.CURRENT_MAJOR_FAST, feast.kind);
        assertEquals(FastingNoticeEngine.Family.DORMITION, feast.family);
        assertTrue(feast.feastDay);
        assertEquals(START, feast.startDate);
        assertEquals(END, feast.endDate);
        assertEquals(14, feast.totalDays);
        assertEquals(14, feast.dayNumber);
        assertEquals(0, feast.daysRemaining);
    }

    @Test
    public void tomorrowWednesdayFastIsAnnouncedFromTuesday() {
        FastingNoticeEngine.DayProvider provider = isoDate -> {
            LocalDate date = LocalDate.parse(isoDate);
            if (date.equals(LocalDate.of(2026, 9, 2))) return weeklyFastDay("صوم الأربعاء");
            return calendarDay(isoDate);
        };

        FastingNoticeEngine.Notice notice = FastingNoticeEngine.evaluate(
                LocalDate.of(2026, 9, 1), provider);

        assertEquals(FastingNoticeEngine.Kind.UPCOMING_WEEKLY_FAST, notice.kind);
        assertEquals(LocalDate.of(2026, 9, 2), notice.targetDate);
        assertEquals(1, notice.daysUntilStart);
    }

    @Test
    public void tomorrowFridayFastIsAnnouncedFromThursday() {
        FastingNoticeEngine.DayProvider provider = isoDate -> {
            LocalDate date = LocalDate.parse(isoDate);
            if (date.equals(LocalDate.of(2026, 9, 4))) return weeklyFastDay("صوم الجمعة");
            return calendarDay(isoDate);
        };

        FastingNoticeEngine.Notice notice = FastingNoticeEngine.evaluate(
                LocalDate.of(2026, 9, 3), provider);

        assertEquals(FastingNoticeEngine.Kind.UPCOMING_WEEKLY_FAST, notice.kind);
        assertEquals(LocalDate.of(2026, 9, 4), notice.targetDate);
        assertEquals(1, notice.daysUntilStart);
    }

    private static JSONObject weeklyFastDay(String titleAr) {
        try {
            return new JSONObject().put("fasting", new JSONObject()
                    .put("is_fast", true)
                    .put("title", new JSONObject().put("ar", titleAr)
                            .put("en", "Weekly fast")
                            .put("el", "Ἑβδομαδιαία νηστεία"))
                    .put("verification", new JSONObject().put("rule", "ordinary_weekly_fast")));
        } catch (JSONException error) {
            throw new AssertionError(error);
        }
    }

    @Test
    public void ordinaryDormitionDayIsNotMarkedAsTheFeast() {
        FastingNoticeEngine.DayProvider provider = FastingNoticeEngineTest::calendarDay;

        FastingNoticeEngine.Notice last = FastingNoticeEngine.evaluate(END, provider);

        assertFalse(last.feastDay);
        assertEquals(14, last.totalDays);
        assertEquals(14, last.dayNumber);
    }

    @Test
    public void postDormitionFishAllowanceDoesNotExtendDormitionCountdown() {
        FastingNoticeEngine.DayProvider provider = isoDate -> {
            LocalDate date = LocalDate.parse(isoDate);
            if (date.equals(LocalDate.of(2026, 9, 2)) || date.equals(LocalDate.of(2026, 9, 4))) {
                try {
                    return new JSONObject().put("fasting", new JSONObject()
                            .put("is_fast", true)
                            .put("title", new JSONObject()
                                    .put("ar", "الأسبوع الأول بعد عيد رقاد السيدة والدة الإله")
                                    .put("en", "Post-Dormition week — Fish, oil, and wine permitted"))
                            .put("verification", new JSONObject().put("rule", "post_dormition_week_fish")));
                } catch (JSONException error) {
                    throw new AssertionError(error);
                }
            }
            return calendarDay(isoDate);
        };

        FastingNoticeEngine.Notice notice = FastingNoticeEngine.evaluate(
                LocalDate.of(2026, 9, 2), provider);

        assertEquals(FastingNoticeEngine.Kind.UPCOMING_WEEKLY_FAST, notice.kind);
        assertEquals(LocalDate.of(2026, 9, 4), notice.targetDate);
        assertEquals(2, notice.daysUntilStart);
        assertEquals(0, notice.daysRemaining);
        assertFalse(notice.feastDay);
    }
}
