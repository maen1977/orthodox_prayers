using System.Globalization;
using System.Text.RegularExpressions;
using System.Windows;

namespace SafeWindowsCleaner.Services;

public sealed record SupportedLanguage(string Code, string NativeName, string EnglishName, bool IsRightToLeft = false);
public sealed record LanguageDisplayOption(string Code, string DisplayName);

/// <summary>
/// Strict bilingual localization boundary for the production application.
/// User-facing text is resolved from the audited Arabic/English catalog and
/// numeric units are normalized only after the final language is known.
/// </summary>
public static class LocalizationService
{
    private static readonly Regex ArabicRegex = new("[\\u0600-\\u06FF]", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex SizeTokenRegex = new(
        @"(?<number>\d+(?:[.,]\d+)?)\s*(?<unit>TB|GB|MB|KB|B|ت\.ب|ج\.ب|م\.ب|ك\.ب|بايت|كيلوبايت|ميغابايت|غيغابايت|تيرابايت)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly Regex TechnicalTokenRegex = new(
        @"(?:(?:[A-Za-z]:\\|\\\\)[^\r\n،؛]+|https?://\S+|\bPID\s*[:=]?\s*\d+\b|\d+(?:[.,]\d+)?\s*(?:%|TB|GB|MB|KB|B|ت\.ب|ج\.ب|م\.ب|ك\.ب|بايت|كيلوبايت|ميغابايت|غيغابايت|تيرابايت)?)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    private static readonly Dictionary<string, LocalizedEntry> EntriesByKey;
    private static readonly Dictionary<string, LocalizedEntry> EntriesByAnyValue;
    private static readonly TemplateLocalizationEntry[] ArabicTemplateEntries;

    public static IReadOnlyList<SupportedLanguage> SupportedLanguages { get; } =
    [
        new("ar", "العربية", "Arabic", true),
        new("en", "English", "English")
    ];

    public static string ActiveLanguageCode { get; private set; } = "ar";

    public static IReadOnlyList<LanguageDisplayOption> GetLanguageDisplayOptions(string? interfaceLanguageCode = null)
    {
        string code = NormalizeLanguage(interfaceLanguageCode ?? ActiveLanguageCode);
        return
        [
            new("ar", T("@LanguageArabic", code)),
            new("en", T("@LanguageEnglish", code))
        ];
    }

    public static event EventHandler? LanguageChanged;

    static LocalizationService()
    {
        EntriesByKey = new Dictionary<string, LocalizedEntry>(StringComparer.Ordinal);
        EntriesByAnyValue = new Dictionary<string, LocalizedEntry>(StringComparer.Ordinal);

        foreach (LocalizedEntry entry in LocalizationCatalog.Entries)
        {
            EntriesByKey[entry.Key] = entry;
            AddReverse(entry.Ar, entry);
            AddReverse(entry.En, entry);
        }

        ArabicTemplateEntries = LocalizationCatalog.Entries
            .Where(entry => !entry.Key.StartsWith('@')
                            && entry.Ar.Contains('{', StringComparison.Ordinal)
                            && entry.Ar.Contains('}', StringComparison.Ordinal))
            .Select(entry => new TemplateLocalizationEntry(entry, BuildTemplateRegex(entry.Ar)))
            .OrderByDescending(entry => entry.Entry.Ar.Length)
            .ToArray();
    }

    public static string NormalizeLanguage(string? code)
    {
        string value = (code ?? string.Empty).Trim().ToLowerInvariant();
        int separator = value.IndexOf('-');
        if (separator >= 0)
        {
            value = value[..separator];
        }

        if (SupportedLanguages.Any(language => language.Code == value))
        {
            return value;
        }

        // Old incomplete non-Arabic language choices migrate to complete English.
        return string.IsNullOrWhiteSpace(value) ? "ar" : "en";
    }

    public static void SetActiveLanguage(string? languageCode)
    {
        string normalized = NormalizeLanguage(languageCode);
        bool changed = !string.Equals(ActiveLanguageCode, normalized, StringComparison.Ordinal);
        ActiveLanguageCode = normalized;
        ApplyApplicationResources(normalized);

        if (changed)
        {
            LanguageChanged?.Invoke(null, EventArgs.Empty);
        }
    }

    /// <summary>
    /// Loads all static WPF interface strings from the same audited catalog used
    /// by dynamic messages. This prevents XAML controls from retaining their
    /// design-time Arabic text when the English interface is active, and avoids
    /// mixed-language menus caused by visual-tree translation timing.
    /// </summary>
    public static void ApplyApplicationResources(string? languageCode = null)
    {
        if (Application.Current is null)
        {
            return;
        }

        string code = NormalizeLanguage(languageCode ?? ActiveLanguageCode);
        foreach (LocalizedEntry entry in LocalizationCatalog.Entries)
        {
            if (!entry.Key.StartsWith("UI.", StringComparison.Ordinal))
            {
                continue;
            }

            Application.Current.Resources[entry.Key] =
                NormalizeTechnicalTokens(ValueFor(entry, code), code);
        }
    }

    public static bool IsArabic(string? languageCode = null)
        => NormalizeLanguage(languageCode ?? ActiveLanguageCode) == "ar";

    public static string T(string key, string? languageCode = null)
    {
        string code = NormalizeLanguage(languageCode ?? ActiveLanguageCode);
        if (EntriesByKey.TryGetValue(key, out LocalizedEntry? entry))
        {
            return NormalizeTechnicalTokens(ValueFor(entry, code), code);
        }

        return Translate(key, code);
    }

    public static string Translate(string? value, string? languageCode = null)
    {
        if (string.IsNullOrEmpty(value))
        {
            return value ?? string.Empty;
        }

        string code = NormalizeLanguage(languageCode ?? ActiveLanguageCode);
        if (EntriesByKey.TryGetValue(value, out LocalizedEntry? keyed))
        {
            return NormalizeTechnicalTokens(ValueFor(keyed, code), code);
        }

        if (EntriesByAnyValue.TryGetValue(value, out LocalizedEntry? exact))
        {
            return NormalizeTechnicalTokens(ValueFor(exact, code), code);
        }

        if (code == "ar")
        {
            if (ContainsArabic(value) || IsTechnicalIdentifier(value))
            {
                return NormalizeTechnicalTokens(value, code);
            }

            // Never leak an unknown English sentence into the Arabic interface.
            // Product names, paths, hashes, URLs and command tokens are preserved;
            // unlocalized prose is replaced with a clear Arabic fallback and kept
            // in the local diagnostic log for developers.
            return BuildStrictFallback(value, code);
        }

        if (!ContainsArabic(value))
        {
            return NormalizeTechnicalTokens(value, code);
        }

        if (TryTranslateTemplate(value, code, out string templateTranslation))
        {
            return NormalizeTechnicalTokens(templateTranslation, code);
        }

        // A production source gate rejects new untranslated UI text. This fallback
        // keeps legacy diagnostics language-consistent without creating hybrid text.
        return BuildStrictFallback(value, code);
    }

    public static string Format(string key, string? languageCode, params object?[] arguments)
    {
        string code = NormalizeLanguage(languageCode ?? ActiveLanguageCode);
        string formatted = string.Format(CultureFor(code), T(key, code), arguments);
        return NormalizeTechnicalTokens(formatted, code);
    }

    public static string FormatNumber(long value, string? languageCode = null)
        => value.ToString("N0", CultureFor(languageCode ?? ActiveLanguageCode));

    public static string FormatSize(long bytes, string? languageCode = null)
        => SafeWindowsCleaner.Helpers.SizeFormatter.Format(bytes, languageCode ?? ActiveLanguageCode);

    public static string NormalizeTechnicalTokens(string value, string? languageCode = null)
    {
        if (string.IsNullOrEmpty(value))
        {
            return value;
        }

        string code = NormalizeLanguage(languageCode ?? ActiveLanguageCode);
        return SizeTokenRegex.Replace(value, match =>
        {
            string number = NormalizeNumberToken(match.Groups["number"].Value, code);
            string unit = NormalizeUnit(match.Groups["unit"].Value, code);
            return $"{number} {unit}";
        });
    }

    public static void Apply(Window window, string languageCode)
    {
        string code = NormalizeLanguage(languageCode);
        SetActiveLanguage(code);
        bool rtl = SupportedLanguages.First(language => language.Code == code).IsRightToLeft;
        window.FlowDirection = rtl ? FlowDirection.RightToLeft : FlowDirection.LeftToRight;
        window.Language = System.Windows.Markup.XmlLanguage.GetLanguage(CultureFor(code).IetfLanguageTag);
    }

    public static CultureInfo CultureFor(string languageCode)
        => NormalizeLanguage(languageCode) == "ar"
            ? CultureInfo.GetCultureInfo("ar-JO")
            : CultureInfo.GetCultureInfo("en-US");

    public static bool ContainsArabic(string? value)
        => !string.IsNullOrEmpty(value) && ArabicRegex.IsMatch(value);

    public static bool ContainsArabicSizeUnit(string? value)
        => !string.IsNullOrWhiteSpace(value)
           && Regex.IsMatch(value, @"(?:ت\.ب|ج\.ب|م\.ب|ك\.ب|بايت|كيلوبايت|ميغابايت|غيغابايت|تيرابايت)", RegexOptions.CultureInvariant);

    public static bool ContainsEnglishSizeUnit(string? value)
        => !string.IsNullOrWhiteSpace(value)
           && Regex.IsMatch(value, @"(?<![A-Za-z])(?:TB|GB|MB|KB|B)(?![A-Za-z])", RegexOptions.CultureInvariant);

    public static bool ValidateCatalog(out string error)
    {
        var keys = new HashSet<string>(StringComparer.Ordinal);
        foreach (LocalizedEntry entry in LocalizationCatalog.Entries)
        {
            if (!keys.Add(entry.Key))
            {
                error = $"Duplicate localization key: {entry.Key}";
                return false;
            }

            if (string.IsNullOrWhiteSpace(entry.Ar))
            {
                error = $"Missing 'ar' translation for: {entry.Key}";
                return false;
            }

            if (string.IsNullOrWhiteSpace(entry.En))
            {
                error = $"Missing 'en' translation for: {entry.Key}";
                return false;
            }

            if (ContainsArabic(entry.En))
            {
                error = $"Arabic text leaked into 'en' translation for: {entry.Key}";
                return false;
            }

            if (ContainsEnglishSizeUnit(entry.Ar))
            {
                error = $"English size unit leaked into 'ar' translation for: {entry.Key}";
                return false;
            }

            if (ContainsArabicSizeUnit(entry.En))
            {
                error = $"Arabic size unit leaked into 'en' translation for: {entry.Key}";
                return false;
            }
        }

        error = string.Empty;
        return true;
    }

    private static void AddReverse(string value, LocalizedEntry entry)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            EntriesByAnyValue.TryAdd(value, entry);
        }
    }

    private static bool TryTranslateTemplate(string value, string code, out string translated)
    {
        foreach (TemplateLocalizationEntry template in ArabicTemplateEntries)
        {
            Match match = template.Pattern.Match(value);
            if (!match.Success)
            {
                continue;
            }

            string localizedTemplate = ValueFor(template.Entry, code);
            translated = Regex.Replace(
                localizedTemplate,
                @"\{(?<index>\d+)(?:[^}]*)\}",
                placeholder =>
                {
                    string groupName = "p" + placeholder.Groups["index"].Value;
                    Group group = match.Groups[groupName];
                    return group.Success ? NormalizeTechnicalTokens(group.Value, code) : string.Empty;
                },
                RegexOptions.CultureInvariant);
            translated = NormalizeTechnicalTokens(translated, code);
            return !ContainsArabic(translated);
        }

        translated = string.Empty;
        return false;
    }

    private static Regex BuildTemplateRegex(string template)
    {
        var pattern = new System.Text.StringBuilder("^");
        int cursor = 0;
        foreach (Match placeholder in Regex.Matches(template, @"\{(?<index>\d+)(?:[^}]*)\}", RegexOptions.CultureInvariant))
        {
            pattern.Append(Regex.Escape(template[cursor..placeholder.Index]));
            pattern.Append("(?<p");
            pattern.Append(placeholder.Groups["index"].Value);
            pattern.Append(@">.+?)");
            cursor = placeholder.Index + placeholder.Length;
        }

        pattern.Append(Regex.Escape(template[cursor..]));
        pattern.Append('$');
        return new Regex(pattern.ToString(), RegexOptions.Compiled | RegexOptions.CultureInvariant | RegexOptions.Singleline);
    }

    private static string ValueFor(LocalizedEntry entry, string code)
        => code == "ar" ? entry.Ar : entry.En;

    private static string NormalizeNumberToken(string value, string code)
    {
        string normalized = value.Replace(',', '.');
        if (!double.TryParse(normalized, NumberStyles.Float, CultureInfo.InvariantCulture, out double number))
        {
            return value;
        }

        string format = normalized.Contains('.') ? "0.##" : "0";
        return number.ToString(format, CultureFor(code));
    }

    private static string NormalizeUnit(string value, string code)
    {
        string canonical = value.Trim().ToUpperInvariant() switch
        {
            "T.B" or "TB" => "TB",
            "G.B" or "GB" => "GB",
            "M.B" or "MB" => "MB",
            "K.B" or "KB" => "KB",
            "B" => "B",
            _ when value is "ت.ب" or "تيرابايت" => "TB",
            _ when value is "ج.ب" or "غيغابايت" => "GB",
            _ when value is "م.ب" or "ميغابايت" => "MB",
            _ when value is "ك.ب" or "كيلوبايت" => "KB",
            _ when value == "بايت" => "B",
            _ => value
        };

        if (code != "ar")
        {
            return canonical;
        }

        return canonical switch
        {
            "TB" => "تيرابايت",
            "GB" => "غيغابايت",
            "MB" => "ميغابايت",
            "KB" => "كيلوبايت",
            "B" => "بايت",
            _ => value
        };
    }

    private static bool IsTechnicalIdentifier(string value)
    {
        string trimmed = value.Trim();
        if (trimmed.Length == 0)
        {
            return true;
        }

        if (!trimmed.Any(char.IsWhiteSpace))
        {
            return true;
        }

        string withoutTokens = TechnicalTokenRegex.Replace(trimmed, string.Empty);
        withoutTokens = Regex.Replace(
            withoutTokens,
            @"[\s\p{P}\p{S}\d_]+",
            string.Empty,
            RegexOptions.CultureInvariant);
        return withoutTokens.Length == 0;
    }

    private static string BuildStrictFallback(string original, string code)
    {
        string message = T("@AdditionalInformationLog", code);
        string[] tokens = TechnicalTokenRegex.Matches(original)
            .Select(match => NormalizeTechnicalTokens(match.Value.Trim(), code))
            .Where(value => value.Length > 0 && !ContainsArabic(value))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(6)
            .ToArray();
        return tokens.Length == 0 ? message : $"{message} {string.Join(" — ", tokens)}";
    }

    private sealed record TemplateLocalizationEntry(LocalizedEntry Entry, Regex Pattern);
}
