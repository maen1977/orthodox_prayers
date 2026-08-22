package com.orthodoxprayers.privateapp.widget;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.view.View;
import android.widget.RemoteViews;

import com.orthodoxprayers.privateapp.MainActivity;
import com.orthodoxprayers.privateapp.OrthodoxPrayersApp;
import com.orthodoxprayers.privateapp.R;
import com.orthodoxprayers.privateapp.data.CommemorationDisplayPolicy;

/** Privacy-preserving home-screen summary; all content is read from the signed local store. */
public final class DailyAgendaWidget extends AppWidgetProvider {
    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] appWidgetIds) {
        for (int appWidgetId : appWidgetIds) updateOne(context, manager, appWidgetId);
    }

    public static void updateAll(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        ComponentName component = new ComponentName(context, DailyAgendaWidget.class);
        int[] ids = manager.getAppWidgetIds(component);
        for (int id : ids) updateOne(context, manager, id);
    }

    private static void updateOne(Context context, AppWidgetManager manager, int widgetId) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.widget_daily_agenda);
        Context application = context.getApplicationContext();
        if (application instanceof OrthodoxPrayersApp) {
            OrthodoxPrayersApp app = (OrthodoxPrayersApp) application;
            org.json.JSONObject current = app.repository().currentDayForDisplay();
            String date = current.optString("date_iso", app.repository().currentAmmanDate());
            String feast = CommemorationDisplayPolicy.displayText(
                    current,
                    app.repository()::localizedValue
            );
            String fast = app.repository().localized(current.optJSONObject("fast"), "—");
            views.setTextViewText(R.id.widget_title, app.repository().local(com.orthodoxprayers.privateapp.R.string.ui_church_prayers_d7f2a5cb));
            views.setTextViewText(R.id.widget_date, date.isEmpty() ? "—" : date);
            views.setTextViewText(R.id.widget_feast, feast);
            views.setViewVisibility(R.id.widget_feast, feast.isEmpty() ? View.GONE : View.VISIBLE);
            views.setTextViewText(R.id.widget_fast, fast.isEmpty() ? "—" : fast);
            views.setTextViewText(R.id.widget_open, app.repository().local(com.orthodoxprayers.privateapp.R.string.ui_open_agenda_a59ab00e));
        }

        Intent open = new Intent(context, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        open.putExtra(MainActivity.EXTRA_SCREEN, "home");
        PendingIntent pending = PendingIntent.getActivity(
                context,
                widgetId,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        views.setOnClickPendingIntent(R.id.widget_root, pending);
        views.setOnClickPendingIntent(R.id.widget_open, pending);
        manager.updateAppWidget(widgetId, views);
    }
}
