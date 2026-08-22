using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Windows.Threading;

namespace BigLaunch.Services;

public sealed class BlockerRule
{
    public string Id { get; set; } = "";
    public string Category { get; set; } = "";      // redistributables | anticheat | cloudsave | auth | modals | launcher
    public string Title { get; set; } = "";         // case-insensitive substring of the window title
    public string? Class { get; set; }              // optional window-class filter
    public string Action { get; set; } = "surface"; // surface | confirm
    public string Label { get; set; } = "";         // what the user is told, in Hebrew
}

/// <summary>
/// "שומר השקה חכם" — our own implementation of the IDEA.
///
/// A game launch stalls behind a dialog the player cannot see from the couch:
/// a VC++ redistributable, an EasyAntiCheat installer, a cloud-save conflict,
/// an EULA. This watches for those windows during the launch window only, and
/// either SURFACES them (default) or presses their confirm button (opt-in,
/// redistributables only).
///
/// 🔴 Deliberately conservative, because it touches other processes' windows:
///  * OFF by default (AppSettings.LaunchWatcher).
///  * Runs ONLY for maxMonitoringTime after a launch WE started — never idle.
///  * "confirm" only ever clicks a button whose own text is in a fixed safe
///    list, and only for rules we marked auto-confirmable.
///  * The pattern list is OUR json, written on first run and user-editable.
/// </summary>
public sealed class LaunchWatcher : IDisposable
{
    private const uint EVENT_SYSTEM_FOREGROUND = 0x0003;
    private const uint EVENT_OBJECT_SHOW = 0x8002;
    private const uint WINEVENT_OUTOFCONTEXT = 0x0000;
    private const uint WINEVENT_SKIPOWNPROCESS = 0x0002;

    private delegate void WinEventProc(IntPtr hook, uint ev, IntPtr hwnd,
                                       int idObject, int idChild, uint thread, uint time);

    [DllImport("user32.dll")]
    private static extern IntPtr SetWinEventHook(uint min, uint max, IntPtr mod,
        WinEventProc proc, uint pid, uint thread, uint flags);
    [DllImport("user32.dll")] private static extern bool UnhookWinEvent(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextW(IntPtr h, StringBuilder s, int max);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassNameW(IntPtr h, StringBuilder s, int max);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] private static extern bool EnumWindows(EnumProc cb, IntPtr p);
    [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr p);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr SendMessageW(IntPtr h, uint msg, IntPtr w, IntPtr l);
    private delegate bool EnumProc(IntPtr h, IntPtr p);

    private const uint BM_CLICK = 0x00F5;
    private const int SW_RESTORE = 9;

    /// <summary>Only these button captions are ever pressed automatically.</summary>
    private static readonly string[] SafeButtons =
    {
        "ok", "אישור", "install", "התקן", "next", "הבא", "accept", "אני מסכים",
        "i agree", "agree", "continue", "המשך", "yes", "כן", "finish", "סיום",
    };

    private readonly AppSettings _settings;
    private readonly DispatcherTimer _sweep;
    private readonly WinEventProc _proc;      // MUST stay referenced or the CLR collects it
    private IntPtr _hook;
    private DateTime _until = DateTime.MinValue;
    private readonly HashSet<IntPtr> _handled = new();

    public List<BlockerRule> Rules { get; private set; } = new();

    /// <summary>(rule, what happened) — surfaced to the user as a toast.</summary>
    public event Action<BlockerRule, string>? Detected;

    public LaunchWatcher(AppSettings settings)
    {
        _settings = settings;
        Rules = LoadRules();
        _proc = OnWinEvent;

        // Two independent signal sources, exactly because neither is complete:
        // the hook catches a dialog the instant it is shown, while the sweep
        // catches one that was already up before we armed.
        _sweep = new DispatcherTimer(DispatcherPriority.Background)
        {
            Interval = TimeSpan.FromMilliseconds(1000)
        };
        _sweep.Tick += (_, _) => Sweep();
    }

    /// <summary>Arm for one launch. 90 s, then it disarms itself.</summary>
    public void Arm(TimeSpan? window = null)
    {
        if (!_settings.LaunchWatcher) return;
        _until = DateTime.UtcNow + (window ?? TimeSpan.FromSeconds(90));
        _handled.Clear();
        if (_hook == IntPtr.Zero)
        {
            try
            {
                _hook = SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_SHOW, IntPtr.Zero,
                                        _proc, 0, 0, WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS);
            }
            catch { }
        }
        _sweep.Start();
    }

    public void Disarm()
    {
        _until = DateTime.MinValue;
        _sweep.Stop();
        if (_hook != IntPtr.Zero) { try { UnhookWinEvent(_hook); } catch { } _hook = IntPtr.Zero; }
    }

    private bool Armed => DateTime.UtcNow < _until;

    private void OnWinEvent(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint th, uint t)
    {
        if (!Armed || idObject != 0 || hwnd == IntPtr.Zero) return;
        try { Inspect(hwnd); } catch { }
    }

    private void Sweep()
    {
        if (!Armed) { Disarm(); return; }
        try { EnumWindows((h, _) => { Inspect(h); return true; }, IntPtr.Zero); } catch { }
    }

    private void Inspect(IntPtr hwnd)
    {
        if (_handled.Contains(hwnd) || !IsWindowVisible(hwnd)) return;

        string title = Text(hwnd, GetWindowTextW);
        if (title.Length == 0) return;
        string cls = Text(hwnd, GetClassNameW);

        var rule = Rules.FirstOrDefault(r =>
            r.Title.Length > 0 &&
            title.Contains(r.Title, StringComparison.OrdinalIgnoreCase) &&
            (string.IsNullOrEmpty(r.Class) || cls.Contains(r.Class, StringComparison.OrdinalIgnoreCase)));
        if (rule is null) return;

        _handled.Add(hwnd);

        if (rule.Action == "confirm" && TryConfirm(hwnd))
        {
            Detected?.Invoke(rule, "אושר אוטומטית");
            return;
        }

        // Default: put it where the player can see it and say what it is.
        try { ShowWindow(hwnd, SW_RESTORE); SetForegroundWindow(hwnd); } catch { }
        Detected?.Invoke(rule, "נדרשת פעולה");
    }

    private static bool TryConfirm(IntPtr dialog)
    {
        IntPtr target = IntPtr.Zero;
        try
        {
            EnumChildWindows(dialog, (h, _) =>
            {
                if (!IsWindowVisible(h)) return true;
                if (!Text(h, GetClassNameW).Contains("button", StringComparison.OrdinalIgnoreCase)) return true;
                string cap = Text(h, GetWindowTextW).Replace("&", "").Trim().ToLowerInvariant();
                if (cap.Length > 0 && SafeButtons.Any(b => cap == b))
                {
                    target = h;
                    return false;      // stop at the first safe button
                }
                return true;
            }, IntPtr.Zero);

            if (target == IntPtr.Zero) return false;
            SendMessageW(target, BM_CLICK, IntPtr.Zero, IntPtr.Zero);
            return true;
        }
        catch { return false; }
    }

    private static string Text(IntPtr h, Func<IntPtr, StringBuilder, int, int> fn)
    {
        var sb = new StringBuilder(512);
        int n = fn(h, sb, sb.Capacity);
        return n > 0 ? sb.ToString() : "";
    }

    // ------------------------------------------------------------- rules

    private static string RulesPath => Path.Combine(Catalog.StateDir, "biglaunch_launch_rules.json");

    /// <summary>
    /// Our own pattern list, seeded on first run and then owned by the user.
    /// Every entry is a window TITLE anyone can read off their own screen.
    /// </summary>
    public static List<BlockerRule> Defaults() => new()
    {
        new() { Id="dx",       Category="redistributables", Title="DirectX",                Action="confirm", Label="התקנת DirectX" },
        new() { Id="vcredist", Category="redistributables", Title="Visual C++",             Action="confirm", Label="התקנת Visual C++" },
        new() { Id="dotnet",   Category="redistributables", Title=".NET Framework",         Action="confirm", Label="התקנת ‎.NET" },
        new() { Id="physx",    Category="redistributables", Title="PhysX",                  Action="confirm", Label="התקנת PhysX" },
        new() { Id="openal",   Category="redistributables", Title="OpenAL",                 Action="confirm", Label="התקנת OpenAL" },
        new() { Id="eac",      Category="anticheat",        Title="EasyAntiCheat",          Action="surface", Label="התקנת EasyAntiCheat" },
        new() { Id="be",       Category="anticheat",        Title="BattlEye",               Action="surface", Label="התקנת BattlEye" },
        new() { Id="cloud",    Category="cloudsave",        Title="Cloud Sync Conflict",    Action="surface", Label="התנגשות שמירה בענן" },
        new() { Id="steamauth",Category="auth",             Title="Steam Guard",            Action="surface", Label="אימות Steam" },
        new() { Id="eula",     Category="modals",           Title="License Agreement",      Action="surface", Label="הסכם רישיון" },
        new() { Id="eula2",    Category="modals",           Title="End User License",       Action="surface", Label="הסכם רישיון" },
        new() { Id="age",      Category="modals",           Title="Age Verification",       Action="surface", Label="אימות גיל" },
        new() { Id="rockstar", Category="launcher",         Title="Rockstar Games Launcher",Action="surface", Label="חוסם Rockstar" },
        new() { Id="social",   Category="launcher",         Title="Social Club",            Action="surface", Label="חוסם Social Club" },
        new() { Id="ubi",      Category="launcher",         Title="Ubisoft Connect",        Action="surface", Label="חוסם Ubisoft" },
        new() { Id="ea",       Category="launcher",         Title="EA app",                 Action="surface", Label="חוסם EA" },
        new() { Id="origin",   Category="launcher",         Title="Origin",                 Action="surface", Label="חוסם Origin" },
        new() { Id="epicl",    Category="launcher",         Title="Epic Games Launcher",    Action="surface", Label="חוסם Epic" },
    };

    private static List<BlockerRule> LoadRules()
    {
        try
        {
            if (File.Exists(RulesPath))
            {
                var r = JsonSerializer.Deserialize<List<BlockerRule>>(File.ReadAllText(RulesPath));
                if (r is { Count: > 0 }) return r;
            }
        }
        catch { }

        var d = Defaults();
        try
        {
            Directory.CreateDirectory(Catalog.StateDir);
            File.WriteAllText(RulesPath, JsonSerializer.Serialize(d, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            }));
        }
        catch { }
        return d;
    }

    public void Dispose() => Disarm();
}
