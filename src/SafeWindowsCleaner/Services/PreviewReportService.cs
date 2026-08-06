using System.Net;
using System.Text;
using System.Text.Json;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class PreviewReportService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true
    };

    public static string ReportsDirectory { get; } = Path.Combine(SettingsService.DataDirectory, "Reports");

    public async Task<PreviewReportResult> CreateAsync(OperationPreview preview, CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(ReportsDirectory);
        string safeOperation = SanitizeFileName(preview.Operation);
        string baseName = $"preview-{DateTime.Now:yyyyMMdd-HHmmss}-{safeOperation}-{Guid.NewGuid():N}";
        string jsonPath = Path.Combine(ReportsDirectory, baseName + ".json");
        string htmlPath = Path.Combine(ReportsDirectory, baseName + ".html");

        await File.WriteAllTextAsync(jsonPath, JsonSerializer.Serialize(preview, JsonOptions), Encoding.UTF8, cancellationToken);
        await File.WriteAllTextAsync(htmlPath, BuildHtml(preview), Encoding.UTF8, cancellationToken);
        return new(jsonPath, htmlPath);
    }

    private static string BuildHtml(OperationPreview preview)
    {
        string code = LocalizationService.ActiveLanguageCode;
        bool rtl = code == "ar";
        IFormatProvider culture = LocalizationService.CultureFor(code);
        string T(string key) => LocalizationService.T(key, code);
        string L(string? value) => LocalizationService.Translate(value, code);
        static string E(string? value) => WebUtility.HtmlEncode(value ?? string.Empty);

        var builder = new StringBuilder();
        builder.Append($"<!doctype html><html lang=\"{E(code)}\" dir=\"{(rtl ? "rtl" : "ltr")}\"><head><meta charset=\"utf-8\">");
        builder.Append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">");
        builder.Append($"<title>{E(T("@PreviewReportTitle"))} - {E(L(preview.Operation))}</title>");
        builder.Append("<style>body{font-family:Segoe UI,Tahoma,Arial,sans-serif;margin:32px;color:#202124;background:#f7f8fa}main{max-width:1100px;margin:auto;background:white;padding:28px;border-radius:14px;box-shadow:0 3px 18px #0002}h1{margin-top:0}dl{display:grid;grid-template-columns:180px 1fr;gap:8px 16px}dt{font-weight:600}table{border-collapse:collapse;width:100%;margin-top:20px}th,td{border:1px solid #ddd;padding:9px;text-align:start;vertical-align:top}th{background:#f0f2f5}.note{padding:12px;background:#fff4ce;border:1px solid #e7c85d;border-radius:8px}</style></head><body><main>");
        builder.Append($"<h1>{E(T("@PreviewReportTitle"))}</h1><p class=\"note\">{E(T("@PreviewOnlyNotice"))}</p><dl>");
        builder.Append($"<dt>{E(L("العملية"))}</dt><dd>{E(L(preview.Operation))}</dd>");
        builder.Append($"<dt>{E(L("الوصف"))}</dt><dd>{E(L(preview.Description))}</dd>");
        builder.Append($"<dt>{E(T("@ReportTime"))}</dt><dd>{E(preview.CreatedAtUtc.LocalDateTime.ToString("G", culture))}</dd>");
        builder.Append($"<dt>{E(L("العناصر"))}</dt><dd>{preview.ItemCount.ToString("N0", culture)}</dd>");
        builder.Append($"<dt>{E(L("الحجم التقريبي"))}</dt><dd>{E(SizeFormatter.Format(preview.EstimatedBytes, code))}</dd>");
        builder.Append($"<dt>{E(T("@RiskLevel"))}</dt><dd>{E(L(preview.RiskLevel))}</dd>");
        builder.Append($"<dt>{E(T("@AdministratorPermission"))}</dt><dd>{E(preview.RequiresAdministrator ? T("@MayBeRequired") : T("@NotExpected"))}</dd></dl>");
        builder.Append($"<table><thead><tr><th>{E(L("العنصر"))}</th><th>{E(T("@ProposedAction"))}</th><th>{E(L("الموقع"))}</th><th>{E(L("الأمان"))}</th><th>{E(L("الحجم"))}</th></tr></thead><tbody>");
        foreach (OperationPreviewItem item in preview.Items)
        {
            builder.Append($"<tr><td>{E(L(item.Name))}</td><td>{E(L(item.Action))}</td><td>{E(item.Location)}</td><td>{E(L(item.Safety))}</td><td>{E(SizeFormatter.Format(item.SizeBytes, code))}</td></tr>");
        }

        builder.Append($"</tbody></table><p>{E(T("@Publisher"))}: {E(PublisherInfo.GetDisplayName(code))} — {E(PublisherInfo.Phone)}</p></main></body></html>");
        return builder.ToString();
    }

    private static string SanitizeFileName(string value)
    {
        string sanitized = string.Concat((value ?? string.Empty).Select(character =>
            Path.GetInvalidFileNameChars().Contains(character) || char.IsWhiteSpace(character) ? '-' : character));
        sanitized = sanitized.Trim('-');
        if (string.IsNullOrWhiteSpace(sanitized))
        {
            sanitized = "operation";
        }

        return sanitized.Length <= 50 ? sanitized : sanitized[..50];
    }
}
