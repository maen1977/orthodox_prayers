package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

public final class RollingPackageDateAcceptanceTest {
    @Test
    public void packageAnchoredYesterdayContainsToday() throws Exception {
        JSONObject packagePayload = packageFromAugust5Through13();
        assertTrue(DataRepository.hasRollingWindow(packagePayload));
        assertTrue(DataRepository.rollingPackageContainsDate(packagePayload, "2026-08-06"));
        assertTrue(DataRepository.rollingPackageContainsDate(packagePayload, "2026-08-13"));
    }

    @Test
    public void packageRejectsDatesOutsideSignedWindow() throws Exception {
        JSONObject packagePayload = packageFromAugust5Through13();
        assertFalse(DataRepository.rollingPackageContainsDate(packagePayload, "2026-08-04"));
        assertFalse(DataRepository.rollingPackageContainsDate(packagePayload, "2026-08-14"));
    }

    private static JSONObject packageFromAugust5Through13() throws Exception {
        JSONObject root = new JSONObject();
        root.put("date_iso", "2026-08-05");
        root.put("rolling_week", new JSONObject()
                .put("schema_version", 2)
                .put("policy", "ROLLING_FUTURE_WINDOW")
                .put("start_date", "2026-08-05")
                .put("end_date", "2026-08-13")
                .put("day_count", 9)
                .put("status", "COMPLETE")
                .put("fail_closed", true));
        JSONArray days = new JSONArray();
        for (int day = 6; day <= 13; day++) {
            days.put(new JSONObject().put("date_iso", String.format("2026-08-%02d", day)));
        }
        root.put("weekly_days", days);
        return root;
    }
}
