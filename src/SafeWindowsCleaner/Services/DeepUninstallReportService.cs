using System.Net;
using System.Text;
using System.Text.Json;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class DeepUninstallReportService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static string ReportsDirectory { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "SafeWindowsCleaner",
        "DeepUninstallReports");

    public async Task<DeepUninstallReportResult> CreateAsync(
        DeepUninstallResult result,
        CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(ReportsDirectory);
        string stamp = result.StartedAt.ToLocalTime().ToString("yyyyMMdd-HHmmss");
        string safeName = SanitizeFileName(result.ApplicationName);
        string jsonPath = Path.Combine(ReportsDirectory, $"deep-uninstall-{safeName}-{stamp}.json");
        string htmlPath = Path.Combine(ReportsDirectory, $"deep-uninstall-{safeName}-{stamp}.html");
        result.JsonReportPath = jsonPath;
        result.HtmlReportPath = htmlPath;

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
        return new DeepUninstallReportResult(htmlPath, jsonPath);
    }

    private static string BuildHtml(DeepUninstallResult result)
    {
        string code = LocalizationService.NormalizeLanguage(result.LanguageCode);
        bool rtl = code == "ar";
        IFormatProvider culture = LocalizationService.CultureFor(code);
        string T(string key) => LocalizationService.T(key, code);
        string N(int value) => value.ToString("N0", culture);

        var html = new StringBuilder();
        html.Append($"<!doctype html><html lang=\"{Encode(code)}\" dir=\"{(rtl ? "rtl" : "ltr")}\"><head><meta charset=\"utf-8\">");
        html.Append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">");
        html.Append($"<title>{Encode(T("@DeepUninstallReport"))}</title>");
        html.Append("<style>body{font-family:Segoe UI,Tahoma,Arial,sans-serif;background:#f4f7fb;color:#172033;margin:0;padding:28px}.box{max-width:1120px;margin:auto}.card{background:#fff;border:1px solid #d9e1ec;border-radius:14px;padding:20px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric{background:#eef3fa;border-radius:10px;padding:14px}.value{font-size:22px;font-weight:700;color:#2563eb}.muted{color:#667085}.warn{color:#b45309}.ok{color:#15803d}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #e5e7eb;padding:8px;text-align:start;vertical-align:top}th{background:#f8fafc}.ltr{direction:ltr;unicode-bidi:embed;word-break:break-all}</style></head><body><div class=\"box\">");
        html.Append($"<h1>{Encode(T("@DeepUninstallReport"))}</h1>");
        html.Append($"<p class=\"muted\">{Encode(T("@Application"))}: {Encode(result.ApplicationName)}<br>{Encode(T("@Publisher"))}: {Encode(string.IsNullOrWhiteSpace(result.Publisher) ? "—" : result.Publisher)}<br>{Encode(T("@ReportTime"))}: {Encode(result.CompletedAt.ToLocalTime().ToString("G", culture))}</p>");

        html.Append("<div class=\"grid\">");
        Metric(html, T("@TotalRemoved"), N(result.TotalRemovedItems));
        Metric(html, T("@FoldersQuarantined"), N(result.DirectoriesQuarantined));
        Metric(html, T("@FilesQuarantined"), N(result.FilesQuarantined));
        Metric(html, T("@RegistryRemoved"), N(result.RegistryKeysRemoved + result.RegistryValuesRemoved));
        Metric(html, T("@ServicesRemoved"), N(result.ServicesRemoved));
        Metric(html, T("@TasksRemoved"), N(result.ScheduledTasksRemoved));
        Metric(html, T("@ProcessesStopped"), N(result.ProcessesStopped));
        Metric(html, T("@QuarantinedSize"), SizeFormatter.Format(result.BytesQuarantined, code));
        Metric(html, T("@PendingRestart"), N(result.PendingDeleteItems));
        html.Append("</div>");

        string resultCss = result.FailedItems == 0 ? "ok" : "warn";
        string summary = LocalizationService.Format(
            "@DeepUninstallSummary",
            code,
            result.TotalRemovedItems,
            result.FailedItems,
            result.SkippedItems);
        html.Append("<div class=\"card\"><h2>" + Encode(T("@Result")) + "</h2><p class=\"" + resultCss + "\">" + Encode(summary) + "</p>");
        if (result.RestartRequired)
        {
            html.Append("<p class=\"warn\">" + Encode(T("@RestartRequiredForLockedFiles")) + "</p>");
        }
        html.Append("<p>" + Encode(T("@RegistryBackup")) + ": <span class=\"ltr\">" + Encode(result.BackupDirectory) + "</span></p></div>");

        if (result.Artifacts.Count > 0)
        {
            html.Append($"<div class=\"card\"><h2>{Encode(T("@RemovedArtifacts"))}</h2><table><thead><tr>");
            Header(html, T("@Type"));
            Header(html, T("@Name"));
            Header(html, T("@Location"));
            Header(html, T("@Reason"));
            Header(html, T("@Status"));
            html.Append("</tr></thead><tbody>");
            foreach (DeepUninstallArtifact artifact in result.Artifacts.Take(500))
            {
                html.Append("<tr>");
                Cell(html, TranslateKind(artifact.Kind, code));
                Cell(html, artifact.Name);
                Cell(html, artifact.Location, "ltr");
                Cell(html, artifact.Reason.StartsWith("@", StringComparison.Ordinal)
                    ? LocalizationService.T(artifact.Reason, code)
                    : LocalizeFreeText(artifact.Reason, code));
                Cell(html, artifact.RequiresRestart ? T("@AfterRestart") : artifact.Removed ? T("@Removed") : T("@Failed"));
                html.Append("</tr>");
            }
            html.Append("</tbody></table></div>");
        }

        if (result.Warnings.Count > 0)
        {
            html.Append($"<div class=\"card\"><h2 class=\"warn\">{Encode(T("@Warnings"))}</h2><ul>");
            foreach (string warning in result.Warnings.Take(250))
            {
                html.Append($"<li>{Encode(LocalizeFreeText(warning, code))}</li>");
            }
            html.Append("</ul></div>");
        }

        html.Append($"<div class=\"card\"><h2>{Encode(T("@ImportantNote"))}</h2><p>{Encode(T("@DeepUninstallSafetyNote"))}</p></div>");
        html.Append("</div></body></html>");
        return html.ToString();
    }

    private static string LocalizeFreeText(string value, string code)
    {
        string translated = LocalizationService.Translate(value, code);
        if (!string.Equals(translated, value, StringComparison.Ordinal) || code == "en")
        {
            return translated;
        }

        return LocalizationService.T("@TechnicalWarning", code);
    }

    private static string TranslateKind(DeepUninstallArtifactKind kind, string code)
        => LocalizationService.T(kind switch
        {
            DeepUninstallArtifactKind.Directory => "@Directory",
            DeepUninstallArtifactKind.File => "@File",
            DeepUninstallArtifactKind.RegistryKey => "@RegistryKey",
            DeepUninstallArtifactKind.RegistryValue => "@RegistryValue",
            DeepUninstallArtifactKind.Service => "@Service",
            DeepUninstallArtifactKind.ScheduledTask => "@ScheduledTask",
            DeepUninstallArtifactKind.Process => "@Process",
            DeepUninstallArtifactKind.PendingDelete => "@PendingDelete",
            _ => "@Type"
        }, code);

    private static void Metric(StringBuilder html, string label, string value)
        => html.Append($"<div class=\"metric\"><div class=\"muted\">{Encode(label)}</div><div class=\"value\">{Encode(value)}</div></div>");

    private static void Header(StringBuilder html, string value)
        => html.Append($"<th>{Encode(value)}</th>");

    private static void Cell(StringBuilder html, string value, string css = "")
        => html.Append($"<td class=\"{css}\">{Encode(value)}</td>");

    private static string SanitizeFileName(string value)
    {
        string cleaned = new(value.Where(character => !Path.GetInvalidFileNameChars().Contains(character)).ToArray());
        cleaned = cleaned.Trim();
        return string.IsNullOrWhiteSpace(cleaned) ? "application" : cleaned[..Math.Min(cleaned.Length, 60)];
    }

    private static string Encode(string value) => WebUtility.HtmlEncode(value);
}
