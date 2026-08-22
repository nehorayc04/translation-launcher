using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace BigLaunch.Services;

public sealed class DriveUsage
{
    public string Name = "";
    public string Label = "";
    public long Total, Free;
    public long Used => Total - Free;
    public double Percent => Total > 0 ? (double)Used / Total : 0;
    public string UsedLabel => Fmt(Used);
    public string TotalLabel => Fmt(Total);
    public string FreeLabel => Fmt(Free);

    public static string Fmt(long b) =>
        b >= 1L << 40 ? $"{b / (double)(1L << 40):0.##} TB" :
        b >= 1L << 30 ? $"{b / (double)(1L << 30):0.#} GB" :
        b >= 1L << 20 ? $"{b / (double)(1L << 20):0} MB" :
        b >= 1L << 10 ? $"{b / (double)(1L << 10):0} KB" : $"{b} B";
}

/// <summary>
/// Storage manager. Two jobs: show where the disk actually went, and let a
/// title be removed through the store that owns it.
///
/// 🔴 We never delete a game folder ourselves. A store keeps its own manifest,
/// and deleting the files behind its back leaves it convinced the game is
/// still installed. Uninstalling is therefore always a HAND-OFF to the owner.
/// </summary>
public static class Storage
{
    public static List<DriveUsage> Drives()
    {
        var list = new List<DriveUsage>();
        foreach (var d in DriveInfo.GetDrives())
        {
            try
            {
                if (!d.IsReady || d.DriveType is not (DriveType.Fixed or DriveType.Removable)) continue;
                list.Add(new DriveUsage
                {
                    Name = d.Name.TrimEnd('\\'),
                    Label = string.IsNullOrWhiteSpace(d.VolumeLabel) ? d.Name.TrimEnd('\\', ':') : d.VolumeLabel,
                    Total = d.TotalSize,
                    Free = d.AvailableFreeSpace,
                });
            }
            catch { }
        }
        return list;
    }

    /// <summary>
    /// Folder size, off the UI thread and cancellable. A 100 GB install can
    /// take seconds to walk, so every caller must be able to abandon it.
    /// </summary>
    public static Task<long> FolderSizeAsync(string dir, CancellationToken ct) => Task.Run(() =>
    {
        long total = 0;
        try
        {
            var stack = new Stack<string>();
            stack.Push(dir);
            while (stack.Count > 0)
            {
                ct.ThrowIfCancellationRequested();
                string cur = stack.Pop();
                try
                {
                    foreach (var f in Directory.EnumerateFiles(cur))
                    {
                        try { total += new FileInfo(f).Length; } catch { }
                    }
                    foreach (var s in Directory.EnumerateDirectories(cur)) stack.Push(s);
                }
                catch { /* a permission-denied subtree is skipped, not fatal */ }
            }
        }
        catch (OperationCanceledException) { throw; }
        catch { }
        return total;
    }, ct);

    /// <summary>Ask the owning store to uninstall. Returns false if we have no route.</summary>
    public static bool Uninstall(LibraryGame g)
    {
        try
        {
            string? uri = g.Source switch
            {
                GameSource.Steam when g.Key.StartsWith("steam:") => "steam://uninstall/" + g.Key[6..],
                GameSource.Epic => "com.epicgames.launcher://apps",
                GameSource.Ubisoft => "uplay://",
                _ => null,
            };
            if (uri is not null)
            {
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(uri) { UseShellExecute = true });
                return true;
            }

            // GOG and manual installs keep a real uninstaller in the folder.
            if (g.InstallDir.Length > 0 && Directory.Exists(g.InstallDir))
            {
                string? un = Directory.EnumerateFiles(g.InstallDir, "unins*.exe", SearchOption.TopDirectoryOnly)
                                      .FirstOrDefault();
                if (un is not null)
                {
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(un) { UseShellExecute = true });
                    return true;
                }
            }
        }
        catch { }
        return false;
    }

    public static void OpenFolder(string dir)
    {
        try
        {
            if (Directory.Exists(dir))
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(dir) { UseShellExecute = true });
        }
        catch { }
    }
}
