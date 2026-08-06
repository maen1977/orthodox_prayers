package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.lang.reflect.Method;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

public final class ThanksgivingVariantSelectionTest {
    @Test
    public void arabicStJohnShowsOnlyItsOwnTroparion() throws Exception {
        String visible = selectArabic("divine_liturgy");
        assertTrue(visible.contains("طروبارية القديس يوحنا الذهبي الفم"));
        assertTrue(visible.contains("نص يوحنا"));
        assertFalse(visible.contains("عند إقامة قداس"));
        assertFalse(visible.contains("نص باسيليوس"));
        assertFalse(visible.contains("نص السابق تقديسه"));
    }

    @Test
    public void arabicBasilShowsOnlyItsOwnTroparion() throws Exception {
        String visible = selectArabic("divine_liturgy_basil");
        assertTrue(visible.contains("طروبارية القديس باسيليوس الكبير"));
        assertTrue(visible.contains("نص باسيليوس"));
        assertFalse(visible.contains("عند إقامة قداس"));
        assertFalse(visible.contains("نص يوحنا"));
        assertFalse(visible.contains("نص السابق تقديسه"));
    }

    @Test
    public void arabicPresanctifiedShowsOnlyItsOwnTroparion() throws Exception {
        String visible = selectArabic("presanctified_liturgy");
        assertTrue(visible.contains("طروبارية القديس غريغوريوس الكبير"));
        assertTrue(visible.contains("نص السابق تقديسه"));
        assertFalse(visible.contains("عند إقامة قداس"));
        assertFalse(visible.contains("نص يوحنا"));
        assertFalse(visible.contains("نص باسيليوس"));
    }

    private static String selectArabic(String liturgyId) throws Exception {
        JSONObject thanksgiving = new JSONObject().put("segments", new JSONArray()
                .put(section("صلوات مشتركة"))
                .put(text("نص مشترك"))
                .put(section("عند إقامة قداس القديس يوحنا الذهبي الفم"))
                .put(note("يقال هذا الفرع عند إقامة قداس القديس يوحنا الذهبي الفم."))
                .put(text("نص يوحنا"))
                .put(section("عند إقامة قداس القديس باسيليوس الكبير"))
                .put(note("يقال هذا الفرع عند إقامة قداس القديس باسيليوس الكبير."))
                .put(text("نص باسيليوس"))
                .put(section("عند إقامة قداس السابق تقديسه"))
                .put(note("يقال هذا الفرع عند إقامة قداس السابق تقديسه."))
                .put(text("نص السابق تقديسه"))
                .put(text("ختام مشترك")));

        Method selector = DataRepository.class.getDeclaredMethod(
                "thanksgivingSegmentsForLiturgy",
                JSONObject.class,
                String.class,
                String.class
        );
        selector.setAccessible(true);
        JSONArray selected = (JSONArray) selector.invoke(null, thanksgiving, "ar", liturgyId);
        return selected.toString();
    }

    private static JSONObject section(String title) throws Exception {
        return new JSONObject()
                .put("type", "section")
                .put("title", new JSONObject().put("ar", title).put("en", "").put("el", ""));
    }

    private static JSONObject note(String value) throws Exception {
        return new JSONObject()
                .put("type", "note")
                .put("text", new JSONObject().put("ar", value).put("en", "").put("el", ""));
    }

    private static JSONObject text(String value) throws Exception {
        return new JSONObject()
                .put("type", "text")
                .put("text", new JSONObject().put("ar", value).put("en", "").put("el", ""));
    }
}
