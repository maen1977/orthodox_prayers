package com.orthodoxprayers.privateapp.data;

import static org.junit.Assert.assertEquals;

import java.util.Arrays;

import org.junit.Test;

public final class DailyDataEndpointPolicyTest {
    private static final String TODAY = "https://raw.githubusercontent.com/maen1977/orthodox_prayers/verified-data/data/calendar/today.json";
    private static final String SIGNATURE = TODAY + ".sig";

    @Test
    public void triesExactDatedFileBeforeTodayAlias() {
        assertEquals(
                Arrays.asList(
                        "https://raw.githubusercontent.com/maen1977/orthodox_prayers/verified-data/data/calendar/2026-07-13.json",
                        TODAY
                ),
                DailyDataEndpointPolicy.jsonCandidates(TODAY, "2026-07-13")
        );
    }

    @Test
    public void derivesMatchingDetachedSignatureForDatedFile() {
        String dated = DailyDataEndpointPolicy.jsonCandidates(TODAY, "2026-07-13").get(0);
        assertEquals(dated + ".sig", DailyDataEndpointPolicy.signatureUrl(TODAY, SIGNATURE, dated));
        assertEquals(SIGNATURE, DailyDataEndpointPolicy.signatureUrl(TODAY, SIGNATURE, TODAY));
    }
}
