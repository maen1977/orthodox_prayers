using System.Windows;
using System.Windows.Media;

namespace SafeWindowsCleaner.Services;

public static class ThemeService
{
    private sealed record Palette(
        string AppBackground,
        string CardBackground,
        string SurfaceBackground,
        string InputBackground,
        string SecondaryBackground,
        string Text,
        string MutedText,
        string Border,
        string GridLine,
        string HeaderBackground);

    private static readonly Palette Light = new(
        "#F4F7FB", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#EEF3FA",
        "#172033", "#667085", "#D9E1EC", "#E9EEF5", "#F7F9FC");

    private static readonly Palette Dark = new(
        "#111827", "#172033", "#1F2937", "#1F2937", "#273449",
        "#F3F4F6", "#AAB4C3", "#3B475A", "#334155", "#243044");

    private static readonly Palette HighContrast = new(
        "#000000", "#000000", "#000000", "#000000", "#000000",
        "#FFFFFF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#000000");

    public static void Apply(string? theme)
    {
        Palette palette = SystemParameters.HighContrast
            ? HighContrast
            : string.Equals(theme, "Dark", StringComparison.OrdinalIgnoreCase) ? Dark : Light;
        SetBrush("AppBackground", palette.AppBackground);
        SetBrush("CardBackground", palette.CardBackground);
        SetBrush("SurfaceBackground", palette.SurfaceBackground);
        SetBrush("InputBackground", palette.InputBackground);
        SetBrush("SecondaryBackgroundBrush", palette.SecondaryBackground);
        SetBrush("TextBrush", palette.Text);
        SetBrush("MutedTextBrush", palette.MutedText);
        SetBrush("BorderBrush", palette.Border);
        SetBrush("GridLineBrush", palette.GridLine);
        SetBrush("HeaderBackgroundBrush", palette.HeaderBackground);
    }

    private static void SetBrush(string key, string colorText)
    {
        Color color = (Color)ColorConverter.ConvertFromString(colorText);
        if (Application.Current.Resources[key] is SolidColorBrush brush && !brush.IsFrozen)
        {
            brush.Color = color;
            return;
        }

        Application.Current.Resources[key] = new SolidColorBrush(color);
    }
}
