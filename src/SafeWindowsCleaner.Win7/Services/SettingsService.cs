using Microsoft.Win32;

namespace SafeWindowsCleaner.Win7.Services
{
    public static class SettingsService
    {
        private const string KeyPath = @"Software\SafeWindowsCleaner";

        public static string LanguageCode
        {
            get
            {
                using (RegistryKey key = Registry.CurrentUser.OpenSubKey(KeyPath))
                {
                    string value = key == null ? null : key.GetValue("LanguageCode") as string;
                    return value == "en" ? "en" : "ar";
                }
            }
            set
            {
                using (RegistryKey key = Registry.CurrentUser.CreateSubKey(KeyPath))
                {
                    key.SetValue("LanguageCode", value == "en" ? "en" : "ar", RegistryValueKind.String);
                }
            }
        }
    }
}
