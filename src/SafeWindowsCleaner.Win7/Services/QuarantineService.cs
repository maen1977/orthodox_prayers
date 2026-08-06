using SafeWindowsCleaner.Win7.Models;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Xml.Serialization;

namespace SafeWindowsCleaner.Win7.Services
{
    public sealed class QuarantineService
    {
        private static readonly string Root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SafeWindowsCleaner", "Win7", "Quarantine");
        private static readonly string IndexPath = Path.Combine(Root, "index.xml");
        private readonly object _sync = new object();

        public int Quarantine(IEnumerable<CleanupItem> items)
        {
            int moved = 0;
            lock (_sync)
            {
                List<QuarantineEntry> index = LoadUnsafe();
                foreach (CleanupItem item in items.Where(x => x.IsSelected))
                {
                    try
                    {
                        if (!File.Exists(item.Path)) continue;
                        Directory.CreateDirectory(Root);
                        string id = Guid.NewGuid().ToString("N");
                        string stored = Path.Combine(Root, id + ".bin");
                        try { File.Move(item.Path, stored); }
                        catch
                        {
                            File.Copy(item.Path, stored, false);
                            File.Delete(item.Path);
                        }
                        index.Add(new QuarantineEntry
                        {
                            Id = id,
                            OriginalPath = item.Path,
                            StoredPath = stored,
                            SizeBytes = item.SizeBytes,
                            CreatedAt = DateTime.Now
                        });
                        moved++;
                    }
                    catch (Exception ex) { LogService.Write("Quarantine failed: " + ex.Message); }
                }
                SaveUnsafe(index);
            }
            return moved;
        }

        public List<QuarantineEntry> Load()
        {
            lock (_sync) { return LoadUnsafe().OrderByDescending(x => x.CreatedAt).ToList(); }
        }

        public bool Restore(QuarantineEntry entry)
        {
            if (entry == null) return false;
            lock (_sync)
            {
                try
                {
                    if (!File.Exists(entry.StoredPath)) return false;
                    string directory = Path.GetDirectoryName(entry.OriginalPath);
                    if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
                    string destination = entry.OriginalPath;
                    if (File.Exists(destination)) destination = GetAvailableName(destination);
                    File.Move(entry.StoredPath, destination);
                    List<QuarantineEntry> index = LoadUnsafe();
                    index.RemoveAll(x => x.Id == entry.Id);
                    SaveUnsafe(index);
                    return true;
                }
                catch (Exception ex) { LogService.Write("Restore failed: " + ex.Message); return false; }
            }
        }

        public bool Delete(QuarantineEntry entry)
        {
            if (entry == null) return false;
            lock (_sync)
            {
                try
                {
                    if (File.Exists(entry.StoredPath)) File.Delete(entry.StoredPath);
                    List<QuarantineEntry> index = LoadUnsafe();
                    index.RemoveAll(x => x.Id == entry.Id);
                    SaveUnsafe(index);
                    return true;
                }
                catch (Exception ex) { LogService.Write("Delete quarantine failed: " + ex.Message); return false; }
            }
        }

        private static string GetAvailableName(string path)
        {
            string directory = Path.GetDirectoryName(path);
            string name = Path.GetFileNameWithoutExtension(path);
            string extension = Path.GetExtension(path);
            for (int i = 1; i < 1000; i++)
            {
                string candidate = Path.Combine(directory, name + " (restored " + i + ")" + extension);
                if (!File.Exists(candidate)) return candidate;
            }
            return Path.Combine(directory, Guid.NewGuid().ToString("N") + extension);
        }

        private static List<QuarantineEntry> LoadUnsafe()
        {
            try
            {
                if (!File.Exists(IndexPath)) return new List<QuarantineEntry>();
                using (FileStream stream = File.OpenRead(IndexPath))
                {
                    return (List<QuarantineEntry>)new XmlSerializer(typeof(List<QuarantineEntry>)).Deserialize(stream);
                }
            }
            catch { return new List<QuarantineEntry>(); }
        }

        private static void SaveUnsafe(List<QuarantineEntry> entries)
        {
            Directory.CreateDirectory(Root);
            string temp = IndexPath + ".tmp";
            using (FileStream stream = File.Create(temp))
            {
                new XmlSerializer(typeof(List<QuarantineEntry>)).Serialize(stream, entries);
            }
            if (File.Exists(IndexPath)) File.Delete(IndexPath);
            File.Move(temp, IndexPath);
        }
    }
}
