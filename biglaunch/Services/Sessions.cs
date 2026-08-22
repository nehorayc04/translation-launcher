using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Windows.Threading;

namespace BigLaunch.Services;

/// <summary>One live (or suspended) game, tracked from launch to exit.</summary>
public sealed class GameSession
{
    public string Key = "";
    public string Name = "";
    public Process? Proc;
    public DateTime StartedUtc = DateTime.UtcNow;
    public DateTime? SuspendedUtc;
    public long AccumulatedSeconds;

    /// <summary>Where the game lives, so the real process can be found when the
    /// thing we started was only a launcher.</summary>
    public string Dir = "";

    /// <summary>
    /// Set once we have actually SEEN the game's own process.
    ///
    /// 🔴🔴 WITHOUT THIS, EVERY STORE-LAUNCHED GAME "EXITED" TWO SECONDS AFTER IT
    /// STARTED. A Steam, Epic or Ubisoft title is started through the store - we
    /// hand Windows a steam:// URI or run the launcher, and THAT process exits
    /// almost immediately while the game itself starts as a child of the store.
    /// The session watched the wrong process (or none at all, for a URI, where
    /// Process.Start returns null), found it dead on the very next tick, banked
    /// zero playtime and announced the game had closed - while it was loading.
    /// Suspend/resume could not work for those titles either, because there was
    /// nothing left to suspend.
    /// </summary>
    public bool Confirmed;

    public bool Suspended => SuspendedUtc is not null;
    public bool Alive { get { try { return Proc is { HasExited: false }; } catch { return false; } } }

    public TimeSpan Elapsed => TimeSpan.FromSeconds(
        AccumulatedSeconds + (Suspended ? 0 : (DateTime.UtcNow - StartedUtc).TotalSeconds));

    public string ElapsedLabel
    {
        get
        {
            var e = Elapsed;
            return e.TotalHours >= 1 ? $"{(int)e.TotalHours}:{e.Minutes:00}" : $"{e.Minutes}:{e.Seconds:00}";
        }
    }
}

/// <summary>
/// Quick Resume + memory guard.
///
/// The mechanism is the documented NT process-suspension pair — the SAME one
/// this project already uses elsewhere to free a busy inference queue. A
/// suspended game keeps every byte of its state in RAM and resumes instantly;
/// it costs zero CPU while parked, which is the whole point of Quick Resume.
///
/// The honest limits, stated rather than hidden:
///  * A suspended game still HOLDS its memory. That is why the memory guard
///    exists and why eviction is offered instead of parking games forever.
///  * A game with anti-cheat may dislike being frozen. Suspension is manual
///    and per-game — never automatic — precisely so the user stays in control.
/// </summary>
public sealed class SessionCoordinator
{
    [DllImport("ntdll.dll")] private static extern int NtSuspendProcess(IntPtr h);
    [DllImport("ntdll.dll")] private static extern int NtResumeProcess(IntPtr h);

    [StructLayout(LayoutKind.Sequential)]
    private struct MEMORYSTATUSEX
    {
        public uint dwLength, dwMemoryLoad;
        public ulong ullTotalPhys, ullAvailPhys, ullTotalPageFile, ullAvailPageFile,
                     ullTotalVirtual, ullAvailVirtual, ullAvailExtendedVirtual;
    }
    [DllImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MEMORYSTATUSEX s);

    public ObservableCollection<GameSession> Sessions { get; } = new();

    public event Action<GameSession>? Started;
    public event Action<GameSession>? Exited;
    public event Action<GameSession>? StateChanged;
    /// <summary>Raised once per crossing, never every tick.</summary>
    public event Action<int>? MemoryWarning;

    private readonly AppSettings _settings;
    private readonly DispatcherTimer _timer;
    private bool _warned;

    public SessionCoordinator(AppSettings settings)
    {
        _settings = settings;
        _timer = new DispatcherTimer(DispatcherPriority.Background)
        {
            // A game's lifetime is measured in minutes; 2 s is plenty and keeps
            // the shell at effectively zero CPU while a game is in front.
            Interval = TimeSpan.FromSeconds(2)
        };
        _timer.Tick += (_, _) => Tick();
        _timer.Start();
    }

    public GameSession Track(LibraryGame g, Process? p)
    {
        bool live = false;
        try { live = p is { HasExited: false }; } catch { }
        var s = new GameSession
        {
            Key = g.Key,
            Name = g.Name,
            Proc = p,
            Dir = g.InstallDir ?? "",
            Confirmed = live && !string.IsNullOrEmpty(g.InstallDir) && Under(p!, g.InstallDir!),
        };
        Sessions.Add(s);

        var prof = _settings.ProfileFor(g.Key)!;
        prof.LaunchCount++;
        prof.LastPlayed = DateTime.Now;
        _settings.Save();

        Started?.Invoke(s);
        return s;
    }

    public GameSession? For(string key) => Sessions.FirstOrDefault(s => s.Key == key);

    public bool Suspend(GameSession s)
    {
        if (s.Suspended || !s.Alive || s.Proc is null) return false;
        try
        {
            if (NtSuspendProcess(s.Proc.Handle) != 0) return false;
            s.AccumulatedSeconds += (long)(DateTime.UtcNow - s.StartedUtc).TotalSeconds;
            s.SuspendedUtc = DateTime.UtcNow;
            StateChanged?.Invoke(s);
            Sfx.Play(Sound.Sleep);
            return true;
        }
        catch { return false; }
    }

    public bool Resume(GameSession s)
    {
        if (!s.Suspended || !s.Alive || s.Proc is null) return false;
        try
        {
            if (NtResumeProcess(s.Proc.Handle) != 0) return false;
            s.SuspendedUtc = null;
            s.StartedUtc = DateTime.UtcNow;       // restart the running clock
            StateChanged?.Invoke(s);
            Sfx.Play(Sound.Wake);
            try { Interop.Focus.RaiseProcess(s.Proc); } catch { }
            return true;
        }
        catch { return false; }
    }

    /// <summary>
    /// Un-freeze everything on the way out.
    ///
    /// 🔴🔴 A SUSPENDED GAME OUTLIVES THE SHELL THAT FROZE IT. NtSuspendProcess
    /// is not a parent-child relationship — the thread stays frozen after this
    /// process is gone, and nothing left on the machine offers a resume. So
    /// quitting Big Launch with a parked game abandoned it: it held every byte
    /// of its memory, showed a dead window, and only Task Manager could end it.
    ///
    /// The quit confirmation already PROMISES "המשחקים המושהים ישוחררו וימשיכו
    /// לרוץ רגיל" — this is the code that makes that sentence true.
    ///
    /// Best-effort by design: it runs while the window is closing, so a process
    /// that died a moment ago must not throw the shutdown path.
    /// </summary>
    public void ReleaseAll()
    {
        foreach (var s in Sessions.ToList())
        {
            try { if (s.Suspended && s.Alive && s.Proc is not null) NtResumeProcess(s.Proc.Handle); }
            catch { }
        }
    }

    /// <summary>Close a session (politely first, then force) — the eviction path.</summary>
    public bool Close(GameSession s)
    {
        try
        {
            if (s.Proc is null) { Remove(s); return true; }
            if (s.Suspended) NtResumeProcess(s.Proc.Handle);   // a frozen process cannot process WM_CLOSE
            if (!s.Proc.CloseMainWindow())
            {
                s.Proc.Kill(entireProcessTree: true);
            }
            return true;
        }
        catch { return false; }
    }

    public (int percent, double usedGb, double totalGb) Memory()
    {
        var m = new MEMORYSTATUSEX { dwLength = (uint)Marshal.SizeOf<MEMORYSTATUSEX>() };
        if (!GlobalMemoryStatusEx(ref m) || m.ullTotalPhys == 0) return (0, 0, 0);
        double total = m.ullTotalPhys / 1073741824.0;
        double used = (m.ullTotalPhys - m.ullAvailPhys) / 1073741824.0;
        return ((int)m.dwMemoryLoad, used, total);
    }

    /// <summary>Oldest suspended session — the natural eviction candidate.</summary>
    public GameSession? EvictionCandidate() =>
        Sessions.Where(s => s.Suspended).OrderBy(s => s.SuspendedUtc).FirstOrDefault();

    /// <summary>How long a game gets to actually appear before we accept that it
    /// never did. Long enough for a cold Steam start on a slow disk; short enough
    /// that a failed launch does not leave a ghost session all evening.</summary>
    private static readonly TimeSpan AppearWindow = TimeSpan.FromSeconds(90);

    private static bool Under(Process p, string dir)
    {
        try
        {
            string? path = Interop.AppIcons.PathOfProcess((uint)p.Id);
            return path is not null && path.StartsWith(dir, StringComparison.OrdinalIgnoreCase);
        }
        catch { return false; }
    }

    /// <summary>
    /// Find the game's own process under its install folder and adopt it.
    ///
    /// Deliberately only runs while a session is UNCONFIRMED: walking every
    /// process and asking each for its image path is far too expensive to do on
    /// a two-second timer forever, and once the real process is in hand there is
    /// nothing left to look for.
    /// </summary>
    private bool TryAdopt(GameSession s)
    {
        if (string.IsNullOrEmpty(s.Dir)) return false;
        try
        {
            foreach (var p in Process.GetProcesses())
            {
                try
                {
                    if (p.Id <= 4) continue;
                    if (!Under(p, s.Dir)) { p.Dispose(); continue; }
                    s.Proc = p;
                    s.Confirmed = true;
                    return true;
                }
                catch { try { p.Dispose(); } catch { } }
            }
        }
        catch { }
        return false;
    }

    private void Tick()
    {
        foreach (var s in Sessions.ToList())
        {
            if (s.Alive) { s.Confirmed = true; continue; }

            // Not alive - but was it ever? A session we have never confirmed is
            // still waiting for the store to bring the game up, so it gets the
            // appearance window before anything is banked or announced.
            if (!s.Confirmed)
            {
                if (TryAdopt(s)) continue;
                if (DateTime.UtcNow - s.StartedUtc < AppearWindow) continue;
            }
            // Bank the playtime the moment the game really exited.
            if (!s.Suspended) s.AccumulatedSeconds += (long)(DateTime.UtcNow - s.StartedUtc).TotalSeconds;
            var prof = _settings.ProfileFor(s.Key)!;
            prof.PlaySeconds += s.AccumulatedSeconds;
            _settings.Save();
            Remove(s);
            Exited?.Invoke(s);
        }

        if (!_settings.MemoryGuard) return;
        int pct = Memory().percent;
        if (pct >= _settings.MemoryWarnPercent && !_warned)
        {
            _warned = true;
            MemoryWarning?.Invoke(pct);
        }
        // Re-arm with hysteresis so a value hovering at the line cannot spam.
        else if (pct < _settings.MemoryWarnPercent - 6) _warned = false;
    }

    private void Remove(GameSession s)
    {
        Sessions.Remove(s);
        try { s.Proc?.Dispose(); } catch { }
    }
}
