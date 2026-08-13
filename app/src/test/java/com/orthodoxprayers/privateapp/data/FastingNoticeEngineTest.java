package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;

import java.time.LocalDate;

import org.json.JSONException;
import org.json.JSONObject;
import org.junit.Test;

public final class FastingNoticeEngineTest {
    private static final LocalDate START = LocalDate.of(2026, 8, 14);
    private static final LocalDate END = LocalDate.of(2026, 8, 27);

    private static JSONObject calendarDay(String isoDate) {
        LocalDate date = LocalDate.parse(isoDate);
        boolean dormition = !date.isBefore(START) && !date.isAfter(END);
        try {
            JSONObject title = new JSONObject()
                    .put("ar", dormition ? "صوم رقاد السيدة والدة الإله" : "لا يوجد صوم")
                    .put("en", dormition ? "Dormition Fast" : "No fast")
                    .put("el", dormition ? "Νηστεία τῆς Κοιμήσεως" : "Χωρὶς νηστεία");
            return new JSONObject().put("fasting", new JSONObject()
                    .put("is_fast", dormition)
                    .put("title", title));
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
}
