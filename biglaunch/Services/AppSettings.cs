using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace BigLaunch.Services;

public sealed class EmulatorLibrary
{
    public string Name { get; set; } = "";
    public string EmulatorExe { get; set; } = "";
    public string RomFolder { get; set; } = "";
}

public sealed class ManualGame
{
    public string Name { get; set; } = "";
    public string? InstallDir { get; set; }
    public string? Exe { get; set; }
}

/// <summary>
/// A per-game profile. This is our OWN local "Smart Profile": the idea from
/// Winhanced, with none of its community dataset — every value here is set by
/// this user, on this machine, for this game.
/// </summary>
public sealed class GameProfile
{
    public string Key { get; set; } = "";
    public string? CustomExe { get; set; }
    public string? LaunchArgs { get; set; }
    public string? CustomBoxArt { get; set; }
    public string? CustomHeroArt { get; set; }
    public string? CustomLogo { get; set; }
    public bool Favorite { get; set; }
    public bool Hidden { get; set; }
    public bool SuspendOnFocusLoss { get; set; }
    /// <summary>Seconds played, accumulated by our own session tracking.</summary>
    public long PlaySeconds { get; set; }
    public DateTime? LastPlayed { get; set; }
    public int LaunchCount { get; set; }
}

/// <summary>
/// A user-made collection - Steam Big Picture's own library concept, entirely
/// local. Membership is by game Key, so a collection survives a re-scan, a
/// moved install folder, and a store that renumbers its own ids.
/// </summary>
public sealed class GameCollection
{
    public string Name { get; set; } = "";
    public List<string> Keys { get; set; } = new();
}

/// <summary>
/// Everything the shell remembers. One JSON file, written atomically, and
/// never fatal: a corrupt or missing file yields defaults rather than a
/// crash — the same self-healing discipline the launcher's own state uses.
/// </summary>
public sealed class AppSettings
{
    // ---- library sources -------------------------------------------------
    public bool SourceSteam { get; set; } = true;
    public bool SourceEpic { get; set; } = true;
    public bool SourceGog { get; set; } = true;
    public bool SourceUbisoft { get; set; } = true;
    public bool SourceXbox { get; set; } = true;
    public bool SourceEmulators { get; set; } = true;

    /// <summary>
    /// Which button prompts to draw: "auto" | "ps5" | "ps4" | "xbox" | "keyboard".
    ///
    /// 🔴 AUTO-DETECT CANNOT ALWAYS BE RIGHT, SO THE USER GETS THE LAST WORD.
    /// A DualSense driven through Steam Input, DS4Windows or Windows' own
    /// pairing arrives as a textbook Xbox pad — XInput reports it, the Sony
    /// VID/PID is gone, and every honest probe on the machine answers "Xbox".
    /// Detection is not failing there; it is reporting what the system sees. But
    /// the person on the couch is holding ✕ ○ □ △, and no amount of probing can
    /// out-argue that. An override is the only correct answer, and it stays the
    /// default-off "auto" so nobody has to set it for the common case.
    /// </summary>
    public string PadStyle { get; set; } = "auto";

    /// <summary>
    /// How much bigger or smaller everything on a shelf is drawn: 0.85 / 1.0 /
    /// 1.15 / 1.3. A 10ft shell is read from wildly different distances - a 24"
    /// monitor at desk range and a 55" TV across a room are the same pixels and
    /// nothing like the same apparent size - so this is a reach setting, not a
    /// taste one.
    /// </summary>
    public double UiScale { get; set; } = 0.85;

    /// <summary>
    /// What a card actually shows: "full" (art + badges), "art" (art only, no
    /// plate text) or "text" (a compact row, no art at all). The last one is
    /// what makes a library of a few hundred titles navigable, and it is also
    /// the only mode that stays readable when a game has no cover.
    /// </summary>
    public string CardStyle { get; set; } = "full";

    public List<EmulatorLibrary> EmulatorLibraries { get; set; } = new();
    public List<ManualGame> ManualGames { get; set; } = new();
    public List<GameProfile> Profiles { get; set; } = new();
    public List<GameCollection> Collections { get; set; } = new();

    /// <summary>Accent colour as #RRGGBB, or empty to follow the Windows accent.
    /// Winhanced ships a fixed gradient row (yellow through purple) rather than a
    /// full picker - a shell has one accent, and a free colour wheel mostly
    /// produces ones that fail against the dark ground.</summary>
    public string AccentHex { get; set; } = "";

    /// <summary>How the library is ordered: installed / played / name / size.
    /// Remembered, because a sort you have to re-pick every launch is not a
    /// preference - it is a chore.</summary>
    public string SortMode { get; set; } = "installed";

    /// <summary>
    /// The library filter chip that was last active.
    ///
    /// The sort was remembered and the filter was not, which is the odder half
    /// of the pair: a user who keeps one collection open lands on "הכול" every
    /// launch and has to walk the chip strip back to it, while the sort they
    /// picked once survives forever. A collection that was deleted since is
    /// dropped on load rather than restored as an empty screen.
    /// </summary>
    public string LastFilter { get; set; } = "all";

    // ---- experience ------------------------------------------------------
    public bool SoundEnabled { get; set; } = true;
    public double SoundVolume { get; set; } = 0.35;
    public bool AnimationsEnabled { get; set; } = true;
    public bool GlassEnabled { get; set; } = true;

    /// <summary>
    /// The ambient backdrop: "accent" (two blobs in the chosen accent) or
    /// "rainbow" (the multi-colour wash that cycles its hue). The desktop
    /// launcher offers the same two under Appearance, and somebody who set one
    /// there expects the console shell to look like the app they came from.
    /// Whether it MOVES is not a third value - it follows AnimationsEnabled,
    /// exactly as the launcher's CSS drops the drift under reduce-motion.
    /// </summary>
    public string AmbientStyle { get; set; } = "rainbow";

    /// <summary>
    /// Rebound buttons, action name -> Pad / Key name. EMPTY MEANS DEFAULTS, and
    /// that matters: storing the whole table would freeze today's defaults into
    /// every settings file ever written, so a later change to a default would
    /// reach nobody who had ever opened this app. Only what the user actually
    /// changed is written down.
    /// </summary>
    /// <summary>
    /// Per-group size, as a multiplier ON TOP of <see cref="UiScale"/>. 1.0 is
    /// "whatever the chosen preset gives", which is why the sliders read 100% in
    /// the middle: the number is not an absolute size, it is how far this one
    /// group has been pushed away from the rest.
    ///
    /// Four groups because they are the four things that fight each other on a
    /// 10ft screen: the covers you are aiming at, the system row you glance at,
    /// the words you read, and the button prompts you only need until you know
    /// them. Somebody sitting close wants small covers and normal text; someone
    /// across a room wants the opposite; nobody wants one number for both.
    /// </summary>
    /// <summary>
    /// Which size baseline this file was written against.
    ///
    /// 🔴 A REBASE MUST NOT MOVE ANYONE'S SCREEN. The tuned sizes moved into the
    /// code as the new 100% (MainWindow.Sizes.GroupBase), and a file still
    /// holding the multipliers that PRODUCED those sizes would multiply them a
    /// second time - the shell would open a fifth larger than the day before for
    /// the one person who had already set it up. Bumping this stamps the file as
    /// rebased and resets the four multipliers exactly once.
    /// </summary>
    public int SizeBaseline { get; set; }

    public double ScaleTiles { get; set; } = 1.0;
    public double ScaleChrome { get; set; } = 1.0;
    public double ScaleText { get; set; } = 1.0;
    public double ScaleHints { get; set; } = 1.0;

    public Dictionary<string, string> PadMap { get; set; } = new();
    public Dictionary<string, string> KeyMap { get; set; } = new();

    /// <summary>
    /// Play the boot film. On by default - it is the product's opener and it
    /// covers the library scan - but it is ten seconds of every single launch,
    /// so somebody who opens this shell twenty times a day has to be able to
    /// turn it off. Skipping it per-launch is one keypress; this is for good.
    /// </summary>
    public bool IntroEnabled { get; set; } = true;
    public bool ShowTelemetry { get; set; } = true;
    public bool DiscordPresence { get; set; } = true;
    /// <summary>
    /// Discord Application ID for Rich Presence. Empty by default: an app id
    /// can only come from Discord's developer portal, so the feature reports
    /// "not configured" rather than pretending to work with an invented one.
    /// </summary>
    public string DiscordAppId { get; set; } = "";

    // ---- behaviour -------------------------------------------------------
    /// <summary>Opt-in: it watches OTHER processes' windows, so it defaults off.</summary>
    public bool LaunchWatcher { get; set; }
    public bool QuickResume { get; set; } = true;
    public bool MemoryGuard { get; set; } = true;
    public int MemoryWarnPercent { get; set; } = 88;
    public bool OnboardingDone { get; set; }
    public string? LastGameKey { get; set; }

    // ---- persistence -----------------------------------------------------

    [JsonIgnore] public static string FilePath =>
        Path.Combine(Catalog.StateDir, "biglaunch_settings.json");

    private static readonly JsonSerializerOptions Opts = new()
    {
        WriteIndented = true,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    /// <summary>The baseline the code currently draws at. See SizeBaseline.</summary>
    private const int CurrentSizeBaseline = 1;

    /// <summary>
    /// Carry an older settings file onto the current size baseline, once.
    ///
    /// The four multipliers a user had set to reach the tuned size are now the
    /// tuned size itself, so keeping them would apply it twice. Anything the
    /// user set BEYOND that is lost in this one migration - which is the honest
    /// trade: a screen that looks the same tomorrow as it did today, for
    /// everyone, instead of a screen that grows for the people who had already
    /// bothered to set it up.
    /// </summary>
    private static AppSettings Rebase(AppSettings s)
    {
        if (s.SizeBaseline >= CurrentSizeBaseline) return s;
        s.ScaleTiles = s.ScaleChrome = s.ScaleText = s.ScaleHints = 1.0;
        s.SizeBaseline = CurrentSizeBaseline;
        try { s.Save(); } catch { }
        return s;
    }

    public static AppSettings Load()
    {
        try
        {
            if (File.Exists(FilePath))
                return Rebase(JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(FilePath)) ?? new AppSettings());
            // FIRST RUN ONLY - inherit what Windows was already told. A fresh
            // file is born on the current baseline, so it is stamped, not reset.
            var seeded = SeedFromSystem(new AppSettings());
            seeded.SizeBaseline = CurrentSizeBaseline;
            return seeded;
        }
        catch
        {
            // A settings file we cannot read must never block the shell from
            // opening; the user gets defaults and can re-set them.
        }
        return new AppSettings();
    }

    /// <summary>
    /// Seed the two experience switches from the OS on the very first run.
    ///
    /// 🔴 A USER WHO TURNED THESE OFF IN WINDOWS HAS ALREADY ANSWERED. Both
    /// "Show animations" and "Transparency effects" are accessibility settings
    /// as much as performance ones - motion sensitivity and readability - and a
    /// shell that opens with a full-screen acrylic surface and sliding rows at
    /// someone who disabled exactly that has ignored a decision they went out
    /// of their way to make. This runs ONCE, when there is no settings file at
    /// all, so the user's own choice inside this app always wins afterwards.
    /// </summary>
    private static AppSettings SeedFromSystem(AppSettings s)
    {
        try { s.AnimationsEnabled = System.Windows.SystemParameters.ClientAreaAnimation; } catch { }
        try
        {
            // The transparency switch has no SystemParameters equivalent; it is
            // this value, and it is the same one Explorer itself reads.
            object? v = Microsoft.Win32.Registry.GetValue(
                @"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                "EnableTransparency", 1);
            if (v is int i) s.GlassEnabled = i != 0;
        }
        catch { }
        return s;
    }

    private DateTime _lastSave = DateTime.MinValue;

    public void Save()
    {
        try
        {
            Directory.CreateDirectory(Catalog.StateDir);
            string tmp = FilePath + ".tmp";
            File.WriteAllText(tmp, JsonSerializer.Serialize(this, Opts));
            File.Move(tmp, FilePath, overwrite: true);   // atomic: never a half file
            _lastSave = DateTime.UtcNow;
        }
        catch { }
    }

    private System.Threading.Timer? _trailing;

    /// <summary>
    /// Coalesce bursts of writes (a slider drag must not hammer the disk) - but
    /// never DROP one.
    ///
    /// 🔴🔴 IT USED TO THROW THE LAST CHANGE AWAY. A call inside the window
    /// simply returned, on the assumption that another one would follow; the
    /// last press of a drag is exactly the call that has nothing after it, so
    /// the value the user settled on was the one value never written. The clean
    /// exit path covers it (OnClosing saves), which is why this survived - but a
    /// shell that is killed rather than closed, or a machine that loses power,
    /// takes the setting with it. Now the burst is still coalesced and a trailing
    /// write always lands.
    ///
    /// The timer is re-armed on each call, so a hundred presses cost one write
    /// after the last one, not a hundred.
    /// </summary>
    public void SaveThrottled(TimeSpan? window = null)
    {
        var w = window ?? TimeSpan.FromSeconds(2);
        if (DateTime.UtcNow - _lastSave >= w) { Save(); return; }

        _trailing ??= new System.Threading.Timer(_ =>
        {
            // Save() is atomic (temp + move) and swallows its own failures, so a
            // write from the timer thread cannot corrupt the file or throw into
            // a thread nobody is watching.
            try { Save(); } catch { }
        });
        _trailing.Change(w, System.Threading.Timeout.InfiniteTimeSpan);
    }

    public GameProfile? ProfileFor(string key, bool create = true)
    {
        var p = Profiles.FirstOrDefault(x => x.Key == key);
        if (p is not null || !create) return p;
        p = new GameProfile { Key = key };
        Profiles.Add(p);
        return p;
    }
}
