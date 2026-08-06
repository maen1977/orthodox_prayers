using System;

namespace SafeWindowsCleaner.Win7.Models
{
    public sealed class CleanupItem
    {
        public bool IsSelected { get; set; }
        public string Category { get; set; }
        public string Path { get; set; }
        public long SizeBytes { get; set; }
        public DateTime LastWriteTime { get; set; }
        public string SizeText { get { return Services.SizeFormatter.Format(SizeBytes); } }
    }
}
