package com.orthodoxprayers.privateapp.ui;

import android.content.Context;
import android.content.res.Configuration;
import android.content.res.Resources;

import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** Resolves app-owned strings in the language selected inside the app. */
public final class LocalizedResources {
    private static final Map<String, Resources> CACHE = new ConcurrentHashMap<>();

    private LocalizedResources() { }

    public static String get(Context context, String language, int resourceId) {
        return resources(context, language).getString(resourceId);
    }

    public static String format(Context context, String language, int resourceId, Object... arguments) {
        return resources(context, language).getString(resourceId, arguments);
    }

    private static Resources resources(Context context, String language) {
        String normalized = normalizeLanguage(language);
        String cacheKey = context.getPackageName() + ":" + normalized;
        Resources resources = CACHE.get(cacheKey);
        if (resources == null) {
            Locale locale = Locale.forLanguageTag(normalized);
            Configuration configuration = new Configuration(context.getResources().getConfiguration());
            configuration.setLocale(locale);
            configuration.setLayoutDirection(locale);
            Context localized = context.getApplicationContext().createConfigurationContext(configuration);
            resources = localized.getResources();
            CACHE.put(cacheKey, resources);
        }
        return resources;
    }

    private static String normalizeLanguage(String language) {
        if ("en".equals(language)) return "en";
        if ("el".equals(language)) return "el";
        return "ar";
    }
}
