package com.orthodoxprayers.privateapp.ui.screens;

import android.view.View;
import android.widget.LinearLayout;

import com.orthodoxprayers.privateapp.data.FastingNoticeEngine;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

import org.json.JSONObject;

import java.time.LocalDate;

/**
 * A deliberately small fasting details page opened from the Home fasting notice.
 * It keeps the full calendar-day screen available from the calendar itself.
 */
public final class FastingSummaryScreen extends BaseScreen {
    private final String date;

    public FastingSummaryScreen(ScreenHost host, String date) {
        super(host);
        this.date = date == null ? "" : date.trim();
    }

    @Override
    public View createView() {
        UiKit.Page page = page(local(com.orthodoxprayers.privateapp.R.string.ui_fasting_summary_title_r66), true);
        JSONObject item = findDay();
        if (item == null) {
            add(page.root, centered(
                    local(com.orthodoxprayers.privateapp.R.string.ui_no_trusted_details_for_this_date_are_included_in_dfb3006c),
                    16,
                    ui.colors().secondaryText(),
                    false
            ), 30, 30);
            return page.scroll;
        }

        JSONObject fasting = item.optJSONObject("fasting");
        if (!isFastingDay(fasting)) {
            LinearLayout card = ui.card();
            card.addView(centered(
                    local(com.orthodoxprayers.privateapp.R.string.ui_fast_summary_no_fast),
                    17,
                    ui.colors().secondaryText(),
                    true
            ));
            add(page.root, card, 16, 16);
            return page.scroll;
        }

        LinearLayout card = ui.card();
        String title = localized(fasting.optJSONObject("title"), fastingDisplayTitle(item, date));
        addField(card, local(com.orthodoxprayers.privateapp.R.string.ui_fast_summary_type), title);

        FastingPeriod period = fastingPeriod();
        if (period != null) {
            addField(card,
                    local(com.orthodoxprayers.privateapp.R.string.ui_fast_summary_period),
                    localFormat(
                            com.orthodoxprayers.privateapp.R.string.ui_fast_summary_period_format,
                            dayLabel(period.start),
                            dayLabel(period.end)
                    )
            );
            addField(card,
                    local(com.orthodoxprayers.privateapp.R.string.ui_fast_summary_days),
                    localFormat(
                            com.orthodoxprayers.privateapp.R.string.ui_fast_summary_days_format,
                            period.totalDays
                    )
            );
        }

        JSONObject guidance = fasting.optJSONObject("guidance");
        if (guidance != null) {
            addField(card,
                    local(com.orthodoxprayers.privateapp.R.string.ui_fast_summary_allowed),
                    localized(guidance.optJSONObject("allowed_summary"), "")
            );
            addField(card,
                    local(com.orthodoxprayers.privateapp.R.string.ui_fast_summary_forbidden),
                    localized(guidance.optJSONObject("forbidden_summary"), "")
            );
        }

        if (card.getChildCount() == 0) {
            card.addView(ui.text(
                    local(com.orthodoxprayers.privateapp.R.string.ui_fast_summary_details_unavailable),
                    14,
                    ui.colors().secondaryText(),
                    false
            ));
        }
        add(page.root, card, 12, 16);
        return page.scroll;
    }

    private JSONObject findDay() {
        return data.calendarDay(date);
    }

    private void addField(LinearLayout card, String label, String value) {
        if (value == null || value.trim().isEmpty()) return;
        card.addView(ui.text(label + ":\n" + value, 15, ui.colors().primaryText(), false),
                ui.margins(-1, -2, 0, 9, 0, 0));
    }

    private FastingPeriod fastingPeriod() {
        LocalDate target = parseDate(date);
        if (target == null) return null;

        FastingNoticeEngine.Notice notice = FastingNoticeEngine.evaluate(
                target,
                isoDate -> data.calendarDay(isoDate)
        );
        if (notice.kind == FastingNoticeEngine.Kind.CURRENT_MAJOR_FAST
                && notice.startDate != null
                && notice.endDate != null) {
            return new FastingPeriod(notice.startDate, notice.endDate, notice.totalDays);
        }

        // Weekly fasts do not have a multi-day season; the selected day is the period.
        return new FastingPeriod(target, target, 1);
    }

    private LocalDate parseDate(String value) {
        try {
            return LocalDate.parse(value);
        } catch (Exception ignored) {
            return null;
        }
    }

    private String dayLabel(LocalDate value) {
        if (value == null) return "";
        JSONObject item = data.calendarDay(value.toString());
        if (item != null) {
            String label = localized(item.optJSONObject("date_label"), "").trim();
            if (!label.isEmpty()) return label;
        }
        return value.toString();
    }

    private static final class FastingPeriod {
        final LocalDate start;
        final LocalDate end;
        final int totalDays;

        FastingPeriod(LocalDate start, LocalDate end, int totalDays) {
            this.start = start;
            this.end = end;
            this.totalDays = Math.max(1, totalDays);
        }
    }
}
