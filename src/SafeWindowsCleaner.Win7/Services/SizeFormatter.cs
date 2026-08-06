using System.Globalization;

namespace SafeWindowsCleaner.Win7.Services
{
    public static class SizeFormatter
    {
        public static string Format(long bytes)
        {
            string[] ar = { "بايت", "كيلوبايت", "ميغابايت", "غيغابايت", "تيرابايت" };
            string[] en = { "B", "KB", "MB", "GB", "TB" };
            string[] units = LocalizationService.IsArabic ? ar : en;
            double value = bytes < 0 ? 0 : bytes;
            int unit = 0;
            while (value >= 1024 && unit < units.Length - 1)
            {
                value /= 1024;
                unit++;
            }
            string number = value >= 100 || unit == 0 ? value.ToString("0", CultureInfo.CurrentCulture) : value.ToString("0.0", CultureInfo.CurrentCulture);
            return number + " " + units[unit];
        }
    }
}
