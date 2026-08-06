using System;

namespace SafeWindowsCleaner.Win7.Models
{
    public sealed class QuarantineEntry
    {
        public string Id { get; set; }
        public string OriginalPath { get; set; }
        public string StoredPath { get; set; }
        public long SizeBytes { get; set; }
        public DateTime CreatedAt { get; set; }
        public string SizeText { get { return Services.SizeFormatter.Format(SizeBytes); } }
        public string CreatedAtText { get { return CreatedAt.ToString("yyyy/MM/dd HH:mm", System.Globalization.CultureInfo.CurrentCulture); } }
    }
}
