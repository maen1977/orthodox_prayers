package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.orthodoxprayers.privateapp.model.LocalizedValue;

import org.json.JSONObject;
import org.junit.Test;

public final class CommemorationDisplayPolicyTest {
    private static final CommemorationDisplayPolicy.Localizer ARABIC = (value, fallback) ->
            new LocalizedValue(value == null ? fallback : value.optString("ar", fallback), false);

    @Test
    public void genericFallbackIsHidden() throws Exception {
        JSONObject day = new JSONObject().put("feast", new JSONObject()
                .put("ar", "تذكار اليوم بحسب التقويم الكنسي القديم")
                .put("en", "Today’s commemoration according to the old church calendar")
                .put("el", "Ἡ σημερινὴ μνήμη κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο"));
        assertEquals("", CommemorationDisplayPolicy.displayText(day, ARABIC));
    }

    @Test
    public void pendingCalendarPlaceholderIsHidden() throws Exception {
        JSONObject day = new JSONObject()
                .put("occasion_status", "PENDING_DAILY_SOURCE_ENRICHMENT")
                .put("feast", new JSONObject().put("ar", "تذكار اليوم يُستكمل من التحديث الموثق"));
        assertEquals("", CommemorationDisplayPolicy.displayText(day, ARABIC));
    }

    @Test
    public void verifiedLocalCommemorationWins() throws Exception {
        JSONObject day = new JSONObject()
                .put("local_commemoration_status", "VERIFIED_LOCAL_PRESENT")
                .put("local_commemoration", new JSONObject()
                        .put("title", new JSONObject().put("ar", "تذكار القديس جاورجيوس")))
                .put("feast", new JSONObject().put("ar", "عيد آخر"));
        assertEquals("تذكار القديس جاورجيوس", CommemorationDisplayPolicy.displayText(day, ARABIC));
    }

    @Test
    public void pinnedRealFeastRemainsVisible() throws Exception {
        JSONObject day = new JSONObject()
                .put("occasion_status", "PINNED_INTERNAL_RULE")
                .put("feast", new JSONObject().put("ar", "عيد الظهور الإلهي المقدس"));
        assertEquals("عيد الظهور الإلهي المقدس", CommemorationDisplayPolicy.displayText(day, ARABIC));
    }

    @Test
    public void unavailableObjectNeverFallsThroughToGenericText() throws Exception {
        JSONObject day = new JSONObject()
                .put("commemoration_status", "UNAVAILABLE_NO_OFFICIAL_SOURCE")
                .put("commemoration", new JSONObject()
                        .put("title", new JSONObject().put("ar", "نص غير موثّق")))
                .put("feast", new JSONObject().put("ar", "تذكار اليوم بحسب التقويم الكنسي القديم"));
        assertEquals("", CommemorationDisplayPolicy.displayText(day, ARABIC));
    }


    @Test
    public void unavailableTranslationIsTreatedAsAbsent() throws Exception {
        JSONObject day = new JSONObject().put("feast", new JSONObject().put("ar", "تذكار موثق بالعربية فقط"));
        CommemorationDisplayPolicy.Localizer unavailable = (value, fallback) ->
                new LocalizedValue("The official native English text is not available for this section.", true);
        assertEquals("", CommemorationDisplayPolicy.displayText(day, unavailable));
    }

    @Test
    public void statusAndGenericClassifiersAreFailClosed() {
        assertTrue(CommemorationDisplayPolicy.isUnavailableStatus("NO_VERIFIED_LOCAL_RECORD"));
        assertTrue(CommemorationDisplayPolicy.isUnavailableStatus("pending_source"));
        assertFalse(CommemorationDisplayPolicy.isDisplayableText("  "));
        assertTrue(CommemorationDisplayPolicy.isDisplayableText("القديس الشهيد فلان"));
    }
}
