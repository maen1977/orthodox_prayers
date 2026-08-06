namespace SafeWindowsCleaner.Services;

public static class PublisherInfo
{
    public const string DisplayName = "معن حنونة للستلايت";
    public const string Phone = "00962788272988";
    public const string ProductName = "منظف ويندوز الآمن";
    public const string EnglishProductName = "Safe Windows Cleaner";

    public static string GetDisplayName(string? languageCode)
        => LocalizationService.NormalizeLanguage(languageCode) == "ar"
            ? DisplayName
            : "Maan Hanouna Satellite";
}
