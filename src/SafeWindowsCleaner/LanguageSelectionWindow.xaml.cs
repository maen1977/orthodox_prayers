using System.Windows;
using System.Windows.Controls;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class LanguageSelectionWindow : Window
{
    private bool _refreshingLanguageChoices;

    public string SelectedLanguageCode { get; private set; } = "ar";

    public LanguageSelectionWindow(string initialLanguage = "ar")
    {
        InitializeComponent();
        string code = LocalizationService.NormalizeLanguage(initialLanguage);
        RefreshLanguageChoices(code);
        ApplySelectedLanguage(code);
    }

    private void LanguagesList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_refreshingLanguageChoices)
        {
            string code = LocalizationService.NormalizeLanguage(LanguagesList.SelectedValue?.ToString() ?? "ar");
            ApplySelectedLanguage(code);
        }
    }

    private void ApplySelectedLanguage(string code)
    {
        string normalized = LocalizationService.NormalizeLanguage(code);
        LocalizationService.Apply(this, normalized);
        RefreshLanguageChoices(normalized);
    }

    private void RefreshLanguageChoices(string code)
    {
        _refreshingLanguageChoices = true;
        try
        {
            LanguagesList.ItemsSource = LocalizationService.GetLanguageDisplayOptions(code);
            LanguagesList.SelectedValue = code;
        }
        finally
        {
            _refreshingLanguageChoices = false;
        }
    }

    private void Continue_Click(object sender, RoutedEventArgs e)
    {
        SelectedLanguageCode = LocalizationService.NormalizeLanguage(
            LanguagesList.SelectedValue?.ToString() ?? "ar");

        DialogResult = true;
        Close();
    }
}
