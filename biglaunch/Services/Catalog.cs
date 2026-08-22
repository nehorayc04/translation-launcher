using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace BigLaunch.Services;

public sealed class GameEntry
{
    public string Id = "";
    public string TitleHe = "";
    public string TitleEn = "";
    public string Tagline = "";
    public string? Cover;
    public string? Banner;
    public string? Logo;
    public string Availability = "";
    public string Status = "";
    public int PriceCents;
    public bool IsSoftware;
    public bool Featured;
    public int SortOrder;
    public string ThemeKey = "default";

    /// <summary>Local install path, from detected_games.json. Null = not installed.</summary>
    public string? InstallPath;

    public bool Installed => !string.IsNullOrEmpty(InstallPath);
    public bool Available => Availability == "available";
    public string Display => !string.IsNullOrWhiteSpace(TitleHe) ? TitleHe : TitleEn;
}

/// <summary>
/// Reads the launcher's own on-disk state. Deliberately READ-ONLY and
/// dependency-free: Big Launch must open instantly and must never be able to
/// corrupt the desktop launcher's caches.
///
/// ⚠ THIS CLASS stays read-only, but the SHELL no longer is: installing,
/// removing, repairing and switching a translation's language now run through
/// ModBridge, which shells out to TranslationManager.exe's headless --mod CLI.
/// The write path deliberately lives THERE and not here - one implementation of
/// backups, journals, game-update awareness and the purchase gate, not two.
/// Buying and signing in are still handed to the desktop app/website.
/// </summary>
/// <summary>
/// One item of the hub's own Hebrew news feed. Winhanced's "What's New" pulls
/// third-party gaming RSS; ours pulls the thing this product actually publishes -
/// which translations shipped, which games were added. Same screen, content we
/// own, no outside feed to depend on or to be legally careful about.
/// </summary>
public sealed class NewsItem
{
    public string Id = "", Date = "", Kind = "", Badge = "", Title = "", Detail = "", Link = "";
}

public static class Catalog
{
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern int SHGetKnownFolderPath(ref Guid id, uint flags, IntPtr token, out IntPtr path);

    private static string RealHome()
    {
        // %USERPROFILE% can be redirected by a sandboxed parent process; the
        // known-folder API reads the token/registry and is always the truth.
        try
        {
            var g = new Guid("5E6C858F-0E22-4760-9AFE-EA3317B67173"); // FOLDERID_Profile
            if (SHGetKnownFolderPath(ref g, 0, IntPtr.Zero, out IntPtr p) == 0)
            {
                string s = Marshal.PtrToStringUni(p) ?? "";
                Marshal.FreeCoTaskMem(p);
                if (!string.IsNullOrEmpty(s)) return s;
            }
        }
        catch { }
        return Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
    }

    public static string StateDir => Path.Combine(RealHome(), ".translation_manager");
    public static string ArtDir   => Path.Combine(StateDir, "biglaunch_art");

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(20) };

    private static JsonElement? ReadJson(string file)
    {
        try
        {
            string p = Path.Combine(StateDir, file);
            if (!File.Exists(p)) return null;
            using var doc = JsonDocument.Parse(File.ReadAllText(p));
            return doc.RootElement.Clone();
        }
        catch { return null; }
    }

    /// <summary>
    /// Every catalog string enters through here - which makes it the one place
    /// the project's iron rule belongs: a plain hyphen, never a long dash.
    /// The rule is deterministic with one right answer, so it lives in the
    /// pipeline rather than in a style note nobody re-reads; the feed is
    /// written by many hands and a stray em dash would otherwise render on a
    /// card we do not control.
    ///
    /// ONE-FOR-ONE, never a run-collapse: "--" stays two characters, because a
    /// repeated dash is usually a decorative rule someone drew on purpose. The
    /// Hebrew maqaf (U+05BE) is deliberately NOT in the class - it is a real
    /// letter-joining mark, not punctuation.
    /// </summary>
    private static string Str(JsonElement e, string k) =>
        e.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.String ? Dashes(v.GetString() ?? "") : "";

    private static readonly char[] LongDashes =
        { '‐', '‑', '‒', '–', '—', '―', '−', '﹘', '﹣', '－' };

    private static string Dashes(string s)
    {
        if (s.Length == 0) return s;
        Span<char> buf = s.Length <= 512 ? stackalloc char[s.Length] : new char[s.Length];
        bool hit = false;
        for (int i = 0; i < s.Length; i++)
        {
            char c = s[i];
            if (Array.IndexOf(LongDashes, c) >= 0) { buf[i] = '-'; hit = true; }
            else buf[i] = c;
        }
        return hit ? new string(buf) : s;
    }

    private static bool Bool(JsonElement e, string k) =>
        e.TryGetProperty(k, out var v) && (v.ValueKind == JsonValueKind.True);

    private static int Int(JsonElement e, string k) =>
        e.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number && v.TryGetInt32(out int i) ? i : 0;

    /// <summary>
    /// The launcher's SWR cache already holds the feed on disk, so the console
    /// reads it with no network call and no second source of truth. Offline it
    /// simply shows the last thing the launcher saw, which is the right answer
    /// for a shell that must open instantly.
    /// </summary>
    public static List<NewsItem> News()
    {
        var list = new List<NewsItem>();
        var cache = ReadJson("cache.json");
        if (cache is { } root
            && root.TryGetProperty("entries", out var entries)
            && entries.TryGetProperty("news", out var nEntry)
            && nEntry.TryGetProperty("data", out var arr)
            && arr.ValueKind == JsonValueKind.Array)
        {
            foreach (var n in arr.EnumerateArray())
            {
                string title = Str(n, "title");
                if (string.IsNullOrWhiteSpace(title)) continue;
                list.Add(new NewsItem
                {
                    Id = Str(n, "id"), Date = Str(n, "date"), Kind = Str(n, "kind"),
                    Badge = Str(n, "badge"), Title = title,
                    Detail = Str(n, "detail"), Link = Str(n, "link"),
                });
            }
        }
        // Newest first. The dates are ISO, so an ordinal sort IS chronological.
        list.Sort((a, b) => string.CompareOrdinal(b.Date, a.Date));
        return list;
    }

    public static List<GameEntry> Load()
    {
        var games = new List<GameEntry>();

        // 1. the SWR catalog cache the launcher already maintains
        var cache = ReadJson("cache.json");
        if (cache is { } root
            && root.TryGetProperty("entries", out var entries)
            && entries.TryGetProperty("games", out var gEntry)
            && gEntry.TryGetProperty("data", out var arr)
            && arr.ValueKind == JsonValueKind.Array)
        {
            foreach (var g in arr.EnumerateArray())
            {
                string id = Str(g, "id");
                if (string.IsNullOrEmpty(id)) continue;
                games.Add(new GameEntry
                {
                    Id           = id,
                    TitleHe      = Str(g, "titleHe"),
                    TitleEn      = Str(g, "titleEn"),
                    Tagline      = Str(g, "tagline"),
                    Cover        = Str(g, "cover")     is { Length: > 0 } c ? c : null,
                    Banner       = Str(g, "bannerUrl") is { Length: > 0 } b ? b : null,
                    Logo         = Str(g, "logoUrl")   is { Length: > 0 } l ? l : null,
                    Availability = Str(g, "availability"),
                    Status       = Str(g, "status"),
                    PriceCents   = Int(g, "priceCents"),
                    IsSoftware   = Bool(g, "isSoftware"),
                    Featured     = Bool(g, "featured"),
                    SortOrder    = Int(g, "sortOrder"),
                    ThemeKey     = Str(g, "themeKey") is { Length: > 0 } t ? t : "default",
                });
            }
        }

        // 2. which of them are actually on this machine
        var det = ReadJson("detected_games.json");
        if (det is { } d && d.ValueKind == JsonValueKind.Object)
        {
            var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var p in d.EnumerateObject())
                if (p.Value.ValueKind == JsonValueKind.String)
                    map[p.Name] = p.Value.GetString() ?? "";
            foreach (var g in games)
                if (map.TryGetValue(g.Id, out var path) && Directory.Exists(path))
                    g.InstallPath = path;
        }

        // Installed first, then featured, then the catalog's own order — the
        // 10ft shell must open on what the player can actually press play on.
        return games
            .Where(g => !string.IsNullOrEmpty(g.Display))
            .OrderByDescending(g => g.Installed)
            .ThenByDescending(g => g.Featured)
            .ThenBy(g => g.SortOrder)
            .ThenBy(g => g.Display, StringComparer.CurrentCulture)
            .ToList();
    }

    // ---------------------------------------------------------------- art

    private static string CachePath(string url)
    {
        Directory.CreateDirectory(ArtDir);
        byte[] h = SHA256.HashData(Encoding.UTF8.GetBytes(url));
        string name = Convert.ToHexString(h)[..24];
        string ext = Path.GetExtension(new Uri(url).AbsolutePath);
        if (string.IsNullOrEmpty(ext) || ext.Length > 6) ext = ".img";
        return Path.Combine(ArtDir, name + ext);
    }

    /// <summary>
    /// Local path for a remote art URL, downloading once and caching forever.
    /// Returns null on any failure — every caller degrades to a themed
    /// placeholder rather than showing a broken tile.
    /// </summary>
    public static async Task<string?> ArtAsync(string? url)
    {
        if (string.IsNullOrWhiteSpace(url)) return null;
        try
        {
            string p = CachePath(url);
            if (File.Exists(p) && new FileInfo(p).Length > 0) return p;
            byte[] bytes = await Http.GetByteArrayAsync(url).ConfigureAwait(false);
            if (bytes.Length == 0) return null;
            string tmp = p + ".part";
            await File.WriteAllBytesAsync(tmp, bytes).ConfigureAwait(false);
            File.Move(tmp, p, overwrite: true);   // atomic — never a half file
            return p;
        }
        catch { return null; }
    }

    /// <summary>
    /// (files, bytes) held by the art cache — the shell's only disk footprint.
    ///
    /// 🔴 IT USED TO MEASURE A FOLDER NOTHING WRITES TO. `ArtDir` is
    /// ~/.translation_manager/biglaunch_art, and the only writer to it is a
    /// method with zero call sites; every cover the shell actually mirrors is
    /// written by ArtCache into %LocalAppData%\BigLaunch\art. So the
    /// maintenance screen reported "0 files" forever while the real cache grew
    /// without bound, and the one action offered to clear it cleared nothing.
    /// </summary>
    public static (int files, long bytes) ArtCacheStats()
    {
        try
        {
            var d = new DirectoryInfo(ArtCache.Folder);
            if (!d.Exists) return (0, 0);
            var f = d.GetFiles();
            return (f.Length, f.Sum(x => x.Length));
        }
        catch { return (0, 0); }
    }

    /// <summary>
    /// Drop the cached art. Safe by construction: every file here is
    /// re-downloadable from its own URL, so the worst case is one slow reload —
    /// which is exactly why this is the one maintenance action offered.
    /// </summary>
    public static int ClearArtCache()
    {
        int n = 0;
        ArtCache.ForgetAttempts();
        try
        {
            var d = new DirectoryInfo(ArtCache.Folder);
            if (!d.Exists) return 0;
            foreach (var f in d.GetFiles())
            {
                try { f.Delete(); n++; } catch { /* a locked file is skipped, not fatal */ }
            }
        }
        catch { }
        return n;
    }

    // ------------------------------------------------------- handoff

    /// <summary>Path to the installed desktop launcher, if present.</summary>
    public static string? LauncherExe()
    {
        foreach (var root in new[]
        {
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData) + @"\Programs",
        })
        {
            try
            {
                string p = Path.Combine(root, "Translation Manager", "TranslationManager.exe");
                if (File.Exists(p)) return p;
            }
            catch { }
        }
        return null;
    }

    /// <summary>
    /// Hand off to the desktop launcher — optionally deep-linked to one game.
    /// This is the "switch between the two shells" path.
    /// </summary>
    public static bool OpenDesktop(string? gameId = null)
    {
        string? exe = LauncherExe();
        if (exe is null) return false;
        try
        {
            var psi = new ProcessStartInfo(exe) { UseShellExecute = true, WorkingDirectory = Path.GetDirectoryName(exe)! };
            if (!string.IsNullOrEmpty(gameId)) psi.Arguments = $"hebrewhub://game/{gameId}";
            Process.Start(psi);
            return true;
        }
        catch { return false; }
    }

    /// <summary>Launch a detected game by its own executable.</summary>
    public static bool Play(GameEntry g)
    {
        if (!g.Installed) return false;
        try
        {
            // Prefer the biggest .exe that isn't an obvious helper — the same
            // heuristic ladder the launcher uses, kept simple here.
            var bad = new[] { "crash", "report", "setup", "install", "unins", "launcher", "redist", "vc_", "directx" };
            var exe = new DirectoryInfo(g.InstallPath!)
                .EnumerateFiles("*.exe", SearchOption.AllDirectories)
                .Where(f => !bad.Any(b => f.Name.ToLowerInvariant().Contains(b)))
                .OrderByDescending(f => f.Length)
                .FirstOrDefault();
            if (exe is null) return false;
            Process.Start(new ProcessStartInfo(exe.FullName)
            {
                UseShellExecute = true,
                WorkingDirectory = exe.DirectoryName!
            });
            return true;
        }
        catch { return false; }
    }
}
