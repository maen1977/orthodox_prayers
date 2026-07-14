package com.orthodoxprayers.privateapp.model;

import org.json.JSONObject;

public final class SearchResult {
    public final JSONObject service;
    public final String snippet;
    public final String matchedSection;
    public final int score;

    public SearchResult(JSONObject service, String snippet, String matchedSection, int score) {
        this.service = service;
        this.snippet = snippet == null ? "" : snippet;
        this.matchedSection = matchedSection == null ? "" : matchedSection;
        this.score = score;
    }
}
