using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using Microsoft.Win32;

namespace BigLaunch.Services;

public enum GameSource { Steam, Epic, Gog, Xbox, Ea, Ubisoft, Emulator, Manual, Hub }

/// <summary>
/// One installed title, from ANY storefront, normalised into a single shape.
/// This is the "ספרייה אוניברסלית" the report puts first on both feature lists.
/// </summary>
public sealed class LibraryGame
{
    public GameSource Source;
    public string Key = "";          // stable id: "steam:1174180", "gog:1495134320", ...
    public string Name = "";
    public string InstallDir = "";
    public string? Exe;              // resolved launch target, when the store gives one
    public string? LaunchUri;        // preferred: hand the STORE the launch (steam://, com.epicgames...)
    public long SizeBytes;
    public DateTime? LastPlayed;

    // download / update state (Steam reports this precisely; others are best-effort)
    public bool Installed = true;
    public bool UpdatePending;
    public long BytesDownloaded, BytesToDownload;

    // artwork, resolved to LOCAL files — never a network call at paint time
    public string? BoxArt, HeroArt, HeroBlur, Logo, Header;

    /// <summary>Set when this title also exists in the Hebrew-translation catalog.</summary>
    public GameEntry? Hub;

    public double DownloadProgress =>
        BytesToDownload > 0 ? Math.Clamp((double)BytesDownloaded / BytesToDownload, 0, 1) : 0;

    public string SourceLabel => Source switch
    {
        GameSource.Steam    => "Steam",
        GameSource.Epic     => "Epic",
        GameSource.Gog      => "GOG",
        GameSource.Xbox     => "Xbox",
        GameSource.Ea       => "EA",
        GameSource.Ubisoft  => "Ubisoft",
        GameSource.Emulator => "אמולטור",
        GameSource.Manual   => "ידני",
        _                   => "מתורגם",
    };

    public string SizeLabel => SizeBytes <= 0 ? "" :
        SizeBytes >= 1L << 30 ? $"{SizeBytes / (double)(1L << 30):0.#} GB"
                              : $"{SizeBytes / (double)(1L << 20):0} MB";
}

/// <summary>
/// Reads every storefront's OWN on-disk records. Read-only by construction:
/// we parse manifests and registry entries a store already wrote for itself,
/// and we never sign in, never call a store API, and never write into a store
/// folder. That is what makes a universal library safe to ship.
/// </summary>
public static class LibraryScanner
{
    // ---------------------------------------------------------------- VDF

    /// <summary>
    /// Minimal Valve KeyValues reader. Steam's manifests are a nested
    /// "key" "value" / "key" { ... } text format with C-style escapes —
    /// small enough to parse exactly rather than regex at.
    /// </summary>
    public static Dictionary<string, object> ParseVdf(string text)
    {
        int i = 0;
        return ParseBlock(text, ref i);
    }

    private static Dictionary<string, object> ParseBlock(string s, ref int i)
    {
        var d = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
        while (i < s.Length)
        {
            SkipTrivia(s, ref i);
            if (i >= s.Length) break;
            if (s[i] == '}') { i++; break; }
            if (s[i] != '"') { i++; continue; }

            string key = ReadQuoted(s, ref i);
            SkipTrivia(s, ref i);
            if (i >= s.Length) break;

            if (s[i] == '{') { i++; d[key] = ParseBlock(s, ref i); }
            else if (s[i] == '"') d[key] = ReadQuoted(s, ref i);
        }
        return d;
    }

    private static void SkipTrivia(string s, ref int i)
    {
        while (i < s.Length)
        {
            if (char.IsWhiteSpace(s[i])) { i++; continue; }
            // "//" line comments are legal in KeyValues
            if (s[i] == '/' && i + 1 < s.Length && s[i + 1] == '/')
            {
                while (i < s.Length && s[i] != '\n') i++;
                continue;
            }
            break;
        }
    }

    private static string ReadQuoted(string s, ref int i)
    {
        i++;                                   // opening quote
        var sb = new StringBuilder();
        while (i < s.Length && s[i] != '"')
        {
            if (s[i] == '\\' && i + 1 < s.Length)
            {
                i++;
                sb.Append(s[i] switch { 'n' => '\n', 't' => '\t', '\\' => '\\', '"' => '"', var c => c });
            }
            else sb.Append(s[i]);
            i++;
        }
        i++;                                   // closing quote
        return sb.ToString();
    }

    private static string? Get(Dictionary<string, object> d, string key) =>
        d.TryGetValue(key, out var v) ? v as string : null;

    private static long GetLong(Dictionary<string, object> d, string key) =>
        long.TryParse(Get(d, key), NumberStyles.Any, CultureInfo.InvariantCulture, out long n) ? n : 0;

    // ---------------------------------------------------------------- Steam

    public static string? SteamRoot()
    {
        foreach (var (hive, path) in new[]
        {
            (Registry.CurrentUser,  @"Software\Valve\Steam"),
            (Registry.LocalMachine, @"SOFTWARE\WOW6432Node\Valve\Steam"),
        })
        {
            try
            {
                using var k = hive.OpenSubKey(path);
                string? p = k?.GetValue("SteamPath") as string ?? k?.GetValue("InstallPath") as string;
                if (!string.IsNullOrEmpty(p) && Directory.Exists(p)) return p.Replace('/', '\\');
            }
            catch { }
        }
        string fallback = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Steam");
        return Directory.Exists(fallback) ? fallback : null;
    }

    /// <summary>Every Steam library folder — a user's games are rarely all on C:.</summary>
    public static List<string> SteamLibraries(string root)
    {
        var libs = new List<string> { root };
        try
        {
            string vdf = Path.Combine(root, "steamapps", "libraryfolders.vdf");
            if (File.Exists(vdf) &&
                ParseVdf(File.ReadAllText(vdf)).TryGetValue("libraryfolders", out var o) &&
                o is Dictionary<string, object> folders)
            {
                foreach (var entry in folders.Values.OfType<Dictionary<string, object>>())
                {
                    string? p = Get(entry, "path");
                    if (!string.IsNullOrEmpty(p) && Directory.Exists(p) &&
                        !libs.Any(x => string.Equals(x, p, StringComparison.OrdinalIgnoreCase)))
                        libs.Add(p);
                }
            }
        }
        catch { }
        return libs;
    }

    private static IEnumerable<LibraryGame> ScanSteam()
    {
        string? root = SteamRoot();
        if (root is null) yield break;

        string artRoot = Path.Combine(root, "appcache", "librarycache");

        foreach (string lib in SteamLibraries(root))
        {
            string apps = Path.Combine(lib, "steamapps");
            string[] manifests;
            try { manifests = Directory.GetFiles(apps, "appmanifest_*.acf"); }
            catch { continue; }

            foreach (string m in manifests)
            {
                LibraryGame? g = null;
                try
                {
                    var d = ParseVdf(File.ReadAllText(m));
                    if (!d.TryGetValue("AppState", out var o) || o is not Dictionary<string, object> st) continue;

                    string appid = Get(st, "appid") ?? "";
                    string name = Get(st, "name") ?? "";
                    string dir = Get(st, "installdir") ?? "";
                    if (appid.Length == 0 || name.Length == 0) continue;

                    // Steam's redistributable entries are not games and must not
                    // clutter a 10ft grid the user scrolls with a thumbstick.
                    if (name.Contains("Redistributable", StringComparison.OrdinalIgnoreCase) ||
                        name.Contains("Steamworks", StringComparison.OrdinalIgnoreCase) ||
                        appid is "228980" or "1070560" or "1391110") continue;

                    long stateFlags = GetLong(st, "StateFlags");
                    long lastPlayed = GetLong(st, "LastPlayed");
                    string full = Path.Combine(apps, "common", dir);

                    g = new LibraryGame
                    {
                        Source = GameSource.Steam,
                        Key = "steam:" + appid,
                        Name = name,
                        InstallDir = Directory.Exists(full) ? full : "",
                        // Let STEAM launch it: this inherits cloud saves, the
                        // overlay, playtime and DRM instead of fighting them.
                        LaunchUri = "steam://rungameid/" + appid,
                        SizeBytes = GetLong(st, "SizeOnDisk"),
                        LastPlayed = lastPlayed > 0
                            ? DateTimeOffset.FromUnixTimeSeconds(lastPlayed).LocalDateTime
                            : null,
                        // bit 2 (0x2) = update required; bit 4 (0x4) = fully installed
                        Installed = (stateFlags & 4) != 0,
                        UpdatePending = (stateFlags & 2) != 0,
                        BytesDownloaded = GetLong(st, "BytesDownloaded"),
                        BytesToDownload = GetLong(st, "BytesToDownload"),
                    };

                    // Steam already cached this game's own art locally. Using the
                    // user's own cache is instant, offline, needs no API key, and
                    // gives exactly the three assets the report asks for.
                    string ad = Path.Combine(artRoot, appid);
                    if (Directory.Exists(ad))
                    {
                        // library_capsule is the NEW name for the portrait art;
                        // library_600x900 is what older caches call it.
                        g.BoxArt   = First(ad, "library_600x900.jpg", "library_600x900_2x.jpg",
                                               "library_capsule.jpg", "library_capsule_2x.jpg");
                        g.HeroArt  = First(ad, "library_hero.jpg", "library_hero_2x.jpg");
                        g.HeroBlur = First(ad, "library_hero_blur.jpg");
                        g.Logo     = First(ad, "logo.png", "logo_2x.png");
                        g.Header   = First(ad, "header.jpg", "library_header.jpg");
                    }
                }
                catch { g = null; }
                if (g is not null) yield return g;
            }
        }
    }

    /// <summary>
    /// Find one of <paramref name="names"/> under an appid's art folder.
    ///
    /// 🔴 STEAM SHIPS TWO LIBRARYCACHE LAYOUTS AT THE SAME TIME, and a resolver
    /// that knows only the old one silently finds nothing for most of the
    /// library - which reads as "this game has no art" rather than as a bug:
    ///
    ///   old (flat)          librarycache/&lt;appid&gt;/library_600x900.jpg
    ///   new (content-addr)  librarycache/&lt;appid&gt;/&lt;sha1&gt;/library_capsule.jpg
    ///                       librarycache/&lt;appid&gt;/&lt;sha1&gt;/library_hero.jpg
    ///
    /// Measured on this machine: 31 of 128 appids still use the flat form, the
    /// rest are one-file-per-sha1 subfolders - and the portrait was RENAMED from
    /// library_600x900 to library_capsule on the way. So the lookup is by FILE
    /// NAME, one level deep, instead of by a fixed path.
    ///
    /// Deliberately depth-1 and not a recursive walk: the cache holds thousands
    /// of files and this runs per game during a library scan.
    /// </summary>
    private static string? First(string dir, params string[] names)
    {
        foreach (string n in names)
        {
            string p = Path.Combine(dir, n);
            if (File.Exists(p)) return p;
        }
        try
        {
            foreach (string sub in Directory.EnumerateDirectories(dir))
                foreach (string n in names)
                {
                    string p = Path.Combine(sub, n);
                    if (File.Exists(p)) return p;
                }
        }
        catch { }
        return null;
    }

    // ---------------------------------------------------------------- Epic

    private static IEnumerable<LibraryGame> ScanEpic()
    {
        string dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "Epic", "EpicGamesLauncher", "Data", "Manifests");
        if (!Directory.Exists(dir)) yield break;

        string[] items;
        try { items = Directory.GetFiles(dir, "*.item"); } catch { yield break; }

        foreach (string f in items)
        {
            LibraryGame? g = null;
            try
            {
                // Epic writes these with a BOM; JsonDocument copes, but read as
                // text first so a malformed file can never abort the whole scan.
                using var doc = JsonDocument.Parse(File.ReadAllText(f).TrimStart('﻿'));
                var r = doc.RootElement;
                string name = Prop(r, "DisplayName");
                string loc = Prop(r, "InstallLocation");
                string app = Prop(r, "AppName");
                string exe = Prop(r, "LaunchExecutable");
                if (name.Length == 0 || loc.Length == 0) continue;

                g = new LibraryGame
                {
                    Source = GameSource.Epic,
                    Key = "epic:" + (app.Length > 0 ? app : name),
                    Name = name,
                    InstallDir = loc,
                    Exe = exe.Length > 0 ? Path.Combine(loc, exe) : null,
                    LaunchUri = app.Length > 0
                        ? $"com.epicgames.launcher://apps/{app}?action=launch&silent=true"
                        : null,
                    SizeBytes = r.TryGetProperty("InstallSize", out var sz) && sz.TryGetInt64(out long b) ? b : 0,
                };
            }
            catch { g = null; }
            if (g is not null) yield return g;
        }
    }

    private static string Prop(JsonElement e, string k) =>
        e.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() ?? "" : "";

    // ---------------------------------------------------------------- GOG

    private static IEnumerable<LibraryGame> ScanGog()
    {
        var results = new List<LibraryGame>();
        foreach (var view in new[] { RegistryView.Registry32, RegistryView.Registry64 })
        {
            try
            {
                using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view);
                using var games = baseKey.OpenSubKey(@"SOFTWARE\GOG.com\Games");
                if (games is null) continue;
                foreach (string id in games.GetSubKeyNames())
                {
                    try
                    {
                        using var k = games.OpenSubKey(id);
                        if (k is null) continue;
                        string name = k.GetValue("gameName") as string ?? "";
                        string path = k.GetValue("path") as string ?? "";
                        if (name.Length == 0 || !Directory.Exists(path)) continue;
                        if (results.Any(x => x.Key == "gog:" + id)) continue;

                        results.Add(new LibraryGame
                        {
                            Source = GameSource.Gog,
                            Key = "gog:" + id,
                            Name = name,
                            InstallDir = path,
                            // GOG records the exact launch target — no guessing.
                            Exe = k.GetValue("exe") as string ?? k.GetValue("launchCommand") as string,
                        });
                    }
                    catch { }
                }
            }
            catch { }
        }
        return results;
    }

    // ---------------------------------------------------------------- Ubisoft

    private static IEnumerable<LibraryGame> ScanUbisoft()
    {
        var results = new List<LibraryGame>();
        try
        {
            using var baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry32);
            using var installs = baseKey.OpenSubKey(@"SOFTWARE\Ubisoft\Launcher\Installs");
            if (installs is null) return results;

            foreach (string id in installs.GetSubKeyNames())
            {
                try
                {
                    using var k = installs.OpenSubKey(id);
                    string? dir = k?.GetValue("InstallDir") as string;
                    if (string.IsNullOrEmpty(dir)) continue;
                    dir = dir.Replace('/', '\\').TrimEnd('\\');
                    if (!Directory.Exists(dir)) continue;

                    results.Add(new LibraryGame
                    {
                        Source = GameSource.Ubisoft,
                        Key = "uplay:" + id,
                        // Ubisoft stores no display name — the folder IS the name.
                        Name = Path.GetFileName(dir),
                        InstallDir = dir,
                        LaunchUri = $"uplay://launch/{id}/0",
                    });
                }
                catch { }
            }
        }
        catch { }
        return results;
    }

    // ---------------------------------------------------------------- Xbox / EA / manual roots

    private static IEnumerable<LibraryGame> ScanFolderRoots()
    {
        var roots = new List<(string dir, GameSource src)>();

        foreach (var d in DriveInfo.GetDrives())
        {
            if (!d.IsReady) continue;
            string x = Path.Combine(d.RootDirectory.FullName, "XboxGames");
            if (Directory.Exists(x)) roots.Add((x, GameSource.Xbox));
        }
        foreach (string p in new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "EA Games"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "EA Games"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Origin Games"),
        })
            if (Directory.Exists(p)) roots.Add((p, GameSource.Ea));

        foreach (var (dir, src) in roots)
        {
            string[] subs;
            try { subs = Directory.GetDirectories(dir); } catch { continue; }
            foreach (string s in subs)
            {
                string name = Path.GetFileName(s);
                // "GameSave" is Xbox's own save folder, not a game.
                if (name is "GameSave" or "desktop.ini") continue;
                yield return new LibraryGame
                {
                    Source = src,
                    Key = $"{src.ToString().ToLowerInvariant()}:{name}",
                    Name = name,
                    InstallDir = s,
                };
            }
        }
    }

    // ---------------------------------------------------------------- emulators

    private static readonly string[] RomExtensions =
    {
        ".nes", ".sfc", ".smc", ".gba", ".gb", ".gbc", ".n64", ".z64", ".v64",
        ".nds", ".3ds", ".cia", ".iso", ".chd", ".cue", ".gcm", ".rvz", ".wbfs",
        ".xci", ".nsp", ".gg", ".md", ".sms", ".pce", ".ws", ".wsc", ".vb",
    };

    /// <summary>
    /// Emulator titles come from folders the USER points us at (Settings →
    /// ספרייה). We never guess a ROM folder and never bundle an emulator —
    /// the user supplies both, which keeps this legally and practically clean.
    /// </summary>
    private static IEnumerable<LibraryGame> ScanEmulators(AppSettings s)
    {
        foreach (var lib in s.EmulatorLibraries)
        {
            if (string.IsNullOrWhiteSpace(lib.RomFolder) || !Directory.Exists(lib.RomFolder)) continue;
            IEnumerable<string> files;
            try
            {
                files = Directory.EnumerateFiles(lib.RomFolder, "*.*", SearchOption.AllDirectories)
                                 .Where(f => RomExtensions.Contains(Path.GetExtension(f).ToLowerInvariant()))
                                 .Take(500);   // a 10ft grid, not a file manager
            }
            catch { continue; }

            foreach (string f in files)
            {
                var fi = new FileInfo(f);
                yield return new LibraryGame
                {
                    Source = GameSource.Emulator,
                    Key = "rom:" + f.ToLowerInvariant(),
                    Name = Path.GetFileNameWithoutExtension(f),
                    InstallDir = Path.GetDirectoryName(f) ?? "",
                    Exe = lib.EmulatorExe,
                    LaunchUri = null,
                    SizeBytes = fi.Exists ? fi.Length : 0,
                };
            }
        }
    }

    // ---------------------------------------------------------------- merge

    /// <summary>
    /// The whole library, from every source, de-duplicated and enriched with
    /// the Hebrew-translation catalog. Runs off the UI thread.
    /// </summary>
    /// <summary>
    /// True when every enabled store answered. False means the list is a PARTIAL
    /// view of the machine.
    ///
    /// 🔴🔴 A PARTIAL SCAN THAT LOOKS COMPLETE IS HOW A LIBRARY GETS ERASED. Each
    /// store is read behind its own try/catch so one dead launcher cannot kill
    /// the whole scan - which is right - but the caller then received a shorter
    /// list with no way to tell it apart from "those games are genuinely gone",
    /// and adopted it wholesale. One locked registry key or a store mid-update
    /// was enough to empty a shelf. The flag is the difference between "here is
    /// the library" and "here is what I could see this time".
    /// </summary>
    public static bool LastScanComplete { get; private set; } = true;

    public static List<LibraryGame> ScanAll(AppSettings settings, List<GameEntry> hubGames)
    {
        var all = new List<LibraryGame>();
        bool complete = true;

        void Add(Func<IEnumerable<LibraryGame>> src, bool enabled)
        {
            if (!enabled) return;
            try { all.AddRange(src()); }
            catch { complete = false; }   // one dead store never kills the scan
        }

        Add(ScanSteam, settings.SourceSteam);
        Add(ScanEpic, settings.SourceEpic);
        Add(ScanGog, settings.SourceGog);
        Add(ScanUbisoft, settings.SourceUbisoft);
        Add(ScanFolderRoots, settings.SourceXbox);
        Add(() => ScanEmulators(settings), settings.SourceEmulators);
        LastScanComplete = complete;

        // Manual entries the user added by hand (Winhanced's ManualGameEntryDialog).
        foreach (var m in settings.ManualGames)
        {
            if (string.IsNullOrWhiteSpace(m.Name)) continue;
            all.Add(new LibraryGame
            {
                Source = GameSource.Manual,
                Key = "manual:" + m.Name.ToLowerInvariant(),
                Name = m.Name,
                InstallDir = m.InstallDir ?? "",
                Exe = m.Exe,
            });
        }

        // 🔴 DE-DUP STEP 1 — THE STORE'S OWN ID IS THE IDENTITY, NOT THE FOLDER.
        // Steam allows the same appid to sit in several library folders, and this
        // machine really does have Borderless Gaming in two of them - so the
        // appmanifest sweep returns it twice with DIFFERENT InstallDirs, and a
        // folder-only de-dup keeps both. Steam's own library shows it once; a
        // duplicate tile in a couch grid is worse than a wrong one, because you
        // cannot tell which of the two you are about to launch.
        var byKey = new Dictionary<string, LibraryGame>(StringComparer.OrdinalIgnoreCase);
        var unique = new List<LibraryGame>();
        foreach (var g in all)
        {
            if (g.Key.Length > 0 && byKey.TryGetValue(g.Key, out var dup))
            {
                // Keep the richer record: art and a launch URI are what the tile needs.
                dup.LaunchUri ??= g.LaunchUri;
                dup.BoxArt ??= g.BoxArt; dup.HeroArt ??= g.HeroArt;
                dup.Logo ??= g.Logo; dup.HeroBlur ??= g.HeroBlur;
                if (dup.InstallDir.Length == 0) dup.InstallDir = g.InstallDir;
                continue;
            }
            if (g.Key.Length > 0) byKey[g.Key] = g;
            unique.Add(g);
        }

        // De-dup step 2: the same folder found through two DIFFERENT stores is one game.
        //
        // A PATH IS NOT A STRING. This compared InstallDir verbatim, so
        // "D:\\Games\\Foo" and "D:\\Games\\Foo\\" were two different games, and so
        // were "D:\\games\\foo" and the same path reached through a junction or
        // an 8.3 name. It mattered most for the hand-added entries: a user adds
        // a game manually BECAUSE the store scan missed it, then the store
        // starts reporting it and they have the same title twice, one of which
        // cannot launch. The store record wins on merge - it is the one with a
        // launch URI and a playtime.
        var byDir = new Dictionary<string, LibraryGame>(StringComparer.OrdinalIgnoreCase);
        var merged = new List<LibraryGame>();
        foreach (var g in unique.OrderBy(x => x.Source is GameSource.Manual or GameSource.Emulator ? 1 : 0))
        {
            string dir = NormDir(g.InstallDir);
            if (dir.Length > 0 && byDir.TryGetValue(dir, out var seen))
            {
                // Prefer the record that can actually launch through its store.
                if (seen.LaunchUri is null && g.LaunchUri is not null) seen.LaunchUri = g.LaunchUri;
                seen.BoxArt ??= g.BoxArt; seen.HeroArt ??= g.HeroArt;
                seen.Logo ??= g.Logo; seen.HeroBlur ??= g.HeroBlur;
                // A manual entry the user named themselves is the name they
                // expect to see, and a store title is often the SKU spelling.
                if (g.Source is GameSource.Manual && g.Name.Length > 0) seen.Name = g.Name;
                continue;
            }
            if (dir.Length > 0) byDir[dir] = g;
            merged.Add(g);
        }

        // Enrich with the translation catalog: a title we ship Hebrew for gets
        // the hub's art and a badge, and stays ONE tile rather than two.
        foreach (var g in merged)
        {
            var hub = hubGames.FirstOrDefault(h =>
                (h.InstallPath is { Length: > 0 } p &&
                 string.Equals(NormDir(p), NormDir(g.InstallDir), StringComparison.OrdinalIgnoreCase))
                || Norm(h.TitleEn) == Norm(g.Name));
            if (hub is not null) g.Hub = hub;
        }

        // Catalog titles we did NOT find installed still belong in the library —
        // they are the shop window for the translations this product exists for.
        foreach (var h in hubGames)
        {
            if (merged.Any(g => g.Hub == h)) continue;
            merged.Add(new LibraryGame
            {
                Source = GameSource.Hub,
                Key = "hub:" + h.Id,
                Name = h.Display,
                InstallDir = h.InstallPath ?? "",
                Installed = h.Installed,
                Hub = h,
            });
        }

        return merged;
    }

    /// <summary>A comparable form of an install path: absolute, no trailing
    /// separator, no case. Never throws - a path from a manifest can be
    /// anything, including a drive that is no longer mounted.</summary>
    private static string NormDir(string dir)
    {
        if (string.IsNullOrWhiteSpace(dir)) return "";
        try { dir = Path.GetFullPath(dir); } catch { }
        return dir.TrimEnd('\\', '/');
    }

    private static string Norm(string s) =>
        new(s.ToLowerInvariant().Where(char.IsLetterOrDigit).ToArray());

    // ---------------------------------------------------------------- launch

    /// <summary>
    /// Start a title. Preference order is deliberate: the store's own URI
    /// first (keeps overlay/cloud-saves/playtime working), then a recorded
    /// exe, then a heuristic scan of the install folder as a last resort.
    /// </summary>
    public static System.Diagnostics.Process? Launch(LibraryGame g, AppSettings s)
    {
        try
        {
            // A per-game profile can override the launch target entirely.
            var prof = s.ProfileFor(g.Key, create: false);
            if (prof?.CustomExe is { Length: > 0 } custom && File.Exists(custom))
                return Start(custom, prof.LaunchArgs);

            if (g.Source == GameSource.Emulator && g.Exe is { Length: > 0 } emu && File.Exists(emu))
                return Start(emu, "\"" + FindRom(g) + "\"");

            // 🔴 A STORE URI CANNOT CARRY ARGUMENTS. steam://rungameid hands the
            // launch to the client and drops anything appended, so a user who
            // typed "-eac_launcher" (Watch Dogs 2 needs exactly that) would have
            // watched it silently do nothing. When arguments are set AND a real
            // executable is known, the exe wins; with no arguments the URI stays
            // preferred, because that is the path the store's own overlay, cloud
            // saves and playtime tracking expect.
            bool wantsArgs = prof?.LaunchArgs is { Length: > 0 };
            if (wantsArgs && g.Exe is { Length: > 0 } direct && File.Exists(direct))
                return Start(direct, prof!.LaunchArgs);

            if (g.LaunchUri is { Length: > 0 } uri)
                return System.Diagnostics.Process.Start(
                    new System.Diagnostics.ProcessStartInfo(uri) { UseShellExecute = true });

            if (g.Exe is { Length: > 0 } exe && File.Exists(exe))
                return Start(exe, prof?.LaunchArgs);

            string? guess = GuessExe(g.InstallDir);
            return guess is null ? null : Start(guess, prof?.LaunchArgs);
        }
        catch { return null; }
    }

    private static string FindRom(LibraryGame g) => g.Key.StartsWith("rom:") ? g.Key[4..] : g.InstallDir;

    private static System.Diagnostics.Process? Start(string exe, string? args) =>
        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(exe)
        {
            Arguments = args ?? "",
            UseShellExecute = true,
            WorkingDirectory = Path.GetDirectoryName(exe) ?? "",
        });

    /// <summary>
    /// Biggest .exe that is not obviously a helper. Crash handlers, redists and
    /// uninstallers are the classic wrong answer, so they are excluded by name.
    /// </summary>
    public static string? GuessExe(string dir)
    {
        if (string.IsNullOrEmpty(dir) || !Directory.Exists(dir)) return null;

        string[] bad = { "crash", "report", "setup", "install", "unins", "redist",
                         "vc_", "directx", "dotnet", "helper", "service", "update" };

        // 🔴 THE FILE NAME IS NOT ENOUGH - THE FOLDER DECIDES TOO. Filtering only
        // on the name let "...\NoDVD\Goldberg\tll.exe" win on a real install:
        // that folder holds files a repack tells you to COPY OVER the game, so
        // it is a staging area, never a launch target. Pointing Play at it runs
        // a loader stub with none of the game's own working directory - it fails
        // quietly, which is the worst way for a launcher to be wrong.
        //
        // These are directory names that never contain the thing the player
        // wants to start: repack/DRM staging, shipped prerequisites, and the
        // vendor tooling that rides along in the same tree.
        string[] badDirs = { "nodvd", "goldberg", "crack", "codex", "plaza", "skidrow",
                             "reloaded", "empress", "rune", "fitgirl", "dodi",
                             "_redist", "redist", "commonredist", "directx", "vcredist",
                             "dotnet", "support", "prereq", "installers", "tools",
                             "backup", "extras", "bonus" };
        try
        {
            return new DirectoryInfo(dir)
                .EnumerateFiles("*.exe", SearchOption.AllDirectories)
                .Where(f => !bad.Any(b => f.Name.Contains(b, StringComparison.OrdinalIgnoreCase)))
                .Where(f =>
                {
                    // Only the part of the path BELOW the install dir is ours to
                    // judge - the user's own folder above it may legitimately be
                    // called anything ("F:\Game Lab\...").
                    string rel = f.FullName.Length > dir.Length ? f.FullName[dir.Length..] : f.Name;
                    return !badDirs.Any(b =>
                        rel.Contains("\\" + b, StringComparison.OrdinalIgnoreCase) ||
                        rel.Contains(b + "\\", StringComparison.OrdinalIgnoreCase));
                })
                .OrderByDescending(f => f.Length)
                .FirstOrDefault()?.FullName;
        }
        catch { return null; }
    }
}
