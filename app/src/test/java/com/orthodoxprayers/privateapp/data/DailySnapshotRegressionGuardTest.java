package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.junit.Test;

public final class DailySnapshotRegressionGuardTest {
    @Test
    public void acceptsASecondWindowThatAddsMatinsGospel() throws JSONException {
        JSONObject accepted = day(
                reading("epistle", "Romans", "Epistle text"),
                reading("gospel", "Matthew", "Gospel text")
        );
        JSONObject candidate = day(
                reading("matins_gospel", "John", "Matins text"),
                reading("epistle", "Romans", "Epistle text"),
                reading("gospel", "Matthew", "Corrected Gospel text")
        );

        assertEquals("", DailySnapshotRegressionGuard.firstRegression(
                accepted, candidate, "en"
        ));
    }

    @Test
    public void rejectsASecondWindowThatDropsAcceptedReadingText() throws JSONException {
        JSONObject accepted = day(
                reading("epistle", "Romans", "Epistle text"),
                reading("gospel", "Matthew", "Gospel text")
        );
        JSONObject candidate = day(
                reading("epistle", "Romans", "Epistle text"),
                reading("gospel", "Matthew", "")
        );

        assertEquals(
                "same_day_content_regression:gospel:body",
                DailySnapshotRegressionGuard.firstRegression(accepted, candidate, "en")
        );
    }

    @Test
    public void doesNotCompareDifferentDates() throws JSONException {
        JSONObject accepted = day(reading("gospel", "Matthew", "Gospel text"));
        JSONObject candidate = day(reading("gospel", "", ""));
        candidate.put("date_iso", "2026-07-26");
        assertEquals("", DailySnapshotRegressionGuard.firstRegression(
                accepted, candidate, "en"
        ));
    }

    private static JSONObject day(JSONObject... readings) throws JSONException {
        JSONArray array = new JSONArray();
        for (JSONObject reading : readings) array.put(reading);
        return new JSONObject()
                .put("date_iso", "2026-07-25")
                .put("readings", array)
                .put("services", new JSONArray());
    }

    private static JSONObject reading(
            String kind,
            String reference,
            String body
    ) throws JSONException {
        return new JSONObject()
                .put("kind", kind)
                .put("reference", localized(reference))
                .put("body", localized(body));
    }

    private static JSONObject localized(String value) throws JSONException {
        return new JSONObject().put("ar", "").put("en", value).put("el", "");
    }
}
