using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Helpers;

/// <summary>
/// Formats byte counts only after the target UI/report language is known.
/// Arabic output never contains English unit abbreviations, and English output
/// never contains Arabic unit names or abbreviations.
/// </summary>
public static class SizeFormatter
{
    private static readonly string[] ArabicUnits = ["بايت", "كيلوبايت", "ميغابايت", "غيغابايت", "تيرابايت"];
    private static readonly string[] EnglishUnits = ["B", "KB", "MB", "GB", "TB"];

    public static string Format(long bytes, string? languageCode = null)
    {
        string code = LocalizationService.NormalizeLanguage(
            string.IsNullOrWhiteSpace(languageCode)
                ? LocalizationService.ActiveLanguageCode
                : languageCode);

        string[] units = code == "ar" ? ArabicUnits : EnglishUnits;
        double value = Math.Max(0, bytes);
        int unit = 0;
        while (value >= 1024 && unit < units.Length - 1)
        {
            value /= 1024;
            unit++;
        }

        IFormatProvider culture = LocalizationService.CultureFor(code);
        string number = unit == 0
            ? value.ToString("0", culture)
            : value.ToString("0.##", culture);
        return $"{number} {units[unit]}";
    }
}
