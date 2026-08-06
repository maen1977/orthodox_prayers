using System.Net;
using System.Text;
using System.Text.Json;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class AutomaticCleanupReportService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true
    };

    public static string ReportsDirectory { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "SafeWindowsCleaner",
        "AutomaticReports");

    public async Task<AutomaticCleanupReportResult> CreateAsync(
        AutomaticCleanupResult result,
        CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(ReportsDirectory);
        string stamp = result.StartedAt.ToLocalTime().ToString("yyyyMMdd-HHmmss");
        string jsonPath = Path.Combine(ReportsDirectory, $"automatic-cleanup-{stamp}.json");
        string htmlPath = Path.Combine(ReportsDirectory, $"automatic-cleanup-{stamp}.html");
        result.HtmlReportPath = htmlPath;
        result.JsonReportPath = jsonPath;

        await File.WriteAllTextAsync(
            jsonPath,
            JsonSerializer.Serialize(result, JsonOptions),
            new UTF8Encoding(false),
            cancellationToken);
        await File.WriteAllTextAsync(
            htmlPath,
            BuildHtml(result),
            new UTF8Encoding(false),
            cancellationToken);

        return new AutomaticCleanupReportResult(htmlPath, jsonPath);
    }

    private static string BuildHtml(AutomaticCleanupResult result)
    {
        string code = LocalizationService.NormalizeLanguage(result.LanguageCode);
        bool rtl = code == "ar";
        IFormatProvider culture = LocalizationService.CultureFor(code);
        string T(string key) => LocalizationService.T(key, code);
        string Translate(string value) => LocalizationService.Translate(value, code);
        string N(int value) => value.ToString("N0", culture);

        string status = result.Cancelled
            ? T("@Cancelled")
            : result.PreviewOnly ? T("@PreviewCompleted") : T("@Completed");
        string duration = result.CompletedAt > result.StartedAt
            ? (result.CompletedAt - result.StartedAt).ToString(@"hh\:mm\:ss", culture)
            : "—";

        var html = new StringBuilder();
        html.Append($"<!doctype html><html lang=\"{Encode(code)}\" dir=\"{(rtl ? "rtl" : "ltr")}\"><head><meta charset=\"utf-8\">");
        html.Append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">");
        html.Append($"<title>{Encode(T("@ReportTitle"))}</title>");
        html.Append("<style>body{font-family:Segoe UI,Tahoma,Arial,sans-serif;background:#f4f7fb;color:#172033;margin:0;padding:28px}.box{max-width:1060px;margin:auto}.card{background:#fff;border:1px solid #d9e1ec;border-radius:14px;padding:20px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.metric{background:#eef3fa;border-radius:10px;padding:14px}.value{font-size:24px;font-weight:700;color:#2563eb}.muted{color:#667085}.ok{color:#15803d}.warn{color:#b45309}li{margin:7px 0}code,.ltr{direction:ltr;unicode-bidi:embed}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #e5e7eb;padding:9px;text-align:start}th{background:#f8fafc}</style></head><body><div class=\"box\">");
        html.Append($"<h1>{Encode(status)}</h1><p class=\"muted\">{Encode(T("@Publisher"))}: {Encode(PublisherInfo.GetDisplayName(code))} — {Encode(PublisherInfo.Phone)}<br>{Encode(T("@Started"))}: {Encode(result.StartedAt.ToLocalTime().ToString("G", culture))} — {Encode(T("@Duration"))}: {Encode(duration)}</p>");

        html.Append("<div class=\"grid\">");
        AppendMetric(html, T("@DiskFreed"), result.DiskFreedText);
        AppendMetric(html, T("@OrphansQuarantined"), SizeFormatter.Format(result.OrphanBytesQuarantined, code));
        AppendMetric(html, T("@TemporaryFiles"), N(result.TemporaryDeletedFiles));
        AppendMetric(html, T("@RegistryFixed"), N(result.BrokenRegistryEntriesDisabled + result.BrokenStartupItemsDisabled));
        html.Append("</div>");

        html.Append($"<div class=\"card\"><h2>{Encode(T("@Details"))}</h2><ul>");
        html.Append($"<li>{Encode(Translate($"الكاش والملفات المؤقتة: حُذف {N(result.TemporaryDeletedFiles)}، تعذر {N(result.TemporaryFailedFiles)}، المساحة {SizeFormatter.Format(result.TemporaryFreedBytes, code)}."))}</li>");
        html.Append($"<li>{Encode(Translate($"بقايا البرامج: عُثر على {N(result.OrphanCandidatesFound)}، نُقل للحجر {N(result.OrphansQuarantined)}، تعذر {N(result.OrphansFailed)}، تم تجاوز {N(result.OrphansSkipped)}."))}</li>");
        html.Append($"<li>{Encode(Translate($"عناصر بدء التشغيل المكسورة: عُثر على {N(result.BrokenRegistryEntriesFound + result.BrokenStartupItemsFound)}، عُطّل بأمان {N(result.BrokenRegistryEntriesDisabled + result.BrokenStartupItemsDisabled)}، تعذر {N(result.StartupItemsFailed)}."))}</li>");
        html.Append($"<li>{Encode(Translate(result.RestorePointMessage.Length == 0 ? "نقطة الاستعادة: لم تُطلب." : $"نقطة الاستعادة: {result.RestorePointMessage}"))}</li>");
        html.Append("</ul></div>");

        AppendList(html, T("@ActionsPerformed"), result.Actions.Select(Translate).ToArray(), "ok", code);
        AppendList(html, T("@SkippedForSafety"), result.SkippedItems.Select(Translate).ToArray(), "muted", code);
        AppendList(html, T("@Warnings"), result.Warnings.Select(Translate).ToArray(), "warn", code);

        html.Append("</div></body></html>");
        return html.ToString();
    }

    private static void AppendMetric(StringBuilder html, string label, string value)
        => html.Append($"<div class=\"metric\"><div class=\"muted\">{Encode(label)}</div><div class=\"value\">{Encode(value)}</div></div>");

    private static void AppendHeader(StringBuilder html, string value)
        => html.Append($"<th>{Encode(value)}</th>");

    private static void AppendCell(StringBuilder html, string value)
        => html.Append($"<td>{Encode(value)}</td>");

    private static void AppendList(
        StringBuilder html,
        string title,
        IReadOnlyCollection<string> items,
        string cssClass,
        string languageCode)
    {
        if (items.Count == 0)
        {
            return;
        }

        html.Append($"<div class=\"card\"><h2 class=\"{cssClass}\">{Encode(title)}</h2><ul>");
        foreach (string item in items.Take(200))
        {
            html.Append($"<li>{Encode(item)}</li>");
        }

        if (items.Count > 200)
        {
            string extra = languageCode == "ar"
                ? $"و{items.Count - 200:N0} عنصر إضافي محفوظ في تقرير JSON."
                : $"And {items.Count - 200:N0} additional items saved in the JSON report.";
            html.Append($"<li>{Encode(extra)}</li>");
        }

        html.Append("</ul></div>");
    }

    private static string Encode(string value) => WebUtility.HtmlEncode(value);
}
