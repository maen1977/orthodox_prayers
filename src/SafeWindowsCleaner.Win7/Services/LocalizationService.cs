using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using System.Windows;

namespace SafeWindowsCleaner.Win7.Services
{
    public static class LocalizationService
    {
        private static readonly Dictionary<string, string[]> Texts = new Dictionary<string, string[]>
        {
            {"AppTitle", new[]{"منظف ويندوز الآمن لايت — ويندوز القديم", "Safe Windows Cleaner Lite — Windows Legacy"}},
            {"Home", new[]{"الرئيسية", "Home"}},
            {"Clean", new[]{"التنظيف الآمن", "Safe cleanup"}},
            {"Programs", new[]{"إزالة البرامج", "Uninstall programs"}},
            {"Memory", new[]{"البرامج الثقيلة والذاكرة", "Heavy apps and memory"}},
            {"Restore", new[]{"الاستعادة", "Restore"}},
            {"Settings", new[]{"الإعدادات", "Settings"}},
            {"Welcome", new[]{"تنظيف بسيط وآمن للأجهزة القديمة", "Simple, safe cleanup for older computers"}},
            {"WelcomeBody", new[]{"نسخة خفيفة مخصصة لويندوز 7 SP1 وويندوز 8 وويندوز 8.1. راجع النتائج قبل تنفيذ أي تغيير.", "A lightweight edition for Windows 7 SP1, Windows 8, and Windows 8.1. Review results before making changes."}},
            {"ScanNow", new[]{"فحص الآن", "Scan now"}},
            {"CleanSelected", new[]{"نقل المحدد إلى الاستعادة", "Move selected to restore center"}},
            {"Refresh", new[]{"تحديث", "Refresh"}},
            {"UninstallSelected", new[]{"إزالة البرنامج المحدد", "Uninstall selected program"}},
            {"CloseSelected", new[]{"إغلاق التطبيق المحدد", "Close selected app"}},
            {"ReservePagefile", new[]{"تفعيل ذاكرة افتراضية آمنة حتى 16 غيغابايت", "Enable safe virtual memory up to 16 GB"}},
            {"RestorePagefile", new[]{"استعادة إعداد ويندوز السابق", "Restore previous Windows setting"}},
            {"RestoreSelected", new[]{"استعادة الملف المحدد", "Restore selected file"}},
            {"DeleteSelected", new[]{"حذف نهائي للمحدد", "Permanently delete selected"}},
            {"Language", new[]{"لغة البرنامج", "Application language"}},
            {"Arabic", new[]{"العربية", "Arabic"}},
            {"English", new[]{"الإنجليزية", "English"}},
            {"RestartLanguage", new[]{"سيُعاد تشغيل البرنامج لتطبيق اللغة.", "The application will restart to apply the language."}},
            {"StatusReady", new[]{"جاهز", "Ready"}},
            {"Scanning", new[]{"جارٍ فحص الملفات الآمنة...", "Scanning safe files..."}},
            {"Cleaning", new[]{"جارٍ نقل الملفات إلى مركز الاستعادة...", "Moving files to the restore center..."}},
            {"NoItems", new[]{"لم يتم العثور على عناصر مناسبة.", "No suitable items were found."}},
            {"SelectItem", new[]{"اختر عنصرًا أولًا.", "Select an item first."}},
            {"ConfirmUninstall", new[]{"سيتم تشغيل أداة الإزالة الرسمية لهذا البرنامج. هل تريد المتابعة؟", "The program's official uninstaller will be launched. Continue?"}},
            {"ConfirmClose", new[]{"سيتم طلب إغلاق التطبيق المحدد. احفظ عملك أولًا.", "The selected app will be asked to close. Save your work first."}},
            {"PagefileInfo", new[]{"هذه ذاكرة افتراضية للنظام وليست رام حقيقية أو ذاكرة كرت شاشة. تحتاج إلى إعادة تشغيل ويندوز.", "This is system virtual memory, not physical RAM or graphics memory. Windows must be restarted."}},
            {"PagefileApplied", new[]{"تم حجز {0}. أعد تشغيل ويندوز لتطبيقها.", "{0} was reserved. Restart Windows to apply it."}},
            {"PagefileRestored", new[]{"تمت استعادة الإعداد السابق. أعد تشغيل ويندوز.", "The previous setting was restored. Restart Windows."}},
            {"NeedSpace", new[]{"المساحة الحرة غير كافية. يجب أن يبقى 8 غيغابايت على الأقل لويندوز بعد إنشاء ملف الذاكرة الافتراضية.", "Free space is insufficient. At least 8 GB must remain available to Windows after creating the page file."}},
            {"ConfirmPagefile", new[]{"سيحجز البرنامج {0} كذاكرة افتراضية مع إبقاء مساحة آمنة لويندوز. يلزم إعادة التشغيل. هل تريد المتابعة؟", "The application will reserve {0} as virtual memory while preserving safe free space for Windows. A restart is required. Continue?"}},
            {"Error", new[]{"خطأ", "Error"}},
            {"Information", new[]{"معلومات", "Information"}},
            {"Category", new[]{"الفئة", "Category"}},
            {"Path", new[]{"المسار", "Path"}},
            {"Size", new[]{"الحجم", "Size"}},
            {"Name", new[]{"الاسم", "Name"}},
            {"Publisher", new[]{"الناشر", "Publisher"}},
            {"Version", new[]{"الإصدار", "Version"}},
            {"MemoryUse", new[]{"استهلاك الذاكرة", "Memory usage"}},
            {"WindowOrStatus", new[]{"النافذة أو الحالة", "Window or status"}},
            {"OriginalPath", new[]{"المسار الأصلي", "Original path"}},
            {"Date", new[]{"التاريخ", "Date"}},
            {"SelectedSummary", new[]{"العناصر المحددة: {0} — الحجم: {1}", "Selected: {0} — Size: {1}"}},
            {"ScanSummary", new[]{"تم العثور على {0} عنصر بحجم {1}.", "Found {0} items totaling {1}."}},
            {"CleanSummary", new[]{"تم نقل {0} ملف إلى مركز الاستعادة.", "Moved {0} files to the restore center."}},
            {"ProgramsFound", new[]{"البرامج الظاهرة: {0}", "Programs shown: {0}"}},
            {"ProcessesFound", new[]{"تطبيقات المستخدم الثقيلة: {0}", "Heavy user apps: {0}"}},
            {"RestoreFound", new[]{"الملفات القابلة للاستعادة: {0}", "Restorable files: {0}"}},
            {"PagefileCurrent", new[]{"إعداد الذاكرة الافتراضية الحالي: {0}", "Current virtual-memory setting: {0}"}},
            {"Automatic", new[]{"إدارة ويندوز التلقائية", "Windows managed"}},
            {"FixedPreset", new[]{"{0} ثابتة — إعادة التشغيل قد تكون مطلوبة", "Fixed {0} — restart may be required"}},
            {"Unknown", new[]{"غير معروف", "Unknown"}},
            {"Temp", new[]{"ملفات مؤقتة", "Temporary files"}},
            {"BrowserCache", new[]{"ذاكرة متصفح مؤقتة", "Browser cache"}},
            {"PagefileUnavailable", new[]{"تعذر الوصول إلى إعدادات الذاكرة الافتراضية في ويندوز.", "Windows virtual-memory settings are unavailable."}},
            {"AlreadyRunning", new[]{"البرنامج يعمل بالفعل.", "Safe Windows Cleaner Lite is already running."}},
            {"WindowsTemp", new[]{"ملفات ويندوز المؤقتة", "Windows temporary files"}},
            {"OperationFailed", new[]{"تعذر إكمال العملية. راجع سجل البرنامج للتفاصيل.", "The operation could not be completed. Review the application log for details."}},
            {"NoVisibleWindow", new[]{"بدون نافذة ظاهرة", "No visible window"}}
        };

        public static bool IsArabic { get { return SettingsService.LanguageCode != "en"; } }

        public static string Get(string key)
        {
            string[] values;
            if (!Texts.TryGetValue(key, out values)) return key;
            return IsArabic ? values[0] : values[1];
        }

        public static string Format(string key, params object[] args)
        {
            return string.Format(CultureInfo.CurrentCulture, Get(key), args);
        }

        public static void ApplyCulture(Window window)
        {
            string cultureName = IsArabic ? "ar-JO" : "en-US";
            CultureInfo culture = CultureInfo.GetCultureInfo(cultureName);
            Thread.CurrentThread.CurrentCulture = culture;
            Thread.CurrentThread.CurrentUICulture = culture;
            CultureInfo.DefaultThreadCurrentCulture = culture;
            CultureInfo.DefaultThreadCurrentUICulture = culture;
            window.Language = System.Windows.Markup.XmlLanguage.GetLanguage(culture.IetfLanguageTag);
            window.FlowDirection = IsArabic ? FlowDirection.RightToLeft : FlowDirection.LeftToRight;
        }
    }
}
