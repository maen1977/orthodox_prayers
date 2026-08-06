namespace SafeWindowsCleaner.Win7.Models
{
    public sealed class ProcessItem
    {
        public int ProcessId { get; set; }
        public string Name { get; set; }
        public string WindowTitle { get; set; }
        public long MemoryBytes { get; set; }
        public string MemoryText { get { return Services.SizeFormatter.Format(MemoryBytes); } }
        public string WindowDisplayText { get { return string.IsNullOrWhiteSpace(WindowTitle) ? Services.LocalizationService.Get("NoVisibleWindow") : WindowTitle; } }
    }
}
