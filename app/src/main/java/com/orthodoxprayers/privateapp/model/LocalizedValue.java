package com.orthodoxprayers.privateapp.model;

public final class LocalizedValue {
    public final String text;
    public final boolean translationUnavailable;

    public LocalizedValue(String text, boolean translationUnavailable) {
        this.text = text == null ? "" : text;
        this.translationUnavailable = translationUnavailable;
    }
}
