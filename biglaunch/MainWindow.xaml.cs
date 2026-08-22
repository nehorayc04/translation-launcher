using System;
using System.Collections.Generic;
using System.Windows.Data;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using IOPath = System.IO.Path;   // System.Windows.Shapes.Path also exists here
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using System.Windows.Threading;
using BigLaunch.Interop;
using BigLaunch.Services;

namespace BigLaunch;

public partial class MainWindow : Window
{
    // ---- state ----------------------------------------------------------
    private AppSettings _settings = new();
    private List<GameEntry> _hub = new();
    private List<LibraryGame> _all = new();

    /// <summary>
    /// 🔴 THE SCAN RESULT, UNFILTERED. SortLibrary used to write its own filtered
    /// output back over _all, so hiding a game DELETED it from memory and no
    /// unhide could ever bring it back without a full rescan. Sorting is a VIEW
    /// of the scan, so it must always derive from this.
    /// </summary>
    private List<LibraryGame> _scanned = new();
    private LibraryGame? _selected;

    private SessionCoordinator? _sessions;
    private LaunchWatcher? _watcher;
    private DiscordRpc? _discord;
    private readonly Telemetry _tel = new();
    private Gamepad? _pad;

    private string _tab = "home";
    // Restored in the constructor from settings - see LastFilter.
    private string _filter = "all";
    private CancellationTokenSource? _sizeCts;

    // What the desktop launcher answered about the four things only it can know
    // (see ShellBridge). Cached so the settings page can be built SYNCHRONOUSLY
    // - it is rebuilt on every focus move, and a page that awaited four
    // subprocesses on each rebuild would be unusable.
    private ShellBridge.Account? _account;
    private ShellBridge.PluginList? _plugins;
    private ShellBridge.BetaPrefs? _beta;
    private ShellBridge.UpdateInfo? _update;
    private bool _shellLoading, _shellLoaded;

    // The focus tree: what the thumbstick can reach on the TOP-most layer.
    private readonly List<FrameworkElement> _nav = new();
    /// <summary>Index in _nav where the view's own items begin (chrome first).</summary>
    private int _navViewStart;
    // Index into _nav of the action this view's current state makes primary.
    // -1 = none nominated, use content order.
    private int _navPreferred = -1;

    /// <summary>
    /// Start a fresh navigation map. 🔴 EVERY screen rebuild goes through here
    /// rather than calling _nav.Clear() directly — a preferred-focus index that
    /// outlived its own screen would point at whatever control happened to land
    /// at that position on the NEXT one, which is a focus landing somewhere
    /// arbitrary and no compiler error anywhere. One place to clear both is the
    /// only version of this that a future screen cannot forget.
    /// </summary>
    private void ResetNav()
    {
        _nav.Clear();
        _navPreferred = -1;
    }

    /// <summary>
    /// Which power-menu row to re-focus when B steps back out of a
    /// confirmation. Coming back from "are you sure?" onto a DIFFERENT row than
    /// the one you were on is a small thing that reads as the console losing
    /// your place - and on a 10ft UI, losing your place is the whole cost of a
    /// wrong click. Recorded at the moment the confirmation is raised, so it
    /// needs no per-row plumbing and is right for every row automatically.
    /// </summary>
    private int _powerFocus;
    private string _layer = "view";        // view | blade | quick | dialog | onboard

    // Winhanced's own strip order is What's New | Library | Store | Friends |
    // Settings, so "what changed" sits immediately after the landing screen.
    // 🔴 "settings" IS DELIBERATELY NOT IN THIS ARRAY. It is reachable from the
    // gear in the header, which is on screen on every tab - so a pill for it in
    // the strip is the same door twice, and the second one costs a stop on
    // every LB/RB sweep through the tabs.
    private static readonly string[] Tabs = { "home", "news", "library", "downloads", "perf", "plugins", "stream" };
    private static readonly Dictionary<string, string> TabNames = new()
    {
        ["home"] = "בית", ["news"] = "מה חדש", ["library"] = "ספרייה", ["downloads"] = "הורדות",
        ["perf"] = "ביצועים", ["plugins"] = "תוספים", ["stream"] = "סטרימינג",
        ["settings"] = "הגדרות",
    };

    // Segoe Fluent / MDL2 — Winhanced's own declared icon font, so a glyph is
    // never an emoji (which would render as a colour bitmap at a random size).
    private const string GlyphPlay = "", GlyphPause = "", GlyphBack = "",
                         GlyphRefresh = "", GlyphDelete = "", GlyphMonitor = "",
                         GlyphPower = "", GlyphCamera = "", GlyphSound = "",
                         GlyphFolder = "", GlyphInfo = "", GlyphWarn = "",
                         GlyphDownload = "", GlyphChip = "", GlyphSettings = "",
                         GlyphGame = "", GlyphSleep = "\uE708", GlyphGrid = "\uE71D",
        // Hibernate gets the SAVE glyph, not a second moon: the row's own
        // subtitle says it saves the state to disk, and two identical moons
        // beside two different actions is exactly the kind of detail that
        // makes a menu feel machine-generated.
        GlyphHibernate = "\uE74E", GlyphStream = "", GlyphCheck = "",
                         // Globe — the Hebrew-translations destination.
                         GlyphGlobe = "\uE774",
                         // Magnifier - the search overlay (X on every screen).
                         GlyphSearch = "\uE721",
                         // Speaker with a slash - the muted state of GlyphSound.
                         GlyphMute = "",
                         // Library / collections. E8F1 is MDL2 "Library" - a stack of
                         // items, which is what a collection is; E710 is the plus.
                         GlyphCollection = "\uE8F1", GlyphAdd = "\uE710",
                         GlyphSort = "\uE8CB", GlyphHide = "\uED1A", GlyphShow = "\uE7B3",
                         GlyphSync = "\uE895", GlyphNews = "\uE789",
                         // E91B is MDL2 "Picture" - the artwork slots.
                         GlyphImage = "\uE91B",
                         // E77B is MDL2 "Contact" - the signed-in account.
                         GlyphUser = "\uE77B",
                         // The header's live-connection chips: WiFi bars, the RJ45
                         // socket for a wired link, and the Bluetooth rune.
                         GlyphWifi = "\uE701", GlyphEthernet = "\uE839",
                         GlyphBluetooth = "\uE702",
                         // Closing a GAME is the \u2715 of a window, never the \u23FB of a
                         // machine. In a shell that can also shut the PC down,
                         // those two actions must not share a glyph.
                         GlyphStop = "\uE711";

    public MainWindow()
    {
        InitializeComponent();
        // The opener is declared VISIBLE in the XAML so it covers frame one. If
        // there is no film to play we have to take it back down here, before
        // anything is presented - anywhere later is a black flash. Settings are
        // read a second time for this (OnLoaded loads them properly); it is one
        // small JSON file, and paying for it buys a clean first frame. Any
        // failure falls through to "no opener", never to a stuck black screen.
        bool willPlay;
        try { willPlay = AppSettings.Load().IntroEnabled && IntroPath() is not null; }
        catch { willPlay = false; }
        if (!willPlay) IntroHost.Visibility = Visibility.Collapsed;
    }

    // =====================================================================
    //  lifecycle
    // =====================================================================

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        // A console shell whose first frame is windowed is simply wrong. XAML's
        // Maximized normally wins, but a session with no resolvable work area
        // comes up at the restore size — re-asserting is a no-op when it didn't.
        if (WindowState != WindowState.Maximized) WindowState = WindowState.Maximized;

        _settings = AppSettings.Load();

        // Restore the filter, but only if it still names something real - a
        // collection deleted on the last run would come back as a library that
        // is permanently empty for no visible reason.
        if (_settings.LastFilter is { Length: > 0 } lf
            && (!lf.StartsWith("col:") || _settings.Collections.Any(c => c.Name == lf[4..])))
            _filter = lf;

        // 🔴 THE FILM STARTS FIRST, BEFORE EVERY OTHER PIECE OF STARTUP WORK.
        // This method used to reach TryStartIntro only after applying the acrylic
        // backdrop, synthesising all eleven audio cues sample by sample, building
        // the bloom and probing the pad hardware - several seconds of work with
        // the window already on screen. That whole stretch was the "empty blurred
        // glass before the video": not a rendering fault, just the opener being
        // last in a queue it should have been at the head of. Everything below is
        // exactly the kind of work that is SUPPOSED to happen behind the film.
        bool intro = TryStartIntro();

        // 🔴🔴 THE ACRYLIC IS APPLIED AFTER THE FIRST FRAME, NOT BEFORE IT.
        //
        // Asking DWM for a backdrop makes the WPF composition target TRANSPARENT
        // (see Backdrop.Apply) - and between that moment and the first frame this
        // window actually paints, the thing showing through is the blurred
        // DESKTOP. That is the pale, blurry screen that kept appearing ahead of
        // the opening film: not a splash, not a loading state, just this window
        // being see-through before it had drawn anything. Deferring the request
        // to ContextIdle - after layout and the first render pass - means the
        // shell is already opaque on screen when the glass arrives behind it.
        Dispatcher.BeginInvoke(DispatcherPriority.ContextIdle, () =>
            Backdrop.Apply(this, _settings.GlassEnabled ? Backdrop.BACKDROP_ACRYLIC : Backdrop.BACKDROP_NONE));

        // 🔴 FROSTING IS HOOKED TO VISIBILITY, NOT TO THE THIRTEEN CALL SITES.
        // Every dialog, picker, confirmation and system panel raises the same two
        // hosts; wiring the blur at each place that opens one is thirteen chances
        // to forget, and the first one forgotten is a panel that reads as glass
        // in one flow and as a flat card in another. The host's own visibility is
        // the single fact that means "something is floating over the shell".
        // 🔴 A THRESHOLD, NOT ANY MouseMove. WPF raises MouseMove for a pointer
        // that has not moved at all when the visual under it changes - a
        // re-render, a scroll, a tile growing under focus - so an unconditional
        // handler would put the cursor back on screen every time the pad moved
        // the selection, which is precisely what it is supposed to hide it for.
        PreviewMouseMove += (_, ev) =>
        {
            if (Mouse.OverrideCursor != Cursors.None) return;
            var now = ev.GetPosition(this);
            if (Math.Abs(now.X - _cursorAt.X) + Math.Abs(now.Y - _cursorAt.Y) > 3) ShowPointer();
        };

        DialogHost.IsVisibleChanged += (_, _) => UpdateFrost();
        QuickMenu.IsVisibleChanged  += (_, _) => UpdateFrost();
        SearchHost.IsVisibleChanged += (_, _) => UpdateFrost();
        Blade.IsVisibleChanged      += (_, _) => UpdateFrost();

        Sfx.Configure(_settings.SoundEnabled, _settings.SoundVolume);
        ApplyUiScale();
        BuildBloom();

        _sessions = new SessionCoordinator(_settings);
        _sessions.Exited += s => Dispatcher.Invoke(() =>
        {
            RestoreShell();
            ShowToast($"{s.Name} - נסגר אחרי {s.ElapsedLabel}");
            _ = UpdatePresenceAsync();
            RepaintIfShowing();
        });
        _sessions.StateChanged += _ => Dispatcher.Invoke(RepaintIfShowing);
        _sessions.MemoryWarning += pct => Dispatcher.Invoke(() => OnMemoryWarning(pct));

        _watcher = new LaunchWatcher(_settings);
        _watcher.Detected += (r, what) => Dispatcher.Invoke(() =>
        {
            Sfx.Play(Sound.Warning);
            ShowToast($"{GlyphWarn}  {r.Label} - {what}");
        });

        // clock + telemetry on one slow timer; a 10ft shell must be idle-cheap.
        var tick = new DispatcherTimer(DispatcherPriority.Background) { Interval = TimeSpan.FromSeconds(2) };
        tick.Tick += (_, _) => OnTick();
        tick.Start();
        OnTick();

        _pad = new Gamepad();
        _pad.Pressed += OnPad;

        // Remote cover art lands asynchronously; coalesce the arrivals into ONE
        // re-render instead of rebuilding the grid once per downloaded image.
        _artRefresh = new DispatcherTimer(DispatcherPriority.Background) { Interval = TimeSpan.FromMilliseconds(450) };
        _artRefresh.Tick += (_, _) =>
        {
            _artRefresh!.Stop();
            // A BACKGROUND REPAINT MUST NEVER PULL THE SCREEN OUT FROM UNDER A
            // MODAL. Art keeps landing for the first seconds after launch and
            // after every library refresh - which is exactly when a first-run
            // user is still reading the wizard, or when someone is typing in
            // the search box. RenderTab focuses its first control, so a repaint
            // behind a card moved focus into a view the user could not see and
            // the next A press hit something invisible. Dropping it costs
            // nothing: every route back to the view re-renders anyway, and by
            // then the art is already on disk.
            if (_layer != "view") return;

            // 🔴 AND IT MUST NOT MOVE THE RING EITHER. Art keeps landing for
            // seconds after a library refresh, and each batch re-rendered the
            // page and focused its FIRST control - so someone browsing the
            // shelf was thrown back to the first cover every half second by
            // pictures arriving behind them. The session repaint already solved
            // this exact problem (RepaintIfShowing); the art tick simply never
            // used the same care.
            int keep = Keyboard.FocusedElement is FrameworkElement fe ? _nav.IndexOf(fe) : -1;
            RenderTab();
            if (keep >= 0) _navPreferred = keep;
        };
        ArtCache.Arrived += _ => Dispatcher.BeginInvoke(() => { _artRefresh?.Stop(); _artRefresh?.Start(); });

        // 🔴 A DIMMED BACKDROP IS A DISMISS TARGET, NOT DECORATION. Every one of
        // these layers darkens the screen behind a floating card, and the dark
        // area reads as "the thing underneath, pushed back" - so clicking it is
        // the obvious way out and doing nothing there feels stuck. The guard is
        // the whole trick: the click only counts when the backdrop ITSELF was
        // hit, so a click that lands anywhere inside the card is left alone.
        // Back() rather than each Close*(), because Back() already owns what
        // each layer dismisses TO (a dialog raised from a game card has to
        // return to that card, not to the page hidden behind it).
        foreach (var host in new Panel[] { DialogHost, SearchHost, QuickMenu, Blade })
        {
            var h = host;
            h.MouseLeftButtonDown += (_, e) =>
            {
                if (!ReferenceEquals(e.OriginalSource, h)) return;
                e.Handled = true;
                Back();
            };
        }

        // Tab must not be able to leave an open overlay. These hosts are
        // SIBLINGS of the page in the visual tree, so WPF's default tab order
        // walks straight out of a modal and into the screen behind it.
        foreach (var host in new DependencyObject[] { DialogHost, SearchHost, QuickMenu, Blade, OnboardHost })
            KeyboardNavigation.SetTabNavigation(host, KeyboardNavigationMode.Cycle);

        SystemEvents_Register();

        // The opener goes up BEFORE the scan, which is the whole point: the load
        // happens behind it. It returns false when there is no video (or the
        // machine cannot decode one), and then the old startup cue plays instead.
        // Prompts are drawn for whatever is plugged in BEFORE the first screen —
        // somebody who opens a 10ft shell with a pad in hand must not be told to
        // press Enter. The first keystroke flips it back to keys.
        _padHardware = PadIdentity.Detect();
        _padKind = _padHardware ?? PadKind.Keyboard;

        if (!_settings.OnboardingDone) { ShowOnboarding(); }
        else if (!intro) { Sfx.Play(Sound.Startup); }

        // The first frame goes up BEFORE the sweep of every store on every disk.
        // The screen it draws is the skeleton above; the real one replaces it
        // when the scan lands, in the same layout, so nothing moves.
        if (_settings.OnboardingDone) { SetTab("home"); }
        await ReloadLibraryAsync();
        if (_settings.OnboardingDone) { SetTab("home"); }

        _ = ConnectDiscordAsync();

        // Can this launcher build be driven headlessly? Answered off the UI
        // thread, cached on disk per launcher build, and re-rendered once so a
        // blade opened afterwards offers the real install button.
        _ = Task.Run(async () =>
        {
            await ModBridge.ProbeAsync();
            Dispatcher.Invoke(() => { if (_layer == "view") RenderTab(); });
            // Then the account/plugins/beta/update read. Started HERE rather
            // than when Settings opens, because the user walks through home and
            // library first - so by the time they reach the page the answers are
            // already on hand and it never shows a row that says "טוען".
            await LoadShellAsync();
        });
    }

    private void OnClosing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        // Freed FIRST: a suspended game stays frozen after this process is gone,
        // and nothing else on the machine can wake it. The quit confirmation
        // promises they are released - this is where that becomes true.
        try { _sessions?.ReleaseAll(); } catch { }
        try { _pad?.Dispose(); _watcher?.Dispose(); _discord?.Dispose(); } catch { }
        _settings.Save();
    }

    private void SystemEvents_Register()
    {
        // Sleep/wake are real events in a console shell: the report lists both
        // cues, and a shell that wakes silently feels broken.
        Microsoft.Win32.SystemEvents.PowerModeChanged += (_, ev) =>
        {
            try
            {
                if (ev.Mode == Microsoft.Win32.PowerModes.Suspend)
                {
                    Sfx.Play(Sound.Sleep);

                    // A FROZEN PROCESS MUST NOT BE CARRIED INTO A SLEEP. The
                    // shell suspends a game to hand its CPU to another one, and
                    // the ONLY thing on the machine that can un-suspend it is
                    // this process. Sleep is where that stops being safe: the
                    // resume may kill us (a driver reset, hibernation restoring
                    // a stale image, the user shutting down from the lock
                    // screen), and then the game is frozen with no owner - it
                    // survives, invisible, until it is killed from Task Manager.
                    // Releasing costs nothing when nothing is suspended.
                    try { _sessions?.ReleaseAll(); } catch { }
                    _settings.Save();
                }
                else if (ev.Mode == Microsoft.Win32.PowerModes.Resume)
                {
                    Sfx.Play(Sound.Wake);

                    // Everything measured against the old power state is now a
                    // guess: the counters are stale (see ResetCounters), the pad
                    // may have been re-enumerated on a different slot, and any
                    // game that did not survive the sleep is still listed.
                    _tel?.ResetCounters();
                    Dispatcher.BeginInvoke(() =>
                    {
                        _padHardware = PadIdentity.Detect();
                        if (_padHardware is { } pk) _padKind = pk;
                        ShowToast("חזרה משינה");
                        RepaintIfShowing();
                    });
                }
            }
            catch { }
        };

        // LOG OFF AND SHUT DOWN DO NOT CLOSE A WINDOW, THEY END A SESSION.
        // OnClosing is where the release and the settings write live, and
        // neither runs when Windows ends the session under us - so a shutdown
        // with a suspended game left it suspended into the next boot's memory
        // image, and every preference changed since the last throttled save was
        // simply lost. This is the same cleanup, on the event that actually
        // fires.
        Microsoft.Win32.SystemEvents.SessionEnding += (_, _) =>
        {
            try { _sessions?.ReleaseAll(); } catch { }
            try { _settings.Save(); } catch { }
        };
    }

    private void OnTick()
    {
        Clock.Text = DateTime.Now.ToString("HH:mm", CultureInfo.InvariantCulture);

        // Cheap: it returns on the first line unless a retry is actually due.
        _ = ConnectDiscordAsync();

        // The pill is no longer "the telemetry chip" - it is the system row, so
        // it stays even when the readouts are turned off; only the numbers go.
        StatPill.Visibility = Visibility.Visible;

        BuildPillChips();

        // 🔴🔴 THE CONTROLLER PAGE HAS TO NOTICE A PAD ARRIVING. Settings is a
        // one-shot render, so "לא זוהה שלט" was written at the moment the screen
        // was built and then never revisited — plug a controller in while
        // looking at that row and it kept saying no controller was found, on a
        // shell that was at that very moment being navigated with it. The row
        // was not wrong when it was drawn; it was never asked again.
        //
        // Gamepad.Connected is maintained by the input poll, so this costs one
        // bool read per second rather than a re-probe, and it re-renders ONLY on
        // a transition and only at page entry — a re-render under a moved focus
        // ring would throw the user's place away to fix a label.
        //
        // ⚠ The poll is no longer a flat 16ms: an EMPTY slot is swept about twice
        // a second (querying one costs a device round-trip - see Gamepad.ScanDue),
        // and only a slot that answered is read at the full rate. So "a pad was
        // just plugged in" can take up to half a second to show up here, which is
        // below the threshold at which anyone reaches for the row to check.
        bool padNow = _pad?.Connected == true;
        if (padNow != _padWasConnected)
        {
            _padWasConnected = padNow;
            if (padNow) _padHardware = null;              // re-identify on the next probe
            if (_layer == "view" && _tab == "settings" && AtPageEntry()) RenderTab();
        }

        StatRow.Children.Clear();
        // 🔴 THE DIVIDER BELONGS TO THE THING IT DIVIDES. Left standing with the
        // readouts turned off it becomes a hairline hanging off the clock with
        // nothing on the other side of it — chrome that describes a boundary
        // that no longer exists.
        if (!_settings.ShowTelemetry)
        {
            StatRow.Visibility = Visibility.Collapsed;
            ClockRule.Visibility = Visibility.Collapsed;
            return;
        }
        StatRow.Visibility = Visibility.Visible;
        ClockRule.Visibility = Visibility.Visible;

        _tel.Sample();
        AddStat("CPU", _tel.CpuPercent);
        AddStat("RAM", _tel.RamPercent);
        if (_tel.GpuKnown) AddStat("GPU", _tel.GpuPercent);
        var b = Telemetry.Battery();
        if (b is { } bat) AddStat("סוללה", bat, invert: true);
    }

    /// <summary>
    /// The GlassPillIndicator's chip row. Winhanced shows a chip only when it
    /// has something to say - a running game, an active download, a battery -
    /// so the pill stays narrow on a desktop and grows on a handheld. Same rule
    /// here: nothing decorative, every chip is a live fact.
    ///
    /// These are STATUS, not navigation: they are deliberately not registered
    /// with Nav(), so a thumbstick never has to walk through them to reach the
    /// content. Power stays reachable at Y -> Power Options.
    /// </summary>
    private void BuildPillChips()
    {
        PillChips.Children.Clear();

        // A game that is running (or parked in Quick Resume) is the single most
        // useful thing this row can surface - Winhanced gives it the first slot
        // and labels it "Return to Game".
        var live = _sessions?.Sessions.FirstOrDefault();
        if (live is not null)
            PillChips.Children.Add(Chip(live.Suspended ? GlyphPause : GlyphPlay,
                                        live.Suspended ? "מושהה" : "פועל", accent: true));

        if (Telemetry.Battery() is { } pct)
            PillChips.Children.Add(Chip(GlyphPower, $"{pct:0}%", warn: pct <= 20));

        // ---- the three system panels ---------------------------------------
        //
        // 🔴🔴 THESE OPEN A PANEL INSIDE THE SHELL. They were passive readouts,
        // which is exactly backwards for the situation they describe: a pad that
        // will not pair and a download that will not start are things you need to
        // ACT on, and the person seeing them is on a couch holding a controller.
        // A readout that names the problem and cannot fix it is the most
        // frustrating control on the screen. Winhanced puts a real panel behind
        // each of these icons for the same reason.
        //
        // ⚠ The state they used to carry is preserved, not traded away: the mute
        // glyph, the offline warning and the wired/wireless distinction all still
        // read at a glance - see ChipButton(label:, warn:).

        // 🔴 "מושתק" MEANS THE SYSTEM, NOT OUR CLICK SOUNDS. The shell-sound
        // preference is something the user JUST set and can see in the quick
        // menu; a muted SYSTEM is the surprise that explains why a game has no
        // sound. Now it is also the way to un-mute it.
        // 🔴 THE STATE IS THE GLYPH, NOT A WORD BESIDE IT. The chip used to spell
        // out "מושתק" next to a crossed speaker - the same fact twice, in a row
        // whose whole job is to be readable at a glance from across a room. The
        // crossed speaker in warning colour already says it.
        bool muted = Interop.Volume.Muted();
        PillChips.Children.Add(ChipButton(muted ? GlyphMute : GlyphSound,
            "עוצמת שמע", () => OpenVolumePanel(), warn: muted));

        // Bluetooth whenever a radio EXISTS - not only when it is switched on.
        // 🔴 THE OLD "only when on" RULE HID THE FIX FROM THE PERSON WHO NEEDED
        // IT: a pad that will not connect because the radio is off showed NO
        // icon at all, so the one screen that could explain it was unreachable.
        // A machine with no Bluetooth hardware still shows nothing, which is
        // correct - there is nothing to say.
        if (Interop.BluetoothDevices.RadioPresent())
        {
            bool btOn = Interop.SystemStatus.BluetoothOn();
            PillChips.Children.Add(ChipButton(GlyphBluetooth, "בלוטות׳",
                () => OpenBluetoothPanel(), warn: !btOn));
        }

        // 🔴 THE NETWORK CHIP IS LOUDEST WHEN THERE IS NO NETWORK. Offline is the
        // one state that silently explains a failed download, a blank store page
        // and a translation that will not fetch - so it keeps the word AND the
        // red, while a healthy link stays a quiet glyph.
        switch (Interop.SystemStatus.Network())
        {
            case Interop.NetLink.Offline:
                PillChips.Children.Add(ChipButton(GlyphWifi, "רשת",
                    () => OpenNetworkPanel(), label: "אין רשת", warn: true)); break;
            case Interop.NetLink.Wired:
                PillChips.Children.Add(ChipButton(GlyphEthernet, "רשת", () => OpenNetworkPanel())); break;
            default:
                PillChips.Children.Add(ChipButton(GlyphWifi, "רשת", () => OpenNetworkPanel())); break;
        }

        // 🔴 A MOUSE COULD NOT REACH SEARCH AT ALL - it lived only on Y/X. Winhanced
        // puts a magnifier FIRST in this same header row, and a shell that hides
        // its only way to find a game behind a button legend fails anyone who
        // walks up with a mouse. These are deliberately NOT in Nav(): a
        // thumbstick must never have to walk through the chrome to reach content,
        // and a pad already has Y for search and the quick menu for power.
        PillChips.Children.Add(ChipButton(GlyphSearch, "חיפוש משחק (" + GlyphFor(LiveToken("Y")) + ")", OpenSearch));

        // 🔴 A GEAR, NOT THE WORD. Settings was reachable only as a tab label in
        // the nav strip and on ☰ — fine for a pad, invisible to someone who
        // walked up with a mouse and is looking for the icon every other shell
        // puts in exactly this corner. It sits between search and power on
        // purpose: those three are the shell's own controls, and the gear is the
        // one you reach for most often of the three, so it gets the middle slot
        // where neither neighbour's muscle memory can steal it.
        PillChips.Children.Add(ChipButton(GlyphSettings, "הגדרות", () => SetTab("settings")));

        // Always last: the power entry, so "how do I turn this off" has a fixed
        // home in the chrome instead of living only three levels into a menu.
        //
        // ⚠ ORDER IS MIRRORED. First child = visual RIGHT in this RTL row, so
        // the requested screen order "power · settings · search" is written here
        // back to front. Adding a chip at the end moves it to the far LEFT.
        PillChips.Children.Add(ChipButton(GlyphPower, "אפשרויות הפעלה",
            () => { _powerFocus = 0; OpenPower(); }));
    }

    /// <summary>
    /// A header chip you can actually click - same glyph, real hit target.
    ///
    /// 🔴 SIZED FOR A COUCH, NOT FOR A TITLE BAR. These started at the same 14px
    /// as the passive status glyphs beside them, which made the three things you
    /// can actually PRESS the smallest targets on the screen - the exact inverse
    /// of what a 10ft shell wants. 18px of glyph inside a 38px box clears the
    /// 44px-ish target guidance once the pill's own padding is counted, and it
    /// is what separates them at a glance from the readouts they used to share a
    /// capsule with.
    /// </summary>
    /// <summary>
    /// An action chip in the header. <paramref name="label"/> and
    /// <paramref name="warn"/> exist so a chip that OPENS something can still
    /// carry the state it used to show as a passive readout — "אין רשת" has to
    /// stay loud after the icon became a button, or making it useful would have
    /// cost the warning that made it worth looking at.
    /// </summary>
    /// <summary>The header chip that raised the panel currently opening - the
    /// anchor an anchored popup grows from. Null when something else opened it.</summary>
    private FrameworkElement? _lastChip;

    private Button ChipButton(string glyph, string tip, Action click,
                              string? label = null, bool warn = false)
    {
        var mark = new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 18,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        if (warn) mark.Foreground = (Brush)FindResource("Destructive");

        object content = mark;
        if (!string.IsNullOrEmpty(label))
        {
            var sp = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center };
            sp.Children.Add(mark);
            sp.Children.Add(new TextBlock
            {
                Text = label,
                Style = (Style)FindResource("Caption"),
                Foreground = warn ? (Brush)FindResource("Destructive") : (Brush)FindResource("FgSecondary"),
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(5, 0, 0, 0),
                FlowDirection = HasHebrew(label!) ? FlowDirection.RightToLeft : FlowDirection.LeftToRight,
            });
            content = sp;
        }

        var b = new Button
        {
            Style = (Style)FindResource("StatusIndicator"),
            VerticalAlignment = VerticalAlignment.Center,
            MinWidth = 38,
            MinHeight = 38,
            Content = content,
        };
        // Remember WHICH chip was pressed, so a panel that belongs to one of
        // them can open FROM it instead of in the middle of the screen.
        // 🔴 NO ToolTip ANYWHERE IN THIS SHELL. WPF's default tooltip is a light
        // popup with a hairline border: on a dark 10ft surface it reads as a
        // bright box that has appeared over the UI, and it is pointer-only, so
        // on the device this shell is actually driven from it never shows at
        // all. The name still has to exist for narrators and for automation, so
        // it moves to AutomationProperties, where it costs nothing on screen.
        System.Windows.Automation.AutomationProperties.SetHelpText(b, tip);
        b.Click += (_, _) => { if (_layer == "view") { _lastChip = b; Sfx.Play(Sound.Select); click(); } };
        return b;
    }

    /// <summary>One GlassPillIndicator chip: a glyph, optionally with a readout.</summary>
    private UIElement Chip(string glyph, string? text, bool accent = false, bool warn = false)
    {
        var brush = accent ? (Brush)FindResource("Accent")
                  : warn ? (Brush)FindResource("Destructive")
                  : (Brush)FindResource("FgSecondary");

        var sp = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 8, 0),
        };
        // Deliberately a size BELOW the action chips: a readout that matched them
        // would read as a button that does nothing when pressed.
        sp.Children.Add(new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 15,
            Foreground = brush,
            VerticalAlignment = VerticalAlignment.Center,
        });
        if (!string.IsNullOrEmpty(text))
            sp.Children.Add(new TextBlock
            {
                Text = text,
                Style = (Style)FindResource("Caption"),
                Foreground = brush,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(5, 0, 0, 0),
                FlowDirection = HasHebrew(text!) ? FlowDirection.RightToLeft : FlowDirection.LeftToRight,
            });
        return sp;
    }

    private void AddStat(string label, double pct, bool invert = false)
    {
        // Warm at 75, destructive at 90 — for the battery the scale inverts,
        // because LOW is the state worth shouting about.
        double alarmValue = invert ? 100 - pct : pct;
        var brush = alarmValue >= 90 ? (Brush)FindResource("Destructive")
                  : alarmValue >= 75 ? new SolidColorBrush((Color)FindResource("GlowWarmColor"))
                  : (Brush)FindResource("FgSecondary");

        // 🔴 THE PAIR IS ONE ISLAND, and its direction is the LABEL's.
        // Pinning only the value fixed "%54" but left the pair split across the
        // RTL parent: "CPU" landed to the RIGHT of its own number, so a
        // left-to-right scan read "54% CPU" - and with three of them in a row it
        // read as "4% GPU 70% RAM 54% CPU", i.e. every number attached to the
        // WRONG label. A Latin label makes an LTR island ("CPU 54%"); a Hebrew
        // label stays RTL, where label-then-value is already the correct order.
        var sp = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Margin = new Thickness(0, 0, 14, 0),
            FlowDirection = HasHebrew(label) ? FlowDirection.RightToLeft : FlowDirection.LeftToRight,
        };
        sp.Children.Add(new TextBlock
        {
            Text = label,
            Style = (Style)FindResource("Caption"),
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 6, 0),
        });
        sp.Children.Add(new TextBlock
        {
            Text = $"{pct:0}%",
            Style = (Style)FindResource("Subtext"),
            Foreground = brush,
            FontWeight = FontWeights.SemiBold,
            VerticalAlignment = VerticalAlignment.Center,
            // 🔴 "54%" rendered as "%54". The digits are LTR but "%" is a Unicode
            // NEUTRAL, so inside this RTL window it resolves to the RTL side of
            // the run and lands in front of the number. A number+unit is an LTR
            // island, so it gets pinned as one — the same rule that keeps a Latin
            // brand name intact inside Hebrew copy.
            FlowDirection = FlowDirection.LeftToRight,
            // A growing readout must not reflow the centred tab strip.
            MinWidth = 40,
            TextAlignment = TextAlignment.Left,
        });
        StatRow.Children.Add(sp);
    }

    // =====================================================================
    //  library
    // =====================================================================

    /// <summary>True while a library scan is in flight. The screen says
    /// "scanning" instead of "nothing found" for exactly this long.</summary>
    // Starts TRUE: the shell always scans at boot, and the very first frame is
    // drawn before that scan begins - the one moment the distinction matters.
    private bool _scanning = true;

    private async Task ReloadLibraryAsync()
    {
        _scanning = true;
        ShowToast("סורק ספרייה…");
        var settings = _settings;
        var (hub, all, complete) = await Task.Run(() =>
        {
            List<GameEntry> h;
            bool hubOk = true;
            try { h = Catalog.Load(); } catch { h = new List<GameEntry>(); hubOk = false; }
            List<LibraryGame> a;
            bool ok = true;
            try { a = LibraryScanner.ScanAll(settings, h); ok = LibraryScanner.LastScanComplete; }
            catch { a = new List<LibraryGame>(); ok = false; }
            return (h, a, ok && hubOk);
        });

        // 🔴🔴 A FAILED SCAN MUST NOT BE ALLOWED TO DELETE ANYTHING.
        //
        // This used to assign the result straight over the library, and every
        // failure path above hands back an EMPTY list - so a locked registry
        // key, a store mid-update or one thrown exception replaced a fifty-game
        // library with nothing, and the shell sat there looking freshly
        // installed. The scan is a MEASUREMENT of the machine, and a measurement
        // that did not finish is not evidence that something is gone.
        //
        // Complete scan  -> adopt it whole, so a game genuinely uninstalled does
        //                   disappear.
        // Partial scan   -> union: everything it DID find, plus whatever it
        //                   failed to look at this time.
        _scanning = false;

        if (complete)
        {
            _hub = hub;
            _scanned = all;
        }
        else
        {
            if (hub.Count > 0) _hub = hub;
            var keys = new HashSet<string>(all.Select(g => g.Key), StringComparer.OrdinalIgnoreCase);
            var kept = _scanned.Where(g => !keys.Contains(g.Key)).ToList();
            _scanned = all.Concat(kept).ToList();
            if (kept.Count > 0)
                ShowToast($"הסריקה לא הושלמה · {Games(kept.Count)} נשמרו מהסריקה הקודמת");
        }

        SortLibrary();
        if (complete) HideToast();
        RenderTab();
    }

    /// <summary>
    /// The library's sort, matching Winhanced's own SecondarySortAndCounter:
    /// installed-first, recently-added, recently-played, A-Z. Favourites always
    /// float above everything - a favourite you cannot find at a glance is not a
    /// favourite - and hidden games are dropped in every mode.
    /// </summary>
    private void SortLibrary()
    {
        var visible = _scanned.Where(g => _settings.ProfileFor(g.Key, create: false)?.Hidden != true);
        var fav = visible.OrderByDescending(g => _settings.ProfileFor(g.Key, create: false)?.Favorite == true);

        _all = (_settings.SortMode switch
        {
            "name" => fav.ThenBy(g => g.Name, StringComparer.CurrentCulture),
            "played" => fav
                .ThenByDescending(g => g.LastPlayed ?? _settings.ProfileFor(g.Key, create: false)?.LastPlayed ?? DateTime.MinValue)
                .ThenBy(g => g.Name, StringComparer.CurrentCulture),
            "size" => fav
                .ThenByDescending(g => g.SizeBytes)
                .ThenBy(g => g.Name, StringComparer.CurrentCulture),
            // "installed" (the default) is what a console shell wants first: the
            // things you can actually press play on, newest activity on top.
            _ => fav
                .ThenByDescending(g => g.Installed)
                .ThenByDescending(g => g.LastPlayed ?? _settings.ProfileFor(g.Key, create: false)?.LastPlayed ?? DateTime.MinValue)
                .ThenBy(g => g.Name, StringComparer.CurrentCulture),
        }).ToList();

        // Reasoning about sort order from a screenshot of BOX ART is guesswork -
        // the tiles carry no names, and in RTL the reading direction is one more
        // thing to get wrong. The list says it in one run.
        SmoothScroll.Trace($"composition all={_all.Count} installed={_all.Count(g => g.Installed)} " +
                           $"hub={_all.Count(g => g.Source == GameSource.Hub)} " +
                           $"hubInstalled={_all.Count(g => g.Source == GameSource.Hub && g.Installed)} " +
                           $"hubInstalledNoDir={_all.Count(g => g.Source == GameSource.Hub && g.Installed && g.InstallDir.Length == 0)}");
        SmoothScroll.Trace($"sort={_settings.SortMode} :: " +
                           string.Join(" | ", _all.Take(10).Select(g => g.Name)));
    }

    private static readonly (string Key, string Label)[] SortModes =
    {
        ("installed", "מותקנים תחילה"),
        ("played",    "שוחקו לאחרונה"),
        ("name",      "לפי שם"),
        ("size",      "לפי גודל"),
    };

    private string SortLabel() =>
        SortModes.FirstOrDefault(m => m.Key == _settings.SortMode).Label ?? SortModes[0].Label;

    /// <summary>Cycle rather than open a dropdown: a menu that holds four items
    /// costs two presses to open and close, and this one control is on the
    /// busiest row in the app.</summary>
    private void CycleSort()
    {
        int i = Array.FindIndex(SortModes, m => m.Key == _settings.SortMode);
        _settings.SortMode = SortModes[(i + 1 + SortModes.Length) % SortModes.Length].Key;
        Save();
        Sfx.Play(Sound.Navigate);
        SortLibrary();
        _focusTag = "sort";
        RenderTab();
    }

    private IEnumerable<LibraryGame> Filtered() => FilteredBy(_filter);

    /// <summary>Change the filter and remember it. Every assignment goes through
    /// here so a new entry point cannot silently stop persisting it.</summary>
    private void SetFilter(string key)
    {
        _filter = key;
        if (_settings.LastFilter == key) return;
        _settings.LastFilter = key;
        _settings.SaveThrottled();
    }

    /// <summary>
    /// The predicate for ANY chip, not just the current one - so the strip can
    /// show each category's count. Winhanced puts a number on every sidebar row
    /// ("Epic 0"), and that number is the point: it tells you which categories
    /// are worth opening BEFORE you open them.
    /// </summary>
    private IEnumerable<LibraryGame> FilteredBy(string key) => key switch
    {
        // 🔴 This used to also require Source != Hub, on the reasoning that "a
        // catalog entry is not an installed game" - but g.Installed ALREADY says
        // that, and a Hub row carries the flag from the hub's own detector. The
        // exclusion was therefore hiding 13 genuinely-installed titles (measured;
        // every one of them with a real install folder) from both this filter and
        // the home "מותקנים" card. Installed means installed, whoever found it.
        "installed" => _all.Where(g => g.Installed),
        "translated" => _all.Where(g => g.Hub is not null),
        "recent" => _all.Where(g => (g.LastPlayed ?? _settings.ProfileFor(g.Key, false)?.LastPlayed) is not null),
        "fav" => _all.Where(g => _settings.ProfileFor(g.Key, false)?.Favorite == true),
        // One chip per REAL storefront, the way the reference lists them. The
        // set is data-driven (see SourceChips) so a machine with no Epic never
        // shows an Epic chip, and adding a scanner needs no change here.
        _ when key.StartsWith("src:") && Enum.TryParse<GameSource>(key[4..], out var src)
            => _all.Where(g => g.Source == src),
        // 🔴 "אחר" IS NOT "everything that is not Steam". It is what no
        // storefront claimed: Manual entries and Hub-only catalog rows. Defining
        // it as the complement of one store made every GOG/Ubisoft/Xbox title
        // land here too, so the per-store chips beside it were double-counting
        // their own games and the numbers never summed to the library.
        "other" => _all.Where(g => g.Source is GameSource.Manual or GameSource.Hub),
        // NOT the mirror of "installed": that one excludes Hub rows because a
        // catalog entry is not an installed game - but it IS exactly what belongs
        // under "not installed". Excluding it here reported 0 while a third of the
        // grid carried a "לא מותקן" badge.
        "uninst" => _all.Where(g => !g.Installed),
        // A collection is just another filter - Steam's own model. Prefixed so a
        // collection can be called "Steam" without colliding with the source chip.
        _ when key.StartsWith("col:") => CollectionOf(key[4..]) is { } c
                                            ? _all.Where(g => c.Keys.Contains(g.Key))
                                            : _all,
        _ => _all,
    };

    /// <summary>
    /// One chip per storefront that actually found something, in the report's own
    /// order, plus "אחר" for what no store claimed.
    ///
    /// 🔴 DATA-DRIVEN, NOT A FIXED LIST. The reference shows every store it knows
    /// including the empty ones — it can afford to, in a vertical rail. In a
    /// horizontal row that is nine dead chips pushing the live ones onto a second
    /// line, so a store with zero games simply is not offered. The consequence to
    /// keep in mind: this set CHANGES per machine, which is exactly why the LT/RT
    /// cycle order (FilterOrder) is built from the same call and not hardcoded.
    /// </summary>
    private (string Key, string Label)[] SourceChips()
    {
        var names = new (GameSource Src, string Label)[]
        {
            (GameSource.Steam, "Steam"), (GameSource.Epic, "Epic"), (GameSource.Gog, "GOG"),
            (GameSource.Ubisoft, "Ubisoft"), (GameSource.Xbox, "Xbox"), (GameSource.Ea, "EA"),
            (GameSource.Emulator, "אמולטורים"),
        };
        var list = names.Where(n => _all.Any(g => g.Source == n.Src))
                        .Select(n => ("src:" + n.Src, n.Label)).ToList();
        if (_all.Any(g => g.Source is GameSource.Manual or GameSource.Hub)) list.Add(("other", "אחר"));
        return list.ToArray();
    }

    private GameCollection? CollectionOf(string name) =>
        _settings.Collections.FirstOrDefault(c => c.Name == name);

    /// <summary>Built-in chips first, then the user's own - the LT/RT cycle order.</summary>
    private string[] FilterOrder() =>
        FilterKeys.Concat(SourceChips().Select(s => s.Key))
                  .Concat(_settings.Collections.Select(c => "col:" + c.Name)).ToArray();

    // =====================================================================
    //  chrome
    // =====================================================================

    /// <summary>
    /// BumperPillNavigation — `[LB] ‹ tabs › [RB]`, built FRESH for whichever
    /// view is being laid out and registered into that view's focus tree as it
    /// goes.
    ///
    /// 🔴🔴 IT IS A PAGE ELEMENT, NOT A HEADER. Winhanced's home puts the section
    /// title and the cover shelf ABOVE this strip and a row of destination tiles
    /// BELOW it — the strip is the waist of the page, not its ceiling — while the
    /// library page carries the identical control at the very top. One control,
    /// two positions, decided by the view. A strip welded into the chrome can
    /// only ever be at the top, which is exactly why our home never read like
    /// theirs no matter how the pills themselves were styled.
    ///
    /// Rebuilding it per view is not waste: `RenderTab` tears the focus tree
    /// down every time anyway, and building the pills in the same pass that
    /// registers them is the rule that keeps focus and layout from drifting
    /// apart. `IsChecked` is set BEFORE the handler is attached, so construction
    /// can never re-enter `SetTab`.
    /// </summary>
    private FrameworkElement NavStrip(Thickness margin)
    {
        var strip = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Center,
            Margin = margin,
        };
        strip.Children.Add(BumperGlyph("LB"));
        foreach (string t in Tabs)
        {
            string tab = t;
            var rb = new RadioButton
            {
                Style = (Style)FindResource("BumperPill"),
                Content = TabNames[t],
                Tag = t,
                IsChecked = t == _tab,
                GroupName = "tabs",
            };
            rb.Checked += (_, _) => { if (_tab != tab) SetTab(tab); };
            strip.Children.Add(Nav(rb));
        }
        strip.Children.Add(BumperGlyph("RB"));
        return strip;
    }

    /// <summary>
    /// The shoulder indicator flanking the pill strip.
    ///
    /// TEXT, not an icon glyph. The pictographic versions were a silent trap:
    /// two of the four codepoints rendered as tofu here and one of them was
    /// U+E7E8 - the POWER icon - so the right trigger advertised itself with a
    /// standby symbol. A shoulder has no agreed glyph across Segoe versions,
    /// pads disagree on its shape anyway, and Winhanced labels these in text
    /// too. A label cannot go missing.
    /// </summary>
    private UIElement BumperGlyph(string label) => new Border
    {
        Style = (Style)FindResource("HintGlyph"),
        Margin = new Thickness(10, 0, 10, 0),
        MinWidth = 34,
        // ⚠ HintGlyph is a fixed 26px CIRCLE, and a keyboard's label for a
        // shoulder is "Shift+Tab", not two letters. Releasing the width lets the
        // circle grow into a stadium instead of guillotining the text - the same
        // release SetHints already makes for the footer, and the same trap that
        // once rendered the stats pill as an empty circle.
        Width = double.NaN,
        Padding = new Thickness(9, 0, 9, 0),
        VerticalAlignment = VerticalAlignment.Center,
        Child = new TextBlock
        {
            // Through GlyphFor, like every other prompt in the shell. This one
            // control printed the XBOX letters to everyone - so a PlayStation
            // pad was told to press "LB", a button it does not have, and a
            // keyboard was told to press a shoulder it does not have either.
            Text = GlyphFor(LiveToken(label)),
            FontSize = 11,
            FontWeight = FontWeights.SemiBold,
            Foreground = (Brush)FindResource("FgMuted"),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            // "LB" is a Latin token; an RTL container would reorder the pair.
            FlowDirection = FlowDirection.LeftToRight,
        },
    };

    private void SetTab(string tab)
    {
        if (tab != "settings" && _sizesOpen) { _settings.Save(); _sizesOpen = false; }
        _tab = tab;
        // The strip belongs to the view, so it is re-created (already checked)
        // by the render below — there is nothing here to keep in sync.
        Sfx.Play(Sound.Navigate);
        RenderTab();
    }

    private void CycleTab(int delta)
    {
        int i = Array.IndexOf(Tabs, _tab);
        if (i < 0) i = 0;
        SetTab(Tabs[(i + delta + Tabs.Length) % Tabs.Length]);
    }

    /// <summary>
    /// The ONLY safe way for a background event to repaint the page.
    ///
    /// 🔴🔴 RenderTab() STARTS WITH ResetNav(), so a repaint fired from a
    /// timer or a process-exit callback does not just redraw pixels - it
    /// REBUILDS THE FOCUS MAP. While a card, the quick menu or a dialog is
    /// open that map belongs to the MODAL, so a session ending underneath one
    /// replaced its D-pad list with the hidden page's controls and the stick
    /// started walking through things the user could not see.
    ///
    /// Skipping it is free: every route back to the page - CloseBlade,
    /// CloseQuick, CloseSearch, CloseDialog - re-renders on its way out.
    /// </summary>
    private void RepaintIfShowing()
    {
        // Only two pages actually show live session state; the rest would be
        // rebuilding an identical tree on every tick.
        if (_layer != "view" || _tab is not ("perf" or "home")) return;

        // 🔴 AND IT MUST NOT MOVE THE RING. A repaint here is the SHELL's idea,
        // not the user's - so landing them back on the first tile because a
        // game they were not looking at changed state reads as the console
        // taking the stick out of their hand. The index survives the rebuild
        // because the page is built in the same order; a title appearing or
        // disappearing shifts it by one, which is still incomparably better
        // than snapping to the top of the shelf.
        int keep = Keyboard.FocusedElement is FrameworkElement fe ? _nav.IndexOf(fe) : -1;
        RenderTab();
        // Set AFTER the render: ResetNav() clears this, and the FocusFirst that
        // reads it is queued at Loaded priority, so it runs later than this line.
        if (keep >= 0) _navPreferred = keep;
    }

    /// <summary>
    /// Rebuild the current screen — at most ONCE per turn of the dispatcher.
    ///
    /// 🔴 A SECOND RENDER IN THE SAME CALL STACK IS ALWAYS A BUG, AND IT IS
    /// ALWAYS VISIBLE. Rebuilding costs the page its scroll position, so the
    /// restored focus animates the view back down from the top; do it twice and
    /// the screen drops, snaps back and drops again. Callers legitimately do not
    /// know whether something further up the stack has already asked (the picker
    /// path had CloseDialog and the pick callback both asking, neither of them
    /// wrong on its own), so coalescing belongs here rather than in a rule every
    /// future caller has to remember.
    ///
    /// Send priority runs the moment the current handler returns, so every state
    /// change made around the call is already in place when the one render runs.
    /// </summary>
    private bool _renderQueued;

    private void RenderTab()
    {
        if (_renderQueued) return;
        _renderQueued = true;
        Dispatcher.BeginInvoke(System.Windows.Threading.DispatcherPriority.Send, () =>
        {
            _renderQueued = false;
            RenderTabCore();
        });
    }

    private void RenderTabCore()
    {
        ResetNav();

        // 🔴 THE OLD VIEW IS NOT CLEARED HERE. It used to be — and that one line
        // is what put an empty background between every two screens: the page
        // vanished, the ground showed through, and only THEN did the new page
        // fade up from nothing. Two screens must overlap for the length of the
        // hand-off, so keep the outgoing page alive and let CrossFade retire it.
        var outgoing = ViewHost.Children.Count > 0
            ? ViewHost.Children[ViewHost.Children.Count - 1]
            : null;
        // Anything older than the topmost (a render that landed mid-fade) goes
        // now — it is already invisible, and letting them pile up would leave a
        // stack of dead pages under the live one.
        while (ViewHost.Children.Count > 1) ViewHost.Children.RemoveAt(0);
        if (outgoing is not null) outgoing.IsHitTestVisible = false;

        // Which way the screens travel. The tab strip is a row, so a tab change
        // slides along it; a re-render of the SAME page has no direction and
        // keeps the plain rise, because sliding a page out from under someone
        // who did not navigate reads as a glitch.
        int from = Array.IndexOf(Tabs, _renderedTab), to = Array.IndexOf(Tabs, _tab);
        double dx = (_renderedTab is null || from < 0 || to < 0 || from == to) ? 0
                  : (to > from ? 34 : -34);
        // 🔴 RE-RENDERING THE SCREEN YOU ARE ALREADY ON IS NOT AN ARRIVAL.
        // Closing any popup rebuilds the current tab, and the entrance animation
        // treated that exactly like opening a new one: the page was seeded 18px
        // low and slid up. Nothing had navigated, so what the eye reads is the
        // whole menu dropping and snapping back - a shudder on the way out of
        // every single dialog. A page that did not change must not move.
        bool sameScreen = _renderedTab is not null && _renderedTab == _tab;
        _renderedTab = _tab;

        // The strip is built FIRST so it registers ahead of the page content and
        // "up" from the first control still reaches it — but it is placed in the
        // PINNED host (see NavHost in the XAML), not inside the scrolling page,
        // so it can never scroll out of reach and never rides the cross-fade.
        _pageSteps.Clear();     // they belong to the page being replaced
        NavHost.Children.Clear();
        NavHost.Children.Add(NavStrip(new Thickness(0, 2, 0, 10)));

        // 🔴 ENTRY FOCUS BELONGS TO THE CONTENT, NOT TO THE WAY IN. You just
        // asked for a tab; landing on the nav means the first thing you do is
        // leave it again. The strip is first in the focus order so "up" reaches
        // it — only the STARTING index moves past it.
        _navViewStart = _nav.Count;

        // How long a screen takes to BUILD is the number behind "the menus feel
        // slow", and it is invisible from outside: the animation that follows is
        // a fixed 260ms, so anything the user feels on top of that happened here.
        var __sw = System.Diagnostics.Stopwatch.StartNew();

        FrameworkElement view;
        if (_tab is "home") view = BuildHome();
        else if (_tab is "library") view = BuildLibrary();
        else
        {
            var doc = new StackPanel();
            doc.Children.Add(_tab switch
            {
                "news" => BuildNews(),
                "downloads" => BuildDownloads(),
                "perf" => BuildPerformance(),
                "plugins" => BuildPlugins(),
                "stream" => BuildStreaming(),
                _ => BuildSettings(),
            });
            // A retry for the case the startup read did not finish (or the
            // machine was offline then). No-op once it has landed.
            if ((_tab == "settings" || _tab == "plugins") && !_shellLoaded) _ = LoadShellAsync();
            view = doc;
        }
        SmoothScroll.Trace($"build {_tab} took {__sw.ElapsedMilliseconds}ms");
        var incoming = SmoothScroll.Host(view, _settings.AnimationsEnabled);
        ViewHost.Children.Add(incoming);
        CrossFade(outgoing, incoming, dx, sameScreen);
        RefreshArtStrength();   // home shows the art in full; a grid dims it back
        SetHints(("A", "בחירה"), ("B", "חזרה"), ("X", "תפריט מהיר"), ("Y", "חיפוש"), ("LB/RB", "החלפת מסך"));
        FooterNote.Text = FooterStatus();
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () =>
        {
            if (_focusTag is { } tag)
            {
                _focusTag = null;
                var again = _nav.FirstOrDefault(c => (c as FrameworkElement)?.Tag as string == tag);
                if (again is not null) { again.Focus(); return; }
            }
            if (_focusGameKey is { } gkey)
            {
                _focusGameKey = null;
                var tile = _nav.FirstOrDefault(c => (c as FrameworkElement)?.Tag is LibraryGame lg
                                                    && string.Equals(lg.Key, gkey, StringComparison.OrdinalIgnoreCase));
                if (tile is not null) { tile.Focus(); return; }
            }
            // The same rule one level down, as a net for every other caller:
            // this runs at Loaded priority, so a modal can have opened in the
            // gap between the render and this callback.
            if (_layer is "dialog" or "blade" or "quick" or "search" or "onboard" or "intro") return;
            FocusFirst();

            // Gated: is the page's TAIL actually reachable? An inner page
            // Scroller nested in the outer host is exactly the shape that can
            // clip trailing content, and it does it silently.
            // 🔴 NOT Children[0]. While a cross-fade is running the outgoing page
            // is still child 0, so measuring it would report the PREVIOUS screen's
            // extent under this screen's name — a reachability check that quietly
            // audits the wrong page is worse than none.
            if (ViewHost.Children.Count > 0 &&
                ViewHost.Children[ViewHost.Children.Count - 1] is ScrollViewer host)
                SmoothScroll.Trace($"tab={_tab} outer ext={host.ExtentHeight:0} vp={host.ViewportHeight:0} " +
                                   $"scrollable={host.ScrollableHeight:0}");
        });
    }

    /// <summary>
    /// The footer's reading-start half. Winhanced puts a live status line
    /// opposite the controller legend, and the pairing is the point: one side
    /// says what you can DO, the other says where you ARE. Ours reports real
    /// counts only - a status bar that shows a constant is furniture, and the
    /// moment it can be wrong it is worse than empty.
    /// </summary>
    private string FooterStatus()
    {
        int total = _all.Count;
        int heb = _all.Count(g => g.Hub is not null);
        // THE NUMBER WAS EVERY SESSION AND THE WORD SAID "SUSPENDED". A game
        // that was simply RUNNING was counted as parked, on the one line of the
        // shell whose whole justification is that it never shows a value that
        // can be wrong. Both states are worth reporting and they are not the
        // same state: one is using the machine, the other is holding memory
        // while frozen.
        int running   = _sessions?.Sessions.Count(x => !x.Suspended) ?? 0;
        int suspended = _sessions?.Sessions.Count(x => x.Suspended) ?? 0;

        string s = _tab switch
        {
            "library" => $"מציג {Filtered().Count()} מתוך {total} משחקים",
            "downloads" => $"{heb} משחקים עם תרגום עברי בספרייה",
            "perf" => "מדדים חיים מהמערכת, מתרעננים כל שתי שניות",
            "plugins" => "תוספים מותקנים והמצב שלהם",
            "stream" => "מחפש מארחי סטרימינג ברשת המקומית",
            "settings" => "ההעדפות נשמרות מיד ומקומית",
            _ => $"{total} משחקים · {heb} מתורגמים לעברית",
        };
        if (running > 0) s += $"  ·  {running} פועלים";
        if (suspended > 0) s += $"  ·  {suspended} מושהים";
        return s;
    }

    /// <summary>Which tab the CURRENT on-screen page belongs to, so a re-render
    /// of the same page can be told apart from a real navigation.</summary>
    private string? _renderedTab;

    /// <summary>
    /// Hand one page over to the next with both on screen at once. The old page
    /// slides and fades out along the SAME axis the new one arrives on, so the
    /// two read as one move — enter and exit sharing a path is what makes a
    /// transition feel like the screen turned rather than blinked.
    /// </summary>
    private void CrossFade(UIElement? outgoing, FrameworkElement incoming, double dx,
                           bool sameScreen = false)
    {
        // Same screen, redrawn: swap it with no motion and no fade at all. Any
        // transition here is a transition between a thing and itself.
        if (sameScreen || !_settings.AnimationsEnabled)
        {
            // Instant swap on a weak machine or an explicit opt-out: the old
            // page goes NOW, so the two never overlap and nothing is animated.
            if (outgoing is not null) ViewHost.Children.Remove(outgoing);
            return;
        }

        // 🔴 SMOOTH IS NOT THE SAME AS SLOW, AND 260ms WAS SLOW. Lengthening the
        // hand-off to sit better on the house curve made every screen change
        // feel like it lagged the key - measured: building a screen costs 0-12ms
        // (205ms once, for the first home render), so everything the user was
        // waiting on was this animation. 170ms keeps the curve and gives the
        // time back; the opacity leads it, so the new screen is readable at
        // ~110ms and the last of the movement lands under the eye's own latency.
        var d = new Duration(TimeSpan.FromMilliseconds(170));
        var ease = HouseEase(arriving: true);

        incoming.Opacity = 0;
        var tin = new TranslateTransform(dx, dx == 0 ? 18 : 0);
        incoming.RenderTransform = tin;
        incoming.BeginAnimation(OpacityProperty,
            new DoubleAnimation(0, 1, new Duration(TimeSpan.FromMilliseconds(110))));
        tin.BeginAnimation(
            dx == 0 ? TranslateTransform.YProperty : TranslateTransform.XProperty,
            new DoubleAnimation(dx == 0 ? 18 : dx, 0, d) { EasingFunction = ease });

        if (outgoing is null) return;

        // The outgoing page leaves the way the incoming one came in, and leaves
        // FASTER than the arrival — two pages at full strength in the same frame
        // is a smear, so the old one clears while the new one is still rising.
        var outD = new Duration(TimeSpan.FromMilliseconds(d.TimeSpan.TotalMilliseconds * 0.6));
        var fade = new DoubleAnimation(1, 0, outD);
        // Removing it in Completed and NOT before: this is the one line that
        // keeps the ground from showing through mid-hand-off.
        fade.Completed += (_, _) => ViewHost.Children.Remove(outgoing);
        var tout = new TranslateTransform();
        outgoing.RenderTransform = tout;
        outgoing.BeginAnimation(OpacityProperty, fade);
        if (dx != 0)
            tout.BeginAnimation(TranslateTransform.XProperty,
                new DoubleAnimation(0, -dx * 0.55, outD) { EasingFunction = ease });
    }

    /// <summary>
    /// A floating surface ARRIVING.
    ///
    /// It grows the last 4% into place while it rises and fades, because that is
    /// what a pane of glass coming towards you does — a pure fade reads as a
    /// picture being switched on, and a pure slide reads as a card being dealt.
    /// The scale is deliberately tiny: anything larger turns every panel into a
    /// zoom effect, which is the thing that makes a shell feel cheap.
    /// </summary>
    private void Animate(FrameworkElement el)
    {
        if (!_settings.AnimationsEnabled) return;

        var d = new Duration(TimeSpan.FromMilliseconds(240));
        var ease = HouseEase(arriving: true);

        el.Opacity = 0;
        el.RenderTransformOrigin = new Point(0.5, 0.35);

        var move = new TranslateTransform(0, 14);
        var grow = new ScaleTransform(0.96, 0.96);
        var g = new TransformGroup();
        g.Children.Add(grow);
        g.Children.Add(move);
        el.RenderTransform = g;

        // Opacity leads the geometry: the surface is already readable while it is
        // still settling, so the motion is felt rather than waited for.
        el.BeginAnimation(OpacityProperty,
            new DoubleAnimation(0, 1, new Duration(TimeSpan.FromMilliseconds(150))) { EasingFunction = ease });
        move.BeginAnimation(TranslateTransform.YProperty, new DoubleAnimation(14, 0, d) { EasingFunction = ease });
        grow.BeginAnimation(ScaleTransform.ScaleXProperty, new DoubleAnimation(0.96, 1, d) { EasingFunction = ease });
        grow.BeginAnimation(ScaleTransform.ScaleYProperty, new DoubleAnimation(0.96, 1, d) { EasingFunction = ease });
    }

    /// <summary>
    /// Which device the footer prompts are drawn for. Detected from the pad that
    /// is plugged in, then overridden by whatever the user LAST touched — a pad
    /// can be connected and idle while the person is on the keyboard, and the
    /// prompts have to name keys that person can actually press.
    /// </summary>
    private PadKind _padKind = PadKind.Keyboard;
    private PadKind? _padHardware;
    private bool _padWasConnected;

    /// <summary>
    /// The user's explicit choice of prompts, or null for "follow detection".
    /// See AppSettings.PadStyle for why an override has to exist at all.
    /// </summary>
    private PadKind? PadOverride => _settings.PadStyle switch
    {
        "ps5" => PadKind.Ps5,
        "ps4" => PadKind.Ps4,
        "xbox" => PadKind.Xbox,
        "keyboard" => PadKind.Keyboard,
        _ => null,
    };

    /// <summary>Re-read the connected pad and, if the prompts change, redraw them.</summary>
    private void RefreshPadKind(bool usedPad)
    {
        PadKind want;
        // An explicit choice outranks every probe, on every input path — a user
        // who has told us what they are holding must not have it argued with the
        // moment they touch a key.
        if (PadOverride is { } forced) want = forced;
        else if (usedPad)
        {
            // Detect only on a PAD event — that event is itself proof a pad is
            // connected, so the scan runs at most once and never on the
            // keystroke path, where ~20 P/Invokes per character would be pure
            // waste. A pad plugged in mid-session is caught by its first press.
            _padHardware ??= PadIdentity.Detect();
            want = _padHardware ?? PadKind.Xbox;
        }
        else want = PadKind.Keyboard;

        if (want == _padKind) return;
        _padKind = want;
        if (_lastHints is { } h) SetHints(h);       // same prompts, this device's glyphs
    }

    /// <summary>
    /// The re-detect the SETTINGS rows run — deliberately not RefreshPadKind.
    ///
    /// 🔴🔴 RefreshPadKind(usedPad: true) ENDS IN `?? PadKind.Xbox`, and that
    /// fallback is correct where it lives: it runs off a PAD EVENT, and the
    /// event is itself proof a controller is connected, so "I could not
    /// identify which pad" safely means "assume Xbox". Called from a BUTTON it
    /// means something else entirely — on a keyboard-only PC the probe finds
    /// nothing, the fallback fires anyway, and every prompt in the shell
    /// relabels itself A / B / X / Y. The user is then told to press buttons
    /// that do not exist on the machine, which is worse than the row doing
    /// nothing at all.
    ///
    /// 🔴 AND A RE-SCAN MUST ALWAYS ANSWER. All three of these rows used to
    /// re-render and stop. When the answer was unchanged — the common case,
    /// since the usual reason to press "check again" is that no pad was found —
    /// the screen redrew identically and the press was indistinguishable from a
    /// dead button. Every path below ends in a toast that states the result.
    /// </summary>
    private void RedetectPad()
    {
        Sfx.Play(Sound.Select);
        _padHardware = null;
        var found = PadIdentity.Detect();

        _padHardware = found;
        _padKind = PadOverride ?? found ?? PadKind.Keyboard;
        if (_lastHints is { } h) SetHints(h);      // same prompts, this device's glyphs

        // With an override set, the scan is still worth running and still worth
        // REPORTING — it is how the user finds out whether the override is even
        // needed — but it must not be phrased as if it changed the prompts.
        if (PadOverride is { } forced)
            ShowToast(found is { } d
                ? $"זוהה {KindNameOf(d)} · הרמזים נשארים {KindNameOf(forced)} לפי הבחירה שלכם"
                : $"לא נמצא שלט · הרמזים נשארים {KindNameOf(forced)} לפי הבחירה שלכם");
        else
            ShowToast(found is { } k
                ? $"זוהה {KindNameOf(k)} · רמזי הכפתורים עודכנו"
                : "לא נמצא שלט מחובר · נשארים ברמזי מקלדת");
    }

    /// <summary>
    /// The colour a face glyph is drawn in.
    ///
    /// 🔴 THE THREE FAMILIES ARE TOLD APART BY COLOUR, NOT BY SHAPE. PS4 and PS5
    /// carry the IDENTICAL four symbols — ✕ ○ □ △ — so a shape-only prompt cannot
    /// distinguish a DualShock from a DualSense, which is exactly the complaint
    /// this answers. Sony's own split is the one to follow: the DualShock 4 tints
    /// each face button, and the DualSense deliberately dropped that for a
    /// monochrome engraved look. So PS4 gets the colours, PS5 stays white, and
    /// Xbox keeps its letters as they are.
    ///
    /// ⚠ DRAWN, NOT BORROWED. These are Unicode glyphs in the shell's own font
    /// with our own brushes over them — no vendor artwork is copied into the
    /// build, which is the same rule the rest of this shell follows for every
    /// icon it shows.
    /// </summary>
    private Brush GlyphBrushFor(string token)
    {
        if (_padKind != PadKind.Ps4) return (Brush)FindResource("FgPrimary");
        return token switch
        {
            "A" => Brushed("#FF7FB2FF"),   // ✕ blue
            "B" => Brushed("#FFFF6E6E"),   // ○ red
            "X" => Brushed("#FFFF8ED2"),   // □ pink
            "Y" => Brushed("#FF6BE39B"),   // △ green
            _ => (Brush)FindResource("FgPrimary"),
        };

        static Brush Brushed(string hex)
        {
            var b = new SolidColorBrush((Color)ColorConverter.ConvertFromString(hex));
            b.Freeze();
            return b;
        }
    }

    /// <summary>One name per device — shared by the settings row and the toast,
    /// so the two can never disagree about what was detected.</summary>
    private static string KindNameOf(PadKind k) => k switch
    {
        PadKind.Ps5 => "שלט PlayStation 5 (DualSense)",
        PadKind.Ps4 => "שלט PlayStation 4 (DualShock)",
        PadKind.Xbox => "שלט Xbox",
        _ => "מקלדת",
    };

    /// <summary>
    /// Open one of Windows' own settings panels (a ms-settings: URI).
    ///
    /// ⚠ THIS IS NOT A ROUTE BACK TO THE DESKTOP LAUNCHER. The console's one hard
    /// rule is that it has exactly ONE door back to the launcher, in Settings —
    /// and this is not it: it opens a WINDOWS panel over the console, which stays
    /// running underneath. Alt-Tab returns to it.
    ///
    /// It reports failure. A ms-settings URI can be blocked by policy on a
    /// managed machine, and a row that silently does nothing is the failure mode
    /// this shell keeps having to design out.
    /// </summary>
    private void OpenSystemPanel(string uri, string what)
    {
        Sfx.Play(Sound.Select);
        try
        {
            Process.Start(new ProcessStartInfo(uri) { UseShellExecute = true });
            ShowToast($"נפתח: {what} של Windows");
        }
        catch
        {
            Sfx.Play(Sound.Warning);
            ShowToast($"לא ניתן לפתוח את {what} · ייתכן שהם חסומים במחשב הזה");
        }
    }

    /// <summary>The five prompt styles, in the order the settings row cycles them.</summary>
    private static readonly string[] PadStyles = { "auto", "ps5", "ps4", "xbox", "keyboard" };

    private string PadStyleLabel() => _settings.PadStyle switch
    {
        "ps5" => "PlayStation 5",
        "ps4" => "PlayStation 4",
        "xbox" => "Xbox",
        "keyboard" => "מקלדת",
        _ => "אוטומטי",
    };

    /// <summary>
    /// Step to the next prompt style and repaint everything that draws one.
    ///
    /// A CYCLE rather than a list of five rows: on a 10ft screen five radio rows
    /// for one three-word answer is a page of chrome, and every other one-of-N
    /// choice in this shell (sort order, category) already cycles in place. The
    /// current value is in the row's own title, so the state is never hidden
    /// behind the press.
    /// </summary>
    private void PickPadStyle() => Picker(
        "סגנון רמזי הכפתורים",
        "איזה סימנים יוצגו בשורת הרמזים ובכל המסכים. \"אוטומטי\" הולך לפי מה שמחובר; " +
        "בחירה מפורשת גוברת עליו תמיד - שימושי כששלט פלייסטיישן מגיע למחשב מחופש לאקסבוקס.",
        new[]
        {
            ("auto",     "אוטומטי",   "לפי השלט המחובר כרגע - חוזר למקלדת כשאין שלט"),
            ("ps5",      "PlayStation 5", "✕ ○ □ △"),
            ("ps4",      "PlayStation 4", "✕ ○ □ △"),
            ("xbox",     "Xbox",      "A B X Y"),
            ("keyboard", "מקלדת",     "Enter · Esc · מקשי אותיות"),
        },
        _settings.PadStyle, SetPadStyle);

    private void SetPadStyle(string style)
    {
        _settings.PadStyle = style;
        Save();

        // Auto has to re-ask the hardware; the explicit styles apply immediately.
        if (_settings.PadStyle == "auto")
        {
            _padHardware = PadIdentity.Detect();
            _padKind = _padHardware ?? PadKind.Keyboard;
        }
        else _padKind = PadOverride!.Value;

        if (_lastHints is { } h) SetHints(h);
        RenderTab();
        ShowToast($"רמזי הכפתורים: {PadStyleLabel()}");
    }

    // ---- display size / card style (the "גודל ותצוגה" section) -------------

    private double UiScale => _settings.UiScale is >= 0.5 and <= 2.0 ? _settings.UiScale : 1.0;

    /// <summary>
    /// Scale the ENTIRE shell, not just the covers.
    ///
    /// 🔴 LayoutTransform, NOT RenderTransform, AND THAT IS THE WHOLE REASON
    /// THIS CANNOT BREAK THE DISPLAY. A RenderTransform scales pixels AFTER
    /// layout: text would be magnified rather than re-rendered, and everything
    /// would grow straight over its neighbours and off the frame. A
    /// LayoutTransform is applied BEFORE the measure pass, so WPF measures the
    /// content against the window DIVIDED by the scale and then draws the result
    /// scaled - every row re-wraps, every scroller recomputes its extent, and
    /// vector text is rendered at its new size. "Bigger" therefore means "less
    /// fits on a screen, and it scrolls", which is correct, instead of "it
    /// spills over the edge", which is what the naive version does.
    ///
    /// The background images are deliberately NOT included: they fill the window
    /// by definition, and scaling them would only crop or letterbox the art.
    /// </summary>
    private static Transform Scaled(double s)
    {
        if (Math.Abs(s - 1.0) <= 0.001) return Transform.Identity;
        var st = new ScaleTransform(s, s);
        st.Freeze();              // may be shared between elements
        return st;
    }

    /// <summary>
    /// The type sizes as the design shipped them, captured ONCE before anything
    /// scales them.
    ///
    /// 🔴 READ THE BASE, NEVER MULTIPLY IN PLACE. Scaling the live resource by
    /// the factor each time compounds: 1.1 applied twice is 1.21, and a user
    /// dragging a slider would watch the text run away from them and never come
    /// back, because the original numbers no longer exist anywhere.
    /// </summary>
    private static readonly string[] FontKeys =
        { "FsCaption", "FsBody2", "FsBody1", "FsSubtitle", "FsH3", "FsH2", "FsH1", "FsDisplay" };
    private Dictionary<string, double>? _fontBase;

    private void ApplyUiScale()
    {
        double s = UiScale;

        // The whole shell first, then the two regions that carry their own
        // multiplier on top of it.
        Chrome.LayoutTransform = Scaled(s);
        HeaderRow.LayoutTransform = Scaled(GroupEffective("chrome"));
        FooterBar.LayoutTransform = Scaled(s * GroupEffective("hints"));

        _fontBase ??= FontKeys.ToDictionary(k => k, k => (double)FindResource(k));
        foreach (var k in FontKeys)
            Resources[k] = _fontBase[k] * GroupEffective("text");
    }

    /// <summary>
    /// 🔴 THE WHOLE LADDER MOVED DOWN ONE RUNG. What used to be the small
    /// step is what this shell should look like by default, so every name now
    /// sits on the step below its old value: רגיל is the old קטן, גדול is the
    /// old רגיל, ענק is the old גדול, and קטן is a new step smaller than
    /// anything that existed before. The NAMES are the fixed points - a step
    /// called רגיל has to BE the ordinary one - so the numbers moved, not the
    /// words.
    /// </summary>
    private string UiScaleLabel() => UiScale switch
    {
        < 0.79 => "קטן",
        < 0.93 => "רגיל",
        < 1.08 => "גדול",
        _ => "ענק",
    };

    private void PickUiScale() => Picker(
        "גודל התצוגה",
        "מגדיל או מקטין את כל מה שעל המסך - כרטיסיות, טקסט, שורות, כפתורים ורמזים. " +
        "ככל שגדול יותר, נוח יותר לקרוא מרחוק ופחות נכנס למסך.",
        new[]
        {
            ("0.72", "קטן",  "הכי הרבה תוכן על המסך - למסך קטן שיושבים ממנו קרוב"),
            ("0.85", "רגיל", "ברירת המחדל"),
            ("1.00", "גדול", "נוח לקריאה ממרחק ספה"),
            ("1.15", "ענק",  "לטלוויזיה גדולה מעבר לחדר"),
            ("custom", "התאמה אישית", "פס נפרד לכרטיסיות, לשורה העליונה, לטקסט ולרמזי הכפתורים"),
        },
        UiScale.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture),
        key =>
        {
            if (key == "custom") { PickPerGroupSizes(); return; }
            _settings.UiScale = double.Parse(key, System.Globalization.CultureInfo.InvariantCulture);
            _settings.Save();
            RenderTab();
            ApplyUiScale();
            ShowToast($"גודל התצוגה: {UiScaleLabel()}");
        });

    private string CardStyle => _settings.CardStyle is "art" or "text" ? _settings.CardStyle : "full";

    private string CardStyleLabel() => CardStyle switch
    {
        "art" => "עטיפה בלבד",
        "text" => "טקסט בלבד",
        _ => "כרטיסייה מלאה",
    };

    private string CardStyleDetail() => CardStyle switch
    {
        "art" => "רק העטיפה, בלי תגיות ובלי סימון החנות - מראה נקי",
        "text" => "רשימת שמות קומפקטית בלי עטיפות - הכי מהיר לספרייה גדולה",
        _ => "עטיפה + תגיות (עברית / מותקן / פועל) + סימון החנות",
    };

    private void PickCardStyle() => Picker(
        "תצוגת כרטיסייה",
        "מה כרטיסייה מציגה בפועל.",
        new[]
        {
            ("full", "כרטיסייה מלאה", "עטיפה + תגיות (עברית / מותקן / פועל) + סימון החנות"),
            ("art",  "עטיפה בלבד",    "רק העטיפה, בלי תגיות ובלי סימון החנות - מראה נקי"),
            ("text", "טקסט בלבד",     "רשימת שמות קומפקטית בלי עטיפות - הכי מהיר לספרייה גדולה"),
        },
        CardStyle,
        key =>
        {
            _settings.CardStyle = key;
            _settings.Save();
            RenderTab();
            ShowToast($"תצוגת כרטיסייה: {CardStyleLabel()}");
        });

    private (string glyph, string label)[]? _lastHints;

    /// <summary>
    /// A logical prompt token to the label THIS device actually carries.
    ///
    /// 🔴 THE TOKEN IS THE MEANING, NOT THE LETTER. Calling it "A" and printing
    /// "A" is right on exactly one of the four devices this shell is used with:
    /// on a PlayStation pad that button is ✕, and on a keyboard there is no
    /// face button at all — the key is Enter. Printing the Xbox letter to
    /// everyone is the same class of error as leaving an English string in a
    /// Hebrew screen: it is legible, and it is not what the user is holding.
    /// ⚠ PS4 and PS5 differ ONLY in the shoulders (L1/R1 vs the same, but the
    /// triggers read L2/R2 on both) — the face glyphs are identical, which is
    /// why they share every branch except that one.
    /// </summary>
    private string GlyphFor(string token) => _padKind switch
    {
        // A remapped key has to reach the legend as well; the literals below
        // remain the fallback for tokens that are not bindable actions.
        PadKind.Keyboard when ActionForToken(token) is { } act && KeyFor(act) is var k && k != Key.None
            => KeyLabel(k),
        PadKind.Keyboard => token switch
        {
            "A" => "Enter", "B" => "Esc", "X" => "X", "Y" => "Y",
            // 🔴 Q AND E, NOT Tab AND Shift+Tab. Tab is a focus key: WPF owns
            // it, a modifier combination is not something a 10ft shell should
            // ask for at all, and Shift+Tab never reached this switch in the
            // first place (only `Key.Tab` was cased, so the reverse direction
            // was a prompt for a binding that did not exist). Q and E are the
            // two keys a hand already resting on WASD can reach without moving,
            // and they are plain single presses.
            "LB/RB" => "Q/E", "LB" => "E", "RB" => "Q",
            "LT/RT" => "PgUp/PgDn", "LT" => "PgUp", "RT" => "PgDn",
            "Start" => "Enter", "☰" => "Enter",
            _ => token,
        },
        PadKind.Ps5 => token switch
        {
            "A" => "✕", "B" => "○", "X" => "□", "Y" => "△",
            "LB/RB" => "L1/R1", "LB" => "L1", "RB" => "R1",
            "LT/RT" => "L2/R2", "LT" => "L2", "RT" => "R2",
            // ⚠ The DualSense renamed Share to CREATE. It is the one LABEL that
            // differs between the two Sony pads — the faces and shoulders are
            // identical, which is why they are told apart by colour instead
            // (see GlyphBrushFor).
            "Start" => "OPTIONS", "Back" => "CREATE",
            _ => token,
        },
        PadKind.Ps4 => token switch
        {
            "A" => "✕", "B" => "○", "X" => "□", "Y" => "△",
            "LB/RB" => "L1/R1", "LB" => "L1", "RB" => "R1",
            "LT/RT" => "L2/R2", "LT" => "L2", "RT" => "R2",
            "Start" => "OPTIONS", "Back" => "SHARE",
            _ => token,
        },
        _ => token,        // Xbox: the tokens ARE the Xbox labels
    };

    /// <summary>
    /// The four PlayStation face buttons, DRAWN.
    ///
    /// 🔴 ✕ ○ □ △ ARE FOUR UNRELATED CODEPOINTS, NOT A SET. They come from
    /// different Unicode blocks (a multiplication sign, a geometric circle, a
    /// geometric square, a geometric triangle) and no font treats them as a
    /// family: the circle and the square are hairline outlines with no bold
    /// variant, while ✕ and △ do get heavier - so asking for Bold produced two
    /// thick shapes next to two thin ones, at three different optical sizes,
    /// each sitting on its own baseline. It read as a rendering fault, because
    /// it was one.
    ///
    /// Drawing them is also the only way to keep this legal: Sony's and Valve's
    /// own button icons are art assets, and this shell never copies one - it
    /// re-implements the shape, which is exactly what it does for every other
    /// glyph it needs and cannot type.
    ///
    /// One 100x100 coordinate box for all four, scaled by ONE Viewbox, so the
    /// stroke weight is identical across the set. The optical sizes are
    /// deliberately NOT equal: the circle overshoots the square slightly and
    /// the triangle is wider than it is tall, which is what makes four
    /// different shapes read as the same size.
    /// </summary>
    private static UIElement? FaceShape(string token, Brush brush, double size = 15)
    {
        string? d = token switch
        {
            // Sizes measured off a render, not guessed: at equal bounding boxes
            // the ✕ read ~16% smaller than the ○, because a diagonal cross has
            // no ink at its corners while a circle is ink all the way round.
            "A" => "M23,23 L77,77 M77,23 L23,77",                 // ✕ (largest box)
            "B" => "M50,22 A28,28 0 1 1 49.9,22 Z",               // ○ (overshoots the square)
            "X" => "M24,24 L76,24 L76,76 L24,76 Z",               // □
            "Y" => "M50,21 L81,76 L19,76 Z",                      // △ (wide, sits high)
            _ => null,
        };
        if (d is null) return null;

        var path = new System.Windows.Shapes.Path
        {
            Data = Geometry.Parse(d),
            Stroke = brush,
            StrokeThickness = 8,
            StrokeStartLineCap = PenLineCap.Round,
            StrokeEndLineCap = PenLineCap.Round,
            StrokeLineJoin = PenLineJoin.Round,
        };
        // The Canvas fixes the coordinate space so every shape gets the SAME
        // scale factor - a per-shape Stretch would normalise each bounding box
        // and hand each one a different stroke weight, which is the defect.
        var box = new Canvas { Width = 100, Height = 100 };
        box.Children.Add(path);
        return new Viewbox { Width = size, Height = size, Child = box };
    }

    private void SetHints(params (string glyph, string label)[] hints)
    {
        _lastHints = hints;
        Hints.Children.Clear();
        foreach (var (writtenToken, l) in hints)
        {
            // The token the call site wrote is the DEFAULT button; the one drawn
            // is whatever carries that action now (see LiveToken).
            string rawGlyph = LiveToken(writtenToken);
            string g = GlyphFor(rawGlyph);
            var sp = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 22, 0) };
            sp.Children.Add(new Border
            {
                Style = (Style)FindResource("HintGlyph"),
                MinWidth = 26,
                Width = double.NaN,          // a two-letter hint must not clip
                Padding = new Thickness(7, 0, 7, 0),
                Child = (_padKind is PadKind.Ps4 or PadKind.Ps5
                            ? FaceShape(rawGlyph, GlyphBrushFor(rawGlyph))
                            : null)
                       ?? new TextBlock
                {
                    Text = g,
                    Style = (Style)FindResource("Caption"),
                    Foreground = GlyphBrushFor(rawGlyph),
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center,
                },
            });
            sp.Children.Add(new TextBlock
            {
                Text = l,
                Style = (Style)FindResource("Caption"),
                VerticalAlignment = VerticalAlignment.Center,
            });

            // 🔴 THE LEGEND IS ALSO A CONTROL, NOT JUST A CAPTION. It already
            // names the five things you can do from here; a mouse user reading
            // "תפריט מהיר" naturally tries to click it, and a label that
            // advertises an action and then ignores the click is a dead spot on
            // every screen. Focusable=false ON PURPOSE: these are a mirror of
            // the pad, so letting them join the spatial ring would add five
            // stops to every sweep and let the pad walk INTO its own legend.
            var hit = new Button
            {
                Style = (Style)FindResource("HintHit"),
                Content = sp,
                Focusable = false,
                Cursor = System.Windows.Input.Cursors.Hand,
            };
            System.Windows.Automation.AutomationProperties.SetHelpText(hit, l);
            string token = writtenToken;
            hit.Click += (_, _) => HintAction(token);
            Hints.Children.Add(hit);
        }
    }

    /// <summary>
    /// Run what a footer legend entry advertises. Keyed off the ABSTRACT token
    /// ("A", "B", "LB/RB"), never the drawn glyph - the glyph is whatever the
    /// current device calls that button, and it changes under us when a pad is
    /// plugged in mid-session.
    /// </summary>
    private void HintAction(string token)
    {
        // Routed through InvokeAction rather than repeating its body: this was a
        // second, hand-copied implementation of five commands, and it had
        // already drifted (it ignored the search box and the text-entry rules
        // that ActivateFocused's real caller applies).
        if (token == "LB/RB")
        {
            if (_layer == "view") { Sfx.Play(Sound.Navigate); CycleTab(1); }
            return;
        }
        if (ActionForToken(token) is { } act) InvokeAction(act);
    }

    // =====================================================================
    //  views
    // =====================================================================

    private ScrollViewer Scroller(UIElement content)
    {
        var sv = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Hidden,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Focusable = false,
            // 🔴 THE TOP PAD IS THE FIRST ROW'S FOCUS CLEARANCE. At 8px the bloom
            // on any tile in the top row grew straight into the viewport edge and
            // was clipped flat — the card looked SLICED rather than lifted, and
            // only ever on the first row, which reads as a rendering bug rather
            // than as a missing 20 pixels.
            // The bottom pad is NOT the focus clearance the top one is - the
            // footer spacer below already keeps content off the bar - so it was
            // 32px of guaranteed empty screen under every page, stacked on top of
            // the edge ramp and the spacer.
            Padding = new Thickness(48, 28, 48, 10),
        };

        // 🔴 A VERTICAL StackPanel WITH HorizontalAlignment=Center SIZES TO ITS
        // WIDEST CHILD - MaxWidth only CLAMPS it, it never fills it. So a page
        // whose cards hold short text collapsed into a narrow ribbon down the
        // middle of a 1920 screen (the downloads page was ~440px wide while the
        // code said 1100), and the very same declaration looked fine on the
        // pages whose cards happen to contain something wide. Binding the width
        // to the viewport - clamped by the MaxWidth that is already declared -
        // gives a real centred column that still shrinks on a small window.
        if (content is FrameworkElement fe
            && !double.IsInfinity(fe.MaxWidth)
            && fe.HorizontalAlignment == HorizontalAlignment.Center)
        {
            fe.SetBinding(WidthProperty, new Binding("ViewportWidth") { Source = sv });
        }

        sv.Content = content;

        // 🔴 THE INNER PAGES NEEDED THE SAME SCROLL EDGE THE TAB HOST ALREADY HAD.
        // Caught on the game blade: scrolled down, the description line sat on
        // the viewport's top edge and was sliced through the middle of the Hebrew
        // glyphs, at full brightness, right under the pinned chips row. A half
        // letter at full opacity does not read as "content continues past here",
        // it reads as text that failed to draw. `Scroller` is the blade's,
        // settings', downloads' and collections' scroller and none of them had a
        // mask, because the fade lived inside SmoothScroll.Host — which only
        // wraps a TAB, and the blade is an overlay layer, not a tab.
        //
        // Calling the shared one rather than writing a second copy is the whole
        // point: the first attempt WAS a local copy, and it expressed the ramp as
        // a fraction of the box — which dissolves the padding instead of the
        // content, the exact bug SmoothScroll's comments already record fixing.
        SmoothScroll.AttachEdgeFade(sv);
        // ...and the same goes for the wheel, for the same reason: these pages
        // are driven by the same held animation that was silently overriding
        // WPF's own wheel handling. See SmoothScroll.AttachWheel.
        SmoothScroll.AttachWheel(sv);
        return sv;
    }

    // ---------------------------------------------------------------- home

    /// <summary>
    /// The home screen:
    ///
    ///     ── nav strip ── (centred, at the TOP - same place on every screen)
    ///     section title   ("שוחקו לאחרונה", large, at the reading-start edge)
    ///     cover shelf     (one row of portrait box art, the page's real content)
    ///     destination row (landscape, brand-coloured tiles)
    ///
    /// 🔴 THE NAV IS AT THE TOP HERE TOO, ON PURPOSE. Winhanced puts it at the
    /// waist on its own home screen, but a strip that moves between screens is
    /// something the user has to re-find every time they arrive - the one piece
    /// of chrome that must never move is the one that gets you everywhere else.
    ///
    /// 🔴🔴 THE BIG HERO PANEL IS GONE, AND THAT IS THE POINT. This screen used
    /// to open with a full-width logo + badges + Play block, which is a STORE
    /// front page — Winhanced opens straight onto your games and gives the first
    /// cover the focus. Nothing is lost: the first tile in "שוחקו לאחרונה" IS the
    /// last game played, and A on it opens the blade whose primary action is
    /// Play. The hero was one extra surface between the user and the thing they
    /// came for, and it was most of why this screen never read like theirs.
    /// </summary>
    private FrameworkElement BuildHome()
    {
        // 🔴🔴 THE HOME SCREEN IS ONE SCREENFUL, AND SCROLLING IT IS A BUG.
        // It used to stack four shelves - recent, the destination row, "your
        // library" and "available in Hebrew" - so the two blocks that matter sat
        // in the top half and everything under them was reached by scrolling
        // past what you had already seen. A console home screen is a LANDING
        // PAGE, not a feed: the row you actually pick from, and the four places
        // you can go, both fully visible the moment it appears. The other two
        // shelves are not lost - "כל המשחקים" and "מתורגמים לעברית" are two of
        // the four tiles, and they open the same lists with filters and search.
        //
        // A Grid rather than a StackPanel because the two blocks SHARE the
        // height: the shelf takes what it needs and the destination row absorbs
        // the rest, so the page ends exactly at the frame at any resolution or
        // display scale instead of leaving a void under it.
        var page = new Grid();

        // 🔴🔴 A STAR ROW IS MEANINGLESS INSIDE A SCROLLER, AND THAT IS WHY THE
        // NEWS BAND KEPT FALLING OFF THE BOTTOM.
        //
        // Every page is hosted in a vertical ScrollViewer, which measures its
        // child against INFINITE height - so "take the remaining space" resolves
        // to "take your content's own height", the page grows past the frame and
        // the last band is simply below it. (Same trap as the horizontal shelf,
        // where HorizontalAlignment could not work until the holder was given a
        // real width.) The height has to come from the VIEWPORT, so the page
        // asks the host for it - the one number the scroller does know.
        //
        // The handler is detached on unload: pages are rebuilt on every render,
        // and a subscription to a long-lived host is a leak per screen change.
        void Fit()
        {
            // The scroller's own bottom pad, and the footer that is drawn on top.
            double h = ViewHost.ActualHeight - 48
                     - (FooterBar.ActualHeight > 10 ? FooterBar.ActualHeight : 70);
            if (h > 240) page.Height = h;
            SmoothScroll.Trace($"home fit: page={page.ActualHeight:0} of {h:0}  rows=" +
                               string.Join(",", page.RowDefinitions.Select(r => r.ActualHeight.ToString("0"))));
        }
        SizeChangedEventHandler onHostResize = (_, _) => Fit();
        page.Loaded += (_, _) => { Fit(); ViewHost.SizeChanged += onHostResize; };
        page.Unloaded += (_, _) => ViewHost.SizeChanged -= onHostResize;

        // Keep the hero ART (it is the shell's whole atmosphere) even though the
        // hero PANEL is gone — the last-played game still paints the backdrop.
        var featured = _selected
            ?? _all.FirstOrDefault(g => g.Key == _settings.LastGameKey)
            ?? _all.FirstOrDefault(g => g.Installed && g.Source != GameSource.Hub)
            ?? _all.FirstOrDefault();
        if (featured is not null) SetBackground(featured);

        // 🔴 SORTED BY WHEN IT WAS PLAYED, NOT BY THE LIBRARY'S SORT. _all carries
        // the user's chosen library order - installed-first by default, with
        // favourites floated above it - so a row titled "שוחקו לאחרונה" was
        // showing "the first fourteen of your library that have ever been
        // played", in an order that had nothing to do with recency. The shelf's
        // whole promise is its order.
        var recent = _all.Where(g => (g.LastPlayed ?? Profile(g).LastPlayed) is not null)
                         .OrderByDescending(g => g.LastPlayed ?? Profile(g).LastPlayed ?? DateTime.MinValue)
                         .Take(ShelfTake).ToList();
        if (recent.Count == 0)
            recent = _all.Where(g => g.Installed && g.Source != GameSource.Hub).Take(ShelfTake).ToList();

        // 🔴🔴 THE COVERS GROW UNTIL THE FRAME RUNS OUT, THEN THE FRAME WINS.
        //
        // Three bands share one screenful, and two of them have a floor: the
        // destination strip is a fixed 150 and a news card stops being readable
        // under ~150. The covers are the only elastic band - so they take the
        // design size multiplied by the user's own tiles setting, CAPPED at what
        // is actually left. Without the cap the shelf simply ate the remainder
        // (at the tuned sizes it needed 654 of 814 available px) and pushed the
        // news band off the bottom of the screen, where the star row it lives in
        // could not save it: a page inside a ScrollViewer is measured against
        // infinite height, so "the rest of the space" is not a quantity it knows.
        //
        // The multiplier is divided back out because Tile() applies it itself -
        // this budget is in DRAWN pixels, and handing Tile() a pre-multiplied
        // number would square the setting.
        // MEASURED off a 1080p frame at the tuned sizes, not estimated: heading
        // 70, the gap under the covers 40, the destination strip 120 + its
        // margins, and the focus bloom the shelf reserves above and below every
        // cover. Under-counting them is what left the news band 67px when the
        // arithmetic said 150 - the covers are elastic, so every pixel nobody
        // claimed went to them.
        // 🔴🔴 EVERY BAND GETS AN EXPLICIT HEIGHT. Auto+Star looked like the right
        // shape and never behaved: a page inside a ScrollViewer is measured
        // against infinite height, so "Star" is not a share of the frame, and
        // the two Auto rows above simply took what they wanted and left the news
        // band whatever remained - measured at 45px when the arithmetic said
        // 150. Three fixed heights, computed from the one number that is real
        // (the host's height, minus the scroller's pad and the footer drawn on
        // top of it), cannot be argued with by anything downstream.
        // The band is the CARD plus everything around it: the section heading,
        // the row's own margins and the card's. Measured, not guessed - a band
        // sized to the card alone clipped the last 30px of every card.
        const double NewsBand = 250, DestBand = 170;
        // 🔴 THE HOST HAS NO SIZE ON THE FIRST RENDER, AND THE HOME PAGE IS BUILT
        // EXACTLY ONCE. Reading ViewHost.ActualHeight alone left the budget at
        // zero on the one pass that matters, so the cap never applied and the
        // covers kept the whole frame. The window itself IS measured by then
        // (it opens maximised), so its height minus the chrome is the fallback.
        // 🔴 THE FOOTER LEGEND IS DRAWN OVER THE PAGE, NOT BESIDE IT. It is an
        // overlay on purpose (it has to stay visible above every layer), so the
        // host's height INCLUDES the strip the footer covers - and a page that
        // believes that number puts its last band underneath it. That is the
        // real reason the news row kept coming out sliced: it was not short, it
        // was hidden. Whatever the footer occupies is not the page's to spend.
        double footer = FooterBar.ActualHeight > 10 ? FooterBar.ActualHeight : 70;
        double avail = (ViewHost.ActualHeight > 300 ? ViewHost.ActualHeight
                                                   : Math.Max(0, ActualHeight - 270)) - 48 - footer;
        double tileScale = Math.Max(0.1, GroupEffective("tiles"));
        double shelfBand = Math.Max(320, avail - NewsBand - DestBand);

        // What is left of the shelf band once its heading and the focus bloom
        // above/below every cover are paid for. The bloom is a function of the
        // cover height, so this solves it the cheap way: assume the full size,
        // and let the clamp below take care of the small difference.
        const double ShelfHead = 100;
        double bloomPair = 2 * (ShelfH * tileScale * 0.045 + 18);
        double drawn = Math.Min(ShelfH * tileScale, Math.Max(220, shelfBand - ShelfHead - bloomPair));

        SmoothScroll.Trace($"home budget: viewHost={ViewHost.ActualHeight:0} win={ActualHeight:0} " +
                           $"avail={avail:0} scale={tileScale:0.00} drawn={drawn:0} coverH={drawn / tileScale:0}");

        // AN EMPTY LIBRARY AND AN UNFINISHED SCAN LOOK IDENTICAL, AND ONLY ONE
        // OF THEM IS BAD NEWS. The first frame is drawn before the stores have
        // been read - deliberately, so the shell is on screen in a few hundred
        // milliseconds rather than after a disk sweep - and it used to announce
        // "לא נמצאו משחקים" to a user whose fifty games were being counted at
        // that moment. Placeholders say the same thing an empty shelf says
        // (nothing here yet) without the verdict, and they show the row's real
        // shape so nothing jumps when the covers land.
        FrameworkElement shelf = recent.Count > 0
            ? TileRow("שוחקו לאחרונה", recent, header: "H1", coverH: drawn / tileScale)
            : _scanning
            ? SkeletonRow(drawn)
            : (FrameworkElement)Empty("לא נמצאו משחקים", "אפשר להפעיל מקורות נוספים בהגדרות → ספרייה");
        page.RowDefinitions.Add(new RowDefinition { Height = new GridLength(shelfBand) });
        page.RowDefinitions.Add(new RowDefinition { Height = new GridLength(DestBand) });
        page.RowDefinitions.Add(new RowDefinition { Height = new GridLength(NewsBand) });

        Grid.SetRow(shelf, 0);
        page.Children.Add(shelf);

        var dest = DestinationRow();
        Grid.SetRow(dest, 1);
        page.Children.Add(dest);

        // The last band: what changed lately. It is the one thing on a console
        // home screen that is worth reading rather than pressing, and it fills
        // the space the destination row stopped stretching into.
        var news = NewsStrip();
        if (news is not null)
        {
            Grid.SetRow(news, 2);
            page.Children.Add(news);
        }

        return page;
    }

    /// <summary>
    /// The shelf's shape, before the shelf exists. Not focusable and not in the
    /// nav ring: there is nothing to select, and a placeholder that takes focus
    /// would steal the cursor from the real tiles the moment they arrive.
    /// </summary>
    private FrameworkElement SkeletonRow(double coverH)
    {
        var wrap = new StackPanel { Margin = new Thickness(0, 0, 0, 12) };
        wrap.Children.Add(Text("שוחקו לאחרונה", "H1", margin: new Thickness(48, 0, 48, 18)));
        wrap.Children.Add(Text("סורק את הספרייה…", "Caption", margin: new Thickness(48, -10, 48, 14)));

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Margin = new Thickness(48, 0, 48, 0),
            FlowDirection = FlowDirection.RightToLeft,
        };
        double w = coverH * 0.68;      // the cover aspect the real tiles use
        for (int i = 0; i < 6; i++)
        {
            var b = new Border
            {
                Width = w,
                Height = coverH,
                CornerRadius = new CornerRadius(14),
                Background = (Brush)FindResource("GlassChip"),
                Margin = new Thickness(0, 0, 18, 0),
                Opacity = 0.55,
            };
            // A slow breath, staggered per card, so the row reads as "working"
            // rather than "broken" - and only when animations are allowed.
            if (_settings.AnimationsEnabled)
            {
                var a = new DoubleAnimation(0.35, 0.7, new Duration(TimeSpan.FromMilliseconds(1100)))
                {
                    AutoReverse = true,
                    RepeatBehavior = RepeatBehavior.Forever,
                    BeginTime = TimeSpan.FromMilliseconds(90 * i),
                    EasingFunction = new SineEase { EasingMode = EasingMode.EaseInOut },
                };
                Timeline.SetDesiredFrameRate(a, 24);   // ambient, not interactive
                b.BeginAnimation(OpacityProperty, a);
            }
            row.Children.Add(b);
        }
        wrap.Children.Add(row);
        return wrap;
    }

    /// <summary>
    /// A row of square "what's new" cards, newest first.
    ///
    /// 🔴 SQUARE, AND A ROW - NOT THE FEED. The full feed already exists on its
    /// own screen and is a list of paragraphs; this is a glance. Square cards
    /// because they are a different SHAPE from the portrait covers above and the
    /// landscape destinations between them, which is what stops the home screen
    /// reading as one undifferentiated grid of rectangles.
    /// </summary>
    private FrameworkElement? NewsStrip()
    {
        var items = Catalog.News();
        if (items.Count == 0) return null;

        // 🔴 A GRID, SO THE STRIP GETS WHAT IS LEFT AND NOT WHAT IT WANTS. The
        // home screen is one screenful by design, and the band above it grows
        // with the display-size setting - at the tuned sizes the cards' fixed
        // height ran off the bottom of the frame and the last row was a sliver.
        // The title takes its own height, the strip takes the remainder, and the
        // cards stretch into whatever that turns out to be.
        var sp = new Grid { Margin = new Thickness(24, 2, 24, 6) };
        sp.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        sp.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        var head = Text("מה חדש", "H3", margin: new Thickness(44, 0, 0, 10));
        Grid.SetRow(head, 0);
        sp.Children.Add(head);

        var strip = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Margin = new Thickness(44, 0, 44, 0),
        };

        foreach (var n in items.Take(8))
        {
            var item = n;
            // The game the item is about, so the card can wear its artwork.
            var linked = _scanned.FirstOrDefault(x => x.Hub is not null && x.Hub.Id == item.Link);
            var col = new StackPanel { Margin = new Thickness(0, 0, 0, 0) };
            col.Children.Add(new TextBlock
            {
                Text = string.IsNullOrWhiteSpace(item.Badge) ? item.Kind : item.Badge,
                Style = (Style)FindResource("Caption"),
                Foreground = (Brush)FindResource("Accent"),
                Margin = new Thickness(0, 0, 0, 6),
            });
            var title = new TextBlock
            {
                Text = item.Title,
                Style = (Style)FindResource("Body"),
                FontWeight = FontWeights.SemiBold,
                TextWrapping = TextWrapping.Wrap,
                // Trimmed with an ellipsis instead of clipped: a card that ends
                // mid-word looks like a rendering fault, while "…" reads as
                // "there is more, press to read it".
                TextTrimming = TextTrimming.CharacterEllipsis,
                MaxHeight = 56,
            };
            Inherit(title);
            col.Children.Add(title);
            if (!string.IsNullOrWhiteSpace(item.Detail))
            {
                var det = new TextBlock
                {
                    Text = item.Detail,
                    Style = (Style)FindResource("Caption"),
                    TextWrapping = TextWrapping.Wrap,
                    TextTrimming = TextTrimming.CharacterEllipsis,
                    Margin = new Thickness(0, 5, 0, 0),
                    MaxHeight = 38,
                };
                col.Children.Add(det);
            }
            col.Children.Add(new TextBlock
            {
                Text = PrettyDate(item.Date),
                Style = (Style)FindResource("Caption"),
                Foreground = (Brush)FindResource("FgMuted"),
                Margin = new Thickness(0, 6, 0, 0),
            });

            // 🔴 THE ART GOES BEHIND THE TEXT, BLURRED, WITH A SCRIM ON TOP.
            // A cover at full clarity behind a paragraph is a legibility problem
            // wearing a decoration's clothes - every light patch eats a line of
            // text. Blurred, it keeps the COLOUR and the mood of the game (which
            // is what makes the card recognisable at a glance) and gives up the
            // detail that was competing with the words; the scrim then guarantees
            // the contrast rather than hoping for it.
            var art = new Grid { ClipToBounds = true };
            var artPath = linked is null ? null
                : Profile(linked).CustomHeroArt ?? linked.HeroArt ?? linked.Header
                  ?? Profile(linked).CustomBoxArt ?? linked.BoxArt ?? linked.Hub?.Cover;
            if (LoadImg(artPath, 480) is { } bg)
            {
                var im = new Image
                {
                    Source = bg,
                    Stretch = Stretch.UniformToFill,
                    Opacity = 0.55,
                    // Rasterised once: the blur is static, and paying for it on
                    // every frame of a scrolling strip is exactly the trap the
                    // background layer already documents.
                    CacheMode = new BitmapCache(),
                    Effect = new BlurEffect { Radius = 14, KernelType = KernelType.Gaussian,
                                              RenderingBias = RenderingBias.Performance },
                };
                art.Children.Add(im);
                art.Children.Add(new Border
                {
                    Background = new LinearGradientBrush(
                        Color.FromArgb(0xE6, 0x0E, 0x14, 0x1B),
                        Color.FromArgb(0x99, 0x0E, 0x14, 0x1B),
                        new Point(0, 1), new Point(0, 0)),
                });
            }
            art.Children.Add(col);

            var card = new Button
            {
                Style = (Style)FindResource("ListRow"),
                // Wider and shorter: a news line is a sentence, and a sentence
                // wants width. The square shape forced every title to wrap three
                // times and left dead space under the date. The HEIGHT is not
                // fixed - it takes the band it is given (see the Grid above), so
                // the row still ends at the frame when everything is scaled up.
                Width = 340,
                // 🔴 A FIXED HEIGHT, AND THE BAND IS SIZED TO MATCH IT. Stretch +
                // Min/Max made the card's size an argument between four layout
                // rules (the star row, the scroller, the panel and the card),
                // and the argument was settled at 45px more than once. The card
                // states what it needs; BuildHome reserves exactly that.
                Height = 140,
                Margin = new Thickness(0, 0, 14, 0),
                Content = art,
                VerticalContentAlignment = VerticalAlignment.Stretch,
                HorizontalContentAlignment = HorizontalAlignment.Stretch,
            };
            card.Click += (_, _) => { Sfx.Play(Sound.Select); SetTab("news"); };

            // What a card can show depends on the height it ends up with, and
            // that is only known after layout. Below ~150px the summary goes,
            // below ~110px the date goes too - the headline is the part that
            // has to survive.
            card.SizeChanged += (_, _) =>
            {
                double h = card.ActualHeight;
                for (int ci = 1; ci < col.Children.Count; ci++)
                {
                    bool isDate = ci == col.Children.Count - 1;
                    bool keep = isDate ? h >= 112 : h >= 150;
                    if (col.Children[ci] is TextBlock t && !ReferenceEquals(t, title))
                        t.Visibility = keep ? Visibility.Visible : Visibility.Collapsed;
                }
            };
            strip.Children.Add(Nav(card));
        }

        var sv = new ScrollViewer
        {
            Content = strip,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Hidden,
            VerticalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Focusable = false,
        };
        SmoothScroll.AttachWheel(sv);
        Grid.SetRow(sv, 1);
        sp.Children.Add(sv);
        return sp;
    }

    /// <summary>
    /// The destination row under the nav — Winhanced's landscape brand tiles.
    ///
    /// These are the shortcuts a 10ft user reaches for without reading: a wide
    /// coloured card with one icon and one word. Each is a real place in THIS
    /// app, not decoration — a tile that leads nowhere is worse than no tile.
    /// </summary>
    private FrameworkElement DestinationRow()
    {
        // 🔴 THE ROW SPANS THE FRAME, IT DOES NOT SIT IN THE MIDDLE OF IT.
        // Measured off Winhanced: four tiles running from x≈25 to x≈1895 of a
        // 1920 frame, i.e. edge to edge. Centring four fixed-width cards left a
        // 400px void on either side and made the row read as a floating widget
        // instead of the page's own footer band. A UniformGrid also keeps them
        // equal when there are three tiles instead of four.
        // 🔴 A BAND, NOT A WALL. Stretching these into the whole lower half turned
        // four shortcuts into four full-height panels that dwarfed the covers
        // above them - the row is a footer of destinations, and it reads as one
        // only while it stays a strip. The height comes from the DestTile style.
        var row = new UniformGrid
        {
            Rows = 1,
            Margin = new Thickness(44, 4, 44, 10),
            VerticalAlignment = VerticalAlignment.Top,
        };

        void Add(string glyph, string label, string tint, Action go)
            => row.Children.Add(Nav(DestTile(glyph, label, tint, go)));

        Add(GlyphGrid, "כל המשחקים", "#FF1D4E89", () => SetTab("library"));
        Add(GlyphDownload, "מותקנים", "#FF1E6F4C", () => { SetFilter("installed"); SetTab("library"); });
        if (_all.Any(g => g.Hub is not null))
            Add(GlyphGlobe, "מתורגמים לעברית", "#FF6B3FA0", () => { SetFilter("translated"); SetTab("library"); });
        Add(GlyphStream, "סטרימינג", "#FF8A5A1B", () => SetTab("stream"));

        return row;
    }

    /// <summary>One landscape destination tile: icon over label, on a brand tint.</summary>
    private FrameworkElement DestTile(string glyph, string label, string tint, Action go)
    {
        var col = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
        col.Children.Add(new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 34,
            Foreground = (Brush)FindResource("FgPrimary"),
            HorizontalAlignment = HorizontalAlignment.Center,
            Margin = new Thickness(0, 0, 0, 14),
            Opacity = 0.92,
        });
        // 🔴 `Foreground = null` PAINTS NOTHING. It reads like "inherit", and it
        // is the opposite: a null brush means there is no brush, so the label
        // vanished entirely and the tiles came out as bare icons. To actually
        // follow the button, BIND to the ancestor's Foreground — the Style's own
        // `Body` setter would otherwise win over inheritance anyway.
        var cap = new TextBlock
        {
            Text = label,
            Style = (Style)FindResource("Body"),
            FontWeight = FontWeights.SemiBold,
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        cap.SetBinding(TextBlock.ForegroundProperty, new Binding("Foreground")
        {
            RelativeSource = new RelativeSource(RelativeSourceMode.FindAncestor, typeof(Button), 1),
        });
        col.Children.Add(cap);

        var b = new Button
        {
            Style = (Style)FindResource("DestTile"),
            Content = col,
            // The tint is the tile's identity, so it is set per instance rather
            // than themed — a colour that means "Steam" is not a palette slot.
            //
            // 🔴 THE FILL IS OPAQUE END TO END. It used to fade into a 40%
            // transparent dark, which let the hero art through the tail of every
            // tile — and once the scrim was lightened so the art could actually
            // be seen, "מותקנים" ended up sitting on a bird's beak. Winhanced's
            // category cards are solid brand colour for exactly this reason, and
            // it is the same rule as Apple's: put the colour on a SOLID layer,
            // never stack a translucent surface on another. The gradient stays,
            // but it runs from the hue to a DARKER SHADE OF ITSELF, so the card
            // still reads as a lit surface instead of a flat rectangle.
            Background = TileFill(tint),
        };
        b.Click += (_, _) => { Sfx.Play(Sound.Select); go(); };
        return b;
    }

    /// <summary>
    /// Fence a measurement so the bidi algorithm cannot take it apart.
    ///
    /// 🔴 "34%" RENDERED AS "%34". In an RTL paragraph a trailing "%" is a
    /// European Terminator with nothing after it, so it resolves to the base
    /// direction and jumps to the other side of its own number — and "23.1 /
    /// 31.9 GB" comes apart the same way, because the "/" between two numbers
    /// is another neutral. The text is correct in memory every time; it is the
    /// LAYOUT that is wrong, so the fix belongs at display, not in the string.
    ///
    /// LRM (U+200E) on both sides makes the fragment its own LTR island inside
    /// the Hebrew sentence, which is exactly what a number-plus-unit is. It is
    /// zero-width in every system font, so unlike an injected control character
    /// in a game font it can never surface as a box.
    /// </summary>
    /// <summary>Hebrew count agreement. "1 משחקים" is a grammatical error, and
    /// one is exactly the count a brand-new collection has.</summary>
    private static string Games(int n) => n == 1 ? "משחק אחד" : Ltr(n.ToString()) + " משחקים";
    private static string Titles(int n) => n == 1 ? "כותר אחד" : Ltr(n.ToString()) + " כותרים";
    private static string Updates(int n) => n == 1 ? "עדכון אחד" : Ltr(n.ToString()) + " עדכונים";

    private static string Ltr(string s) => "‎" + s + "‎";

    /// <summary>
    /// A catalog price, in shekels.
    ///
    /// 🔴 INTEGER DIVISION ON THE ONE SCREEN THAT SHOWS A PRICE. `PriceCents / 100`
    /// turned 5350 into "53 ₪" - the shell quietly under-charged by half a shekel
    /// everywhere it quoted a number, on a paid product. Formatted from a decimal
    /// through one helper so no call site can round it again, and fenced LTR so
    /// the number does not come apart inside a Hebrew sentence.
    /// </summary>
    private static string Price(int cents)
    {
        decimal v = decimal.Divide(cents, 100m);
        // Whole shekels stay whole - "53 ₪", not "53.00 ₪" - because the catalog
        // prices in round numbers and a trailing .00 reads like a form field.
        string n = v == decimal.Truncate(v) ? v.ToString("0") : v.ToString("0.00");
        return Ltr(n + " ₪");
    }

    /// <summary>
    /// What stage a translation is at, in the website's own vocabulary.
    ///
    /// 🔴 A MOD IN THE CATALOG IS NOT A MOD YOU CAN INSTALL. Every game with a
    /// hub entry was offered as "זמין להתקנה", including the ones still being
    /// translated - so the shell promised a download that does not exist yet and
    /// the button could only fail. The catalog has always carried the stage
    /// (`availability`); nothing was reading it.
    /// </summary>
    private static string StageLabel(string availability) => availability switch
    {
        "available"   => "זמין",
        "in-progress" => "בעבודה",
        "extracting"  => "בתהליך שליפה",
        "translating" => "בתהליך תרגום",
        "packing"     => "בתהליך אריזה",
        "finalizing"  => "בתהליך השלמה",
        "qa"          => "בבקרת איכות",
        "coming-soon" => "בקרוב",
        "planned"     => "מתוכנן",
        "paused"      => "מושהה",
        "archived"    => "בארכיון",
        _             => "בעבודה",
    };

    /// <summary>A brand hue shaded into itself — opaque, so nothing behind it
    /// can compete with the label sitting on top.</summary>
    private static LinearGradientBrush TileFill(string tint)
    {
        var c = (Color)ColorConverter.ConvertFromString(tint)!;
        var dark = Color.FromRgb((byte)(c.R * 0.42), (byte)(c.G * 0.42), (byte)(c.B * 0.42));
        return new LinearGradientBrush(c, dark, 65);
    }

    /// <summary>
    /// A shelf: a section title with a row of covers beneath it.
    ///
    /// The title is indented twice as far as the covers, which is measured off
    /// Winhanced rather than chosen — their "Recent Games" sits at ~90px while
    /// the first cover starts at ~25px. The covers running closer to the edge is
    /// what tells you the row CONTINUES; a title aligned to them would make the
    /// shelf look like a boxed card instead of a strip through the screen.
    /// </summary>
    // 🔴 THE SHELF IS MEASURED FROM WINHANCED'S OWN FRAME, NOT GUESSED.
    // Theirs: a 230x360 cover, seven of them, spanning almost the full screen
    // width with a ~22px inset. Ours was 176x264 - a third smaller in area, and
    // the wordmark on a cover is the thing you read from a couch, so smaller is
    // not "denser", it is less legible. 230x345 keeps the same 2:3 portrait.
    //
    // And a shelf must END INSIDE THE FRAME. Fourteen tiles was 2716px of
    // content in a 1756px row, so the closing "All Games" tile sat five cards
    // past the edge - the one affordance that answers "is that everything?" was
    // the only thing you could never see. Six covers + that tile is seven items
    // at a 248px pitch = 1736px: the whole shelf, ending deliberately, and the
    // same seven-item rhythm their home screen has. The rest are one screen
    // away in the library, where a full grid belongs.
    //
    // ⚠ The "All Games" tile is OURS, not a Winhanced element - their recent
    // row simply runs to the frame edge. It is kept because a truncated row
    // raises a question and this answers it where the eye already is.
    // 🔴 THE SHELF IS THE PAGE NOW, SO IT CARRIES MORE. With the two lower
    // shelves gone, six covers left the home screen looking half-empty and put
    // "כל המשחקים" - which belongs at the END, as the row's full stop - three
    // tiles from the start. The row scrolls, so a longer shelf costs nothing but
    // gives the eye somewhere to go before it runs out.
    private const int ShelfTake = 14;
    private const double ShelfW = 280, ShelfH = 420;

    private FrameworkElement TileRow(string title, List<LibraryGame> games, string header = "H3",
                                     double? coverH = null)
    {
        // The shelf normally draws at the design size; the home screen passes a
        // height derived from what is actually left of the frame (see BuildHome).
        double shelfH = coverH ?? ShelfH;
        double shelfW = shelfH * (ShelfW / ShelfH);   // keep the 2:3 box art ratio

        // The bottom margin is between one shelf and the next, and the LAST
        // shelf on a page pays it against the frame instead - where it stacks on
        // the scroller's pad, the edge ramp and the footer spacer.
        var sp = new StackPanel { Margin = new Thickness(24, 6, 24, 6) };
        // 🔴 THE HEADING NEEDS CLEARANCE, BECAUSE A FOCUSED COVER GROWS INTO IT.
        // Tiles scale up on focus and their accent bloom reaches further still,
        // so the card at the start of the row was rising over the section title
        // and cutting it in half. The gap is the growth, not decoration.
        sp.Children.Add(Text(title, header, margin: new Thickness(24, 0, 0, 14)));

        // 🔴 A SHELF NEEDS AN INSET, OR ITS FIRST CARD IS SLICED. The row's
        // edge-fade mask starts biting at 3% of the viewport, and a focused tile
        // also scales up — so a card flush against the frame lost a strip of art
        // and read as broken rather than as "the row continues". The inset is
        // inside the scrolling content on purpose: as the shelf scrolls, the gap
        // travels with it and the far end still dissolves into the fade.
        // 44px, not 34: the inset has to clear BOTH the edge-fade ramp (~24px)
        // AND the focus growth of the card sitting against the frame - scale
        // plus its shadow bloom. At 34 the focused first cover lost a strip of
        // art to the mask and read as clipped instead of as "the row continues".
        // 88px of inset + 7 items at a 248px pitch is exactly the 1824px viewport.
        var strip = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Margin = new Thickness(44, 0, 44, 0),
        };
        // 🔴 THE OLD RULE HERE WAS "horizontal air only - a shelf is ONE row, so a
        // taller margin would just cost height the home screen has no spare of."
        // That reasoning is what sliced every focused card: a shelf's viewport
        // height IS the strip height, so the focus bloom had literally nowhere to
        // go and got clipped instead of overlapping a neighbour. The height is
        // not spare, it is required - see TileBloomV.
        foreach (var g in games)
        {
            var t = Tile(g, shelfW, shelfH);
            double bv = TileBloomV(shelfH);
            t.Margin = new Thickness(17, bv, 17, bv);
            strip.Children.Add(Nav(t));
        }

        // Winhanced closes every home row with an "All Games" tile instead of
        // letting it just run off the edge. It answers the question the truncated
        // row raises ("is that everything?") in the place the user is already
        // looking, and it gives the row a deliberate END.
        var more = MoreTile(shelfW, shelfH);
        double mbv = TileBloomV(shelfH);
        more.Margin = new Thickness(17, mbv, 17, mbv);   // same pitch as its neighbours
        strip.Children.Add(Nav(more));

        // 🔴 A FIXED FADE CANNOT BE RIGHT AT BOTH ENDS AT ONCE, and that is why
        // this looked wrong for so long. The two edges are doing opposite jobs:
        // the end the shelf STARTS at holds a card that is fully in frame, so any
        // ramp there eats a good card (a 3%/56px one visibly did); the end the
        // shelf RUNS OFF holds a card sliced mid-art, which needs a ramp WIDE
        // enough to read as a dissolve rather than as a broken cover. Splitting
        // the difference — the old 1.4% on both sides — gave a hard-looking cut
        // at the overflow and still no hint that anything continues past it.
        //
        // So the mask now follows the actual scroll position: an edge with
        // nothing behind it is perfectly square, an edge with content behind it
        // dissolves. That is also the only "there is more this way" affordance
        // this row has, since its scrollbar is hidden by design.
        var mask = new LinearGradientBrush
        {
            StartPoint = new Point(0, 0),
            EndPoint = new Point(1, 0),
            GradientStops =
            {
                new GradientStop(Color.FromArgb(0x00, 0, 0, 0), 0.000),
                new GradientStop(Color.FromArgb(0xFF, 0, 0, 0), 0.000),
                new GradientStop(Color.FromArgb(0xFF, 0, 0, 0), 1.000),
                new GradientStop(Color.FromArgb(0x00, 0, 0, 0), 1.000),
            },
        };
        // 🔴 A ROW THAT DOES NOT FILL THE FRAME IS CENTRED, NOT PARKED ON ONE
        // EDGE. A horizontal ScrollViewer measures its child against infinity, so
        // the strip always gets exactly its desired width and alignment inside it
        // can never do anything - which is why a short shelf (or any shelf at a
        // small display scale, or on a wide monitor) sat hard against the reading
        // edge with a lake of empty space beside it. Giving the holder a MinWidth
        // of the VIEWPORT is what makes alignment mean something again: when the
        // tiles are narrower than the frame the holder fills it and the strip
        // centres inside; when they are wider the holder grows with them and the
        // row scrolls exactly as before.
        var hold = new Grid();
        strip.HorizontalAlignment = HorizontalAlignment.Center;
        hold.Children.Add(strip);

        var sv = new ScrollViewer
        {
            Content = hold,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Hidden,
            VerticalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Focusable = false,
            OpacityMask = mask,
        };
        hold.SetBinding(FrameworkElement.MinWidthProperty,
            new System.Windows.Data.Binding("ViewportWidth") { Source = sv });
        // Both the mask offsets and ScrollViewer.HorizontalOffset live in the
        // element's OWN coordinate space, which RTL mirrors identically — so
        // "offset 0" means the same physical end in both, and this needs no
        // direction special-case.
        // 🔴 THE RAMP IS THE INSET, IN PIXELS - NOT A PERCENTAGE OF THE SHELF.
        // At 4.5% of a 1824px row the dissolve was ~82px wide while the strip's
        // own inset is 44, so the other ~38px landed ON the first card: a soft
        // vertical wipe straight through the "כל המשחקים" tile that reads as the
        // card being sliced, not as the row continuing. Tying the ramp to the
        // inset makes it dissolve exactly the empty margin it was meant to and
        // stop at the card's edge - and it stays right at every display scale,
        // because both numbers are scaled by the same transform.
        void Edges()
        {
            double w = sv.ActualWidth;
            double ramp = w > 1 ? Math.Min(0.06, 44.0 / w) : 0.0;
            bool atStart = sv.HorizontalOffset <= 1;
            bool atEnd = sv.HorizontalOffset >= sv.ScrollableWidth - 1;
            mask.GradientStops[1].Offset = atStart ? 0.0 : ramp;
            mask.GradientStops[2].Offset = atEnd ? 1.0 : 1.0 - ramp;
        }
        sv.ScrollChanged += (_, _) => Edges();
        sv.SizeChanged += (_, _) => Edges();     // the ramp is width-derived now
        sv.Loaded += (_, _) => Edges();
        sp.Children.Add(sv);
        return sp;
    }

    // ------------------------------------------------------------- library

    private FrameworkElement BuildLibrary()
    {
        var root = new Grid();
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var head = new StackPanel();
        // 🔴 STACKED PILL ROWS NEED AIR BETWEEN THEM OR THEY READ AS ONE BLOCK.
        // The pinned tab strip, the category chips and the sort header are all
        // pill-shaped and all the same height, so at a few px apart the eye
        // groups them into a single striped band and cannot tell which row it is
        // actually on. They are different CONTROLS, and the gap is what says so.
        Grid.SetRow(head, 0);
        root.Children.Add(head);

        // 🔴 THE CATEGORIES ARE A HORIZONTAL ROW. A vertical rail is what the
        // reference ships and it WAS tried here — but it charges 268px of a 10ft
        // screen permanently, and on this library that is a whole column of box
        // art traded away for nine words that fit on one line. The counts are the
        // part of that experiment worth keeping, so they stayed on the chips:
        // knowing a category is empty BEFORE clicking it was the rail's real win,
        // and it costs two characters here.
        var cats = new WrapPanel
        {
            Orientation = Orientation.Horizontal,
            // Centred, under the centred tab strip it hangs from — left to
            // stretch, the row started at the reading edge and drifted away
            // from the pills above it, so the two rows read as unrelated.
            HorizontalAlignment = HorizontalAlignment.Center,
            Margin = new Thickness(44, 0, 44, 16),
        };

        // The triggers cycle categories, so the bumpers flank the row they drive.
        cats.Children.Add(BumperGlyph("LT"));

        // Two blocks with a rule between them, the way the reference groups them:
        // first WHAT STATE a game is in, then WHERE it came from. Collections are
        // the user's own, so they join the second block.
        var states = new (string Key, string Label)[]
        {
            ("all", "הכול"), ("installed", "מותקנים"), ("uninst", "לא מותקנים"),
            ("recent", "לאחרונה"), ("fav", "מועדפים"), ("translated", "מתורגמים"),
        };
        var sources = SourceChips()
            .Concat(_settings.Collections.Select(c => ("col:" + c.Name, c.Name))).ToArray();

        void AddCat(string key, string label)
        {
            // Name, then its count in a dimmer, smaller face so the row still
            // scans as a list of NAMES and the numbers sit under them. An EMPTY
            // category dims further — visible, but visibly not worth a click,
            // which beats hiding it and leaving the user to wonder where it went.
            int n = FilteredBy(key).Count();
            var face = new StackPanel { Orientation = Orientation.Horizontal };
            face.Children.Add(new TextBlock { Text = label, VerticalAlignment = VerticalAlignment.Center });
            face.Children.Add(new TextBlock
            {
                Text = n.ToString(),
                VerticalAlignment = VerticalAlignment.Center,
                FontSize = 12.5,
                Opacity = n == 0 ? 0.32 : 0.62,
                Margin = new Thickness(9, 1, 0, 0),
            });

            var chip = new RadioButton
            {
                Style = (Style)FindResource("Chip"),
                Content = face,
                Margin = new Thickness(0, 0, 8, 8),
                Opacity = n == 0 && _filter != key ? 0.55 : 1,
                Tag = key,
                GroupName = "filter",
                IsChecked = _filter == key,
            };
            chip.Checked += (_, _) => { if (_filter != key) { SetFilter(key); Sfx.Play(Sound.Navigate); RenderTab(); } };
            cats.Children.Add(Nav(chip));
        }

        foreach (var (key, label) in states) AddCat(key, label);
        // A vertical rule, because the row is horizontal: state on one side of
        // it, origin on the other, same grouping the rail had.
        cats.Children.Add(new Border
        {
            Width = 1,
            Background = (Brush)FindResource("HairlineBrush"),
            Margin = new Thickness(6, 7, 14, 15),
        });
        foreach (var (key, label) in sources) AddCat(key, label);
        cats.Children.Add(BumperGlyph("RT"));
        head.Children.Add(cats);

        var games = Filtered().ToList();

        var body = new Grid();

        // The grid carries its own header: sort + how many are shown. It belongs
        // over the tiles it describes, under the categories that chose them.
        var col = new Grid();
        col.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        col.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        // 🔴 HorizontalAlignment.Right IS THE VISUAL *LEFT* HERE. Alignment is
        // expressed in LAYOUT space and this window is RightToLeft, so the two
        // are mirrored — the same trap the footer legend carries a comment about.
        // Centred, this row sat under the middle of the chip strip and read as a
        // fourth category rather than as the grid's own header; parked at the far
        // edge it becomes what it is, a control that belongs to the tiles below.
        var gridHead = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(46, 0, 46, 14),
            VerticalAlignment = VerticalAlignment.Center,
        };
        // 🔴 A WPF Style CANNOT be applied across sibling types. "Chip" is
        // TargetType="RadioButton" (the category rows are radios), and a Button IS
        // NOT a RadioButton - they are siblings under ButtonBase. Setting it threw
        // at RENDER time, which blanked the ENTIRE library view while the build
        // stayed clean at 0 warnings. Ghost() already builds the right control.
        var sortBtn = Ghost(GlyphSort, SortLabel(), CycleSort);
        System.Windows.Automation.AutomationProperties.SetHelpText(sortBtn, "מיון הספרייה");
        sortBtn.Tag = "sort";
        sortBtn.VerticalAlignment = VerticalAlignment.Center;
        gridHead.Children.Add(Nav(sortBtn));
        gridHead.Children.Add(new TextBlock
        {
            Text = Titles(games.Count),
            Style = (Style)FindResource("Caption"),
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(18, 0, 0, 0),
        });
        Grid.SetRow(gridHead, 0);
        col.Children.Add(gridHead);

        // Entry focus belongs to the CONTENT. Landing on the nav pill you just
        // came through makes the shell look like it is still on the previous
        // page - the same bug the document views had. The category rows are
        // added ABOVE this line on purpose: they stay reachable (the pad picks
        // by geometry, not by order) without stealing the first focus.
        _navViewStart = _nav.Count;

        // Centred, so the leftover width splits evenly instead of piling up on
        // one side — and so the edge tile keeps room for its focus bloom, which
        // the viewport was clipping when the block hugged the reading-start edge.
        var wrap = new WrapPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        // With the category row overhead instead of alongside, the grid gets the
        // full width back — 252px covers land six to a row at 1920 with the
        // gutters below, which is the reference's own density.
        //
        // 🔴 THE GUTTERS ARE SET HERE, NOT ON THE SHARED STYLE. A grid needs air
        // on BOTH axes - packed at the style's default the covers ran together
        // into one wall of art with no reading rhythm. The shelves on the home
        // screen have no vertical neighbour, so widening the style would have
        // spent 36px of height per shelf on nothing.
        foreach (var g in games)
        {
            var t = Tile(g, 252, 378);
            double gbv = TileBloomV(378);
            t.Margin = new Thickness(17, gbv, 17, gbv);
            wrap.Children.Add(Nav(t));
        }
        if (games.Count == 0)
        {
            // 🔴 AN EMPTY COLLECTION MUST BE DELETABLE FROM WHERE YOU SEE IT.
            // Removing the last game leaves a chip that filters to nothing, and
            // the picker only ever ADDS - so without this the strip fills up with
            // dead chips the user cannot get rid of. This is the one screen where
            // an empty collection is unmistakably in front of them.
            if (_filter.StartsWith("col:") && CollectionOf(_filter[4..]) is { } dead)
            {
                var box = new StackPanel { HorizontalAlignment = HorizontalAlignment.Center };
                box.Children.Add(Empty($"האוסף \u201c{dead.Name}\u201d ריק",
                    "אפשר להוסיף אליו משחקים מתוך דף המשחק, או למחוק אותו"));
                var del = Ghost(GlyphDelete, "מחק את האוסף", () => Confirm(
                    $"למחוק את האוסף \u201c{dead.Name}\u201d?",
                    "האוסף עצמו יימחק. המשחקים עצמם לא מושפעים ונשארים בספרייה.",
                    "מחק", destructive: true,
                    () => { _settings.Collections.Remove(dead); SetFilter("all"); Save(); RenderTab(); }));
                del.HorizontalAlignment = HorizontalAlignment.Center;
                del.Margin = new Thickness(0, 18, 0, 0);
                box.Children.Add(Nav(del));
                wrap.Children.Add(box);
            }
            else
            {
                // 🔴 AN EMPTY STATE MUST NOT HAND OUT ADVICE THAT CANNOT WORK.
                // Every filter used to land on the same line - "enable more
                // sources in Settings → Library" - which is genuinely the answer
                // for an empty STORE filter and is nonsense for the others.
                // Nothing in Settings will ever populate "favourites"; the user
                // was being sent to a screen that cannot help, which is worse
                // than saying nothing. Each filter now answers for itself, and
                // an empty filter that is actually GOOD NEWS says so instead of
                // reading as a fault.
                var (emptyTitle, emptyHint) = _filter switch
                {
                    "fav"        => ("עוד לא סימנתם מועדפים",
                                     "פתחו משחק ובחרו \"הוסף למועדפים\" - הוא יופיע כאן ובראש הספרייה"),
                    "recent"     => ("עוד לא הפעלתם משחק מכאן",
                                     "כל משחק שתריצו דרך המסך הזה יופיע כאן, מהאחרון לראשון"),
                    "translated" => ("אין עדיין תרגום עברי למשחקים שלכם",
                                     "התרגומים הזמינים מופיעים בכרטיס של כל משחק"),
                    "installed"  => ("אף אחד מהמשחקים לא מותקן כרגע",
                                     "התקינו משחק דרך החנות שלו והוא יופיע כאן"),
                    "uninst"     => ("כל המשחקים שלכם מותקנים",
                                     "אין כאן מה לעשות - זו בשורה טובה"),
                    _            => ("אין כותרים בקטגוריה הזו",
                                     "אפשר להפעיל מקורות נוספים בהגדרות → ספרייה"),
                };
                wrap.Children.Add(Empty(emptyTitle, emptyHint));
            }
        }

        var scroll = Scroller(wrap);
        Grid.SetRow(scroll, 1);
        col.Children.Add(scroll);

        body.Children.Add(col);
        Grid.SetRow(body, 1);
        root.Children.Add(body);
        return root;
    }

    // ----------------------------------------------------------- downloads

    private FrameworkElement BuildDownloads()
    {
        var sp = new StackPanel { MaxWidth = 1100, HorizontalAlignment = HorizontalAlignment.Center };
        sp.Children.Add(Text("הורדות ועדכונים", "H2", margin: new Thickness(0, 8, 0, 16)));

        var active = _all.Where(g => g.BytesToDownload > 0 && g.BytesDownloaded < g.BytesToDownload).ToList();
        // A title already listed above as an active transfer must NOT appear a
        // second time as "waiting in the store" - the store reports both facts
        // for the same queued download, and printing both read as two games.
        var updates = _all.Where(g => g.UpdatePending && !active.Contains(g)).ToList();

        if (active.Count == 0 && updates.Count == 0)
            sp.Children.Add(Empty("אין הורדות פעילות", "כשמשחק יתעדכן דרך החנות שלו - ההתקדמות תופיע כאן"));

        if (active.Count > 0)
            sp.Children.Add(Text("בהורדה", "H3", margin: new Thickness(0, 4, 0, 8)));

        foreach (var g in active)
        {
            // A download row uses the FULL width of the column: title at the
            // reading-start edge, the size read-out at the far edge, the bar
            // spanning both underneath. A stacked title+caption left ~900px of
            // the card empty and read as a narrow ribbon inside a wide box.
            var card = new Grid();
            card.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            card.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            card.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            card.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

            var name = Inherit(new TextBlock
            {
                Text = g.Name,
                Style = (Style)FindResource("Body"),
                FontWeight = FontWeights.Medium,
                TextTrimming = TextTrimming.CharacterEllipsis,
            });
            Grid.SetRow(name, 0); Grid.SetColumn(name, 0);

            // Each measurement is fenced LTR: a bare "0 B" next to Hebrew lets
            // the unit jump across the number ("B 0"), because a Latin run and a
            // digit run separated only by a space resolve as one block against
            // the paragraph's RTL base.
            var size = Inherit(new TextBlock
            {
                Text = g.DownloadProgress <= 0
                    ? $"ממתין בתור  ·  {Ltr(DriveUsage.Fmt(g.BytesToDownload))}"
                    : $"{Ltr(DriveUsage.Fmt(g.BytesDownloaded))} מתוך {Ltr(DriveUsage.Fmt(g.BytesToDownload))}",
                Style = (Style)FindResource("Caption"),
                VerticalAlignment = VerticalAlignment.Center,
                Opacity = 0.72,
                Margin = new Thickness(18, 0, 0, 0),
            });
            Grid.SetRow(size, 0); Grid.SetColumn(size, 1);

            var bar = new ProgressBar
            {
                Style = (Style)FindResource("Meter"),
                Minimum = 0, Maximum = 1, Value = g.DownloadProgress,
                Margin = new Thickness(0, 10, 0, 0),
            };
            Grid.SetRow(bar, 1); Grid.SetColumnSpan(bar, 2);

            card.Children.Add(name);
            card.Children.Add(size);
            card.Children.Add(bar);

            // Focusable, because a page you cannot touch has no entry focus at
            // all - the shell then falls back to the nav pill, which reads as
            // "you never left the previous screen". The action is the only one
            // that is honest here: the STORE owns the transfer.
            var row = new Button { Style = (Style)FindResource("ListRow"), Content = card };
            row.Click += (_, _) =>
            {
                Sfx.Play(Sound.Select);
                LibraryScanner.Launch(g, _settings);
                ShowToast("נפתח בחנות המקורית");
            };
            sp.Children.Add(Nav(row));
        }

        if (updates.Count > 0)
            sp.Children.Add(Text("ממתינים לעדכון", "H3", margin: new Thickness(0, 22, 0, 8)));

        foreach (var g in updates)
            sp.Children.Add(Nav(RowButton(GlyphDownload, g.Name, "ממתין לעדכון בחנות",
                () => { LibraryScanner.Launch(g, _settings); ShowToast("נפתח בחנות המקורית"); })));

        // 🔴 THIS SECTION USED TO SAY "translations are installed in the desktop
        // launcher" and render DEAD rows. That was true before the headless
        // bridge existed; the moment install/remove/language/repair started
        // working from the console it became misinformation printed on the one
        // screen a user goes to when a translation needs attention - pointing
        // them at the app the separation rule says they should not have to open.
        // The rows now go where the actions live: the game's own blade.
        var hubGames = _all.Where(g => g.Hub is { Available: true, Installed: true }).Take(8).ToList();
        if (hubGames.Count > 0)
        {
            sp.Children.Add(Text("תרגומים", "H3", margin: new Thickness(0, 22, 0, 6)));
            sp.Children.Add(Text("בחרו משחק כדי להתקין, להסיר או להחליף את שפת המשחק",
                "Caption", margin: new Thickness(0, 0, 0, 10)));
            foreach (var g in hubGames)
            {
                var game = g;                            // capture per iteration
                string sub = game.Hub!.PriceCents > 0
                    ? $"תרגום עברי · בתשלום - {Price(game.Hub.PriceCents)}"
                    : "תרגום עברי זמין";
                sp.Children.Add(Nav(RowButton(GlyphCheck, game.Name, sub, () => OpenBlade(game))));
            }
        }
        return Scroller(sp);
    }

    // --------------------------------------------------------- performance

    private FrameworkElement BuildPerformance()
    {
        var sp = new StackPanel { MaxWidth = 1100, HorizontalAlignment = HorizontalAlignment.Center };
        sp.Children.Add(Text("ביצועים וסשנים", "H2", margin: new Thickness(0, 8, 0, 16)));

        // live meters
        _tel.Sample();
        var meters = new StackPanel();
        meters.Children.Add(Meter("מעבד", _tel.CpuPercent, Ltr($"{_tel.CpuPercent:0}%")));
        meters.Children.Add(Meter("זיכרון", _tel.RamPercent, Ltr($"{_tel.RamUsedGb:0.0} / {_tel.RamTotalGb:0.0} GB")));
        // 🔴 "מסך" MEANS *SCREEN*, NOT GPU. This row shows graphics-processor
        // LOAD, and sitting directly under "מעבד" it read as "display: 0%" -
        // a meter about the monitor. The sibling row names the CPU "מעבד", so
        // the parallel term is the one that makes the pair legible at 10ft.
        if (_tel.GpuKnown) meters.Children.Add(Meter("מעבד גרפי", _tel.GpuPercent, Ltr($"{_tel.GpuPercent:0}%")));
        else meters.Children.Add(Text("מסך - לא זמין דרך מוני הביצועים של Windows", "Caption"));
        var bat = Telemetry.Battery();
        if (bat is { } b) meters.Children.Add(Meter("סוללה", b, Ltr($"{b:0}%")));
        sp.Children.Add(Card(meters));

        // 🔴 ORDER: meters, then STORAGE, then live sessions. The first two are
        // always-true facts about the machine, so they read as one continuous
        // "what this PC is doing right now" block; the sessions list is usually
        // empty, and an empty state wedged between them split that block in two
        // and pushed the drives below the fold for no reason.
        // storage
        sp.Children.Add(Text("אחסון", "H3", margin: new Thickness(0, 24, 0, 10)));
        foreach (var d in Storage.Drives())
            // The drive letter is a Latin token, not a word: "(C:)" mirrors to
            // "(:C)" under RTL because the parentheses and the colon are all
            // neutrals. Fenced, and the parens dropped for a separator that has
            // no handedness to get wrong.
            sp.Children.Add(Card(Meter($"{Ltr(d.Name)}‏  ·  {d.Label}", d.Percent * 100,
                $"{Ltr(d.FreeLabel)} פנוי מתוך {Ltr(d.TotalLabel)}")));

        // sessions / Quick Resume
        sp.Children.Add(Text("משחקים פעילים", "H3", margin: new Thickness(0, 24, 0, 10)));
        var live = _sessions?.Sessions.ToList() ?? new List<GameSession>();
        if (live.Count == 0)
            sp.Children.Add(Empty("אין משחק פעיל", "משחק שתפעיל מכאן יופיע כאן - אפשר יהיה להשהות ולחדש אותו"));
        foreach (var s in live)
        {
            string sub = s.Suspended ? $"מושהה · {s.ElapsedLabel}" : $"פועל · {s.ElapsedLabel}";
            sp.Children.Add(Nav(RowButton(s.Suspended ? GlyphPlay : GlyphPause, s.Name, sub,
                () => { if (s.Suspended) ResumeSession(s); else SuspendSession(s); })));
        }

        return Scroller(sp);
    }

    // ----------------------------------------------------------- streaming

    // ------------------------------------------------------------- plugins

    /// <summary>
    /// Plugins as a tab of their own, next to Performance.
    ///
    /// They used to be four rows near the bottom of Settings, which is where a
    /// preference goes - and a plugin is not a preference. It is a background
    /// job with its own state that can start doing things to your machine
    /// while you are in a game, so the one question that matters ("what is
    /// running, and can I stop it") should not be something you scroll a
    /// settings page to find.
    /// </summary>
    private FrameworkElement BuildPlugins()
    {
        var sp = new StackPanel { MaxWidth = 1100, HorizontalAlignment = HorizontalAlignment.Center };
        sp.Children.Add(Text("תוספים", "H2", margin: new Thickness(0, 8, 0, 6)));
        sp.Children.Add(Text("מה מותקן, מה פועל, ומה אפשר לכבות מכאן",
            "Subtext", margin: new Thickness(0, 0, 0, 16)));

        if (!ShellBridge.Available())
        {
            sp.Children.Add(Empty("אין חיבור למנהל התרגומים",
                "התוספים מנוהלים על ידי הלאנצ׳ר; פתח אותו פעם אחת והרשימה תופיע כאן"));
            return Scroller(sp);
        }
        if (_plugins is null)
        {
            sp.Children.Add(Empty("טוען את רשימת התוספים…", "רגע אחד"));
            return Scroller(sp);
        }

        var installed = _plugins.Items.Where(p => p.Installed).ToList();
        var available = _plugins.Items.Where(p => !p.Installed).ToList();

        if (installed.Count == 0)
            sp.Children.Add(Empty("אין תוספים מותקנים", "אפשר להתקין אותם מהלאנצ׳ר"));
        else
        {
            sp.Children.Add(Text("מותקנים", "H3", margin: new Thickness(0, 8, 0, 10)));
            foreach (var p in installed)
            {
                var pl = p;
                sp.Children.Add(Nav(Toggle(pl.Name,
                    pl.Tagline.Length > 0 ? pl.Tagline : "תוסף מותקן",
                    pl.Enabled,
                    v => _ = TogglePluginAsync(pl.Id, v))));
            }
        }

        // 🔴 THE ONES YOU DO NOT HAVE ARE SHOWN, BUT NOT AS BUTTONS. Installing
        // downloads and registers code, and the decision needs the price, the
        // permissions and the full description - none of which fit a couch row,
        // and all of which the launcher already shows. Hiding them entirely
        // would be worse: then "תוספים" looks like the complete set and the
        // user never learns the rest exist.
        if (available.Count > 0)
        {
            sp.Children.Add(Text("זמינים להתקנה", "H3", margin: new Thickness(0, 24, 0, 10)));
            foreach (var p in available)
                sp.Children.Add(InfoRow(GlyphInfo, p.Name,
                    p.Tagline.Length > 0 ? p.Tagline : "לא מותקן"));
            sp.Children.Add(Text("ההתקנה נעשית מהלאנצ׳ר, שם מוצגים גם המחיר וההרשאות",
                "Subtext", margin: new Thickness(0, 10, 0, 0)));
        }

        return Scroller(sp);
    }

    private FrameworkElement BuildStreaming()
    {
        var sp = new StackPanel { MaxWidth = 1100, HorizontalAlignment = HorizontalAlignment.Center };
        sp.Children.Add(Text("סטרימינג ומשחק בענן", "H2", margin: new Thickness(0, 8, 0, 6)));
        sp.Children.Add(Text("ביג לאנץ׳ פותח את הלקוחות שכבר מותקנים אצלך - הוא לא מבצע את הסטרימינג בעצמו",
            "Subtext", margin: new Thickness(0, 0, 0, 16)));

        var targets = Streaming.Targets();
        if (targets.Count == 0)
            sp.Children.Add(Empty("לא נמצאו לקוחות סטרימינג", "התקן Moonlight, Sunshine או Chiaki והם יופיעו כאן"));

        // What you HAVE comes first - a page that opens on seven things you do
        // not own is a catalogue, not a control surface. Order: installed
        // clients, then the browser services (which need nothing installed),
        // then the clients you could add.
        foreach (var t in targets.OrderByDescending(x => x.Installed)
                                 .ThenByDescending(x => x.WebOnly))
        {
            var state = t.Installed ? Badge("מותקן", accent: true)
                      : t.WebOnly   ? Badge("בדפדפן")
                                    : Badge("לא מותקן");
            var target = t;   // capture per iteration
            sp.Children.Add(Nav(RowButton(GlyphStream, t.Name, t.Detail, () =>
            {
                if (!Streaming.Open(target)) return;
                ShowToast(target.Installed || target.WebOnly
                    ? $"{target.Name} נפתח"
                    : $"נפתח דף ההורדה של {target.Name}");
            }, trailing: state)));
        }

        return Scroller(sp);
    }

    // ------------------------------------------------------------ settings

    /// <summary>
    /// Ask the desktop launcher for the account, the plugins, the beta opt-in
    /// and the update state - the four things this process cannot answer.
    ///
    /// 🔴 ONE CALL, NOT FOUR. Each call starts the launcher's whole backend, so
    /// asking separately meant four Python interpreters loading one after
    /// another on a machine that may be a handheld - most of a minute of
    /// "טוען" for four small answers.
    /// </summary>
    private async Task LoadShellAsync(bool force = false)
    {
        if (_shellLoading || (_shellLoaded && !force)) return;
        _shellLoading = true;
        try
        {
            await ShellBridge.EnsureProbedAsync().ConfigureAwait(false);
            if (ShellBridge.Available())
            {
                using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(3));
                var s = await ShellBridge.AllAsync(cts.Token).ConfigureAwait(false);
                if (s is not null)
                {
                    // ?? keeps the last known value for a section that came back
                    // null, so a transient failure in one of them leaves the
                    // page showing the truth it had rather than blanking it.
                    _account = s.Account ?? _account;
                    _plugins = s.Plugins ?? _plugins;
                    _beta = s.Beta ?? _beta;
                    _update = s.Update ?? _update;
                }
            }
        }
        catch { }
        finally
        {
            _shellLoading = false;
            _shellLoaded = true;
            Dispatcher.Invoke(() =>
            {
                // 🔴 A LATE RE-RENDER STEALS THE USER'S PLACE. RenderTab rebuilds
                // the focus map from scratch, and these cards INSERT rows above
                // the existing ones - so every index shifts and the ring would
                // jump somewhere arbitrary in the middle of a scroll. Refresh
                // only while the page is still untouched; a user who already
                // started moving keeps their position and sees the real values
                // the next time Settings opens.
                // 🔴 BOTH CONSUMERS, NOT JUST SETTINGS. This read feeds the settings
                // page AND the plugins page, and plugins moved out to a tab of its
                // own this session - so a gate that still named only "settings"
                // left BuildPlugins stuck on its "טוען…" placeholder for good, with
                // the finished list already sitting in _plugins.
                if (_layer == "view" && (_tab == "settings" || _tab == "plugins") && AtPageEntry()) RenderTab();
            });
        }
    }

    /// <summary>
    /// Flip a plugin on or off in the launcher's own registry.
    ///
    /// The switch has ALREADY moved on screen (Toggle owns its visual state), so
    /// the only thing left is to make the world agree - or, when it will not, to
    /// say so and put the switch back. A toggle that stays flipped after a failed
    /// write is the UI asserting something untrue.
    /// </summary>
    private async Task TogglePluginAsync(string id, bool on)
    {
        string why = "";
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(2));
            var (list, message) = await ShellBridge.SetPluginAsync(id, on, cts.Token).ConfigureAwait(false);
            if (list is not null) { _plugins = list; return; }
            why = message;
        }
        catch { }
        Dispatcher.Invoke(() =>
        {
            ShowToast(why.Length > 0 ? why : "לא ניתן היה לשנות את התוסף");
            // The toggle lives on the PLUGINS page now, so naming "settings"
            // here made this rollback dead code and a failed write left the
            // switch flipped - the UI asserting something untrue.
            if (_layer == "view" && _tab == "plugins") RenderTab();
        });
    }

    /// <summary>
    /// Step one game through follow-global → on → off → follow-global.
    /// Re-opens the blade so the row shows the state that was actually stored,
    /// not the one we hoped for.
    /// </summary>
    private async Task CycleBetaAsync(LibraryGame g, string gameId, bool? current)
    {
        bool? next = current switch { null => true, true => false, _ => null };
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(2));
            var res = await ShellBridge.SetBetaOverrideAsync(gameId, next, cts.Token).ConfigureAwait(false);
            if (res is not null)
            {
                _beta = res;
                Dispatcher.Invoke(() => { if (_layer == "blade" && _selected?.Key == g.Key) OpenBlade(g); });
                return;
            }
        }
        catch { }
        Dispatcher.Invoke(() => ShowToast("לא ניתן היה לשנות את הגדרת הבטא"));
    }

    private async Task SetBetaAsync(bool on)
    {
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(2));
            var res = await ShellBridge.SetBetaAsync(on, cts.Token).ConfigureAwait(false);
            if (res is not null) { _beta = res; return; }
        }
        catch { }
        Dispatcher.Invoke(() =>
        {
            ShowToast("לא ניתן היה לשנות את הגדרת הבטא");
            if (_layer == "view" && _tab == "settings") RenderTab();
        });
    }

    /// <summary>True while focus is still where the page opened it.</summary>
    private bool AtPageEntry()
    {
        var f = Keyboard.FocusedElement as FrameworkElement;
        if (f is null) return true;
        var first = _nav.Skip(_navViewStart).FirstOrDefault(Usable);
        return first is null || ReferenceEquals(f, first);
    }

    /// <summary>Which settings category the pane is showing.</summary>
    private string _setCat = "";

    /// <summary>
    /// Settings as a category rail plus a pane, not one long scroll.
    ///
    /// 🔴 A SINGLE SCROLLING PAGE IS THE WRONG SHAPE FOR A CONTROLLER. Eight
    /// sections stacked into one column means the only way to reach the last
    /// one is to press "down" past every row in the seven before it - and this
    /// page had grown to roughly sixty focusables. On a mouse that is a flick;
    /// on a pad it is a minute of held input, and it gets worse with every
    /// setting added. A rail turns "scroll to it" into "point at it": one press
    /// to the category, one press into its rows.
    ///
    /// The rail takes a quarter of the width and sits at the visual RIGHT, which
    /// in this RTL shell is Grid.Column 0 - the reading edge, where a Hebrew eye
    /// starts. Reading a column index as a screen position is the single most
    /// common way to land something on the wrong side of this window.
    /// </summary>
    private FrameworkElement BuildSettings()
    {
        var cats = new List<(string Name, string Glyph, StackPanel Panel)>();
        StackPanel Section(string name, string glyph)
        {
            var pane = new StackPanel();
            cats.Add((name, glyph, pane));
            return pane;
        }

        var head = new StackPanel();
        var sp = head;

        // ---- identity, as the page's own header. The same badge Windows shows
        // on the taskbar and on the boot splash, so the thing you launched, the
        // thing in the tray and the thing that says "this is Big Launch" are
        // visibly one product.
        //
        // 🔴 IT SITS AT THE TOP, NOT IN A FOOTER. Content BELOW the last
        // focusable row is unreachable with a controller - BringIntoView stops
        // as soon as that row is on screen - so a brand block at the bottom of
        // a long settings page is a block nobody with a pad will ever see.
        {
            var id = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 6, 0, 18) };
            id.Children.Add(new Image
            {
                Source = new BitmapImage(new Uri("pack://application:,,,/Assets/logo.png")),
                Width = 52, Height = 52,
                Margin = new Thickness(0, 0, 16, 0),
                VerticalAlignment = VerticalAlignment.Center,
            });
            var t = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
            t.Children.Add(Text("הגדרות", "H2"));
            t.Children.Add(Text($"ביג לאנץ׳ · גרסה {Ltr(typeof(MainWindow).Assembly.GetName().Version?.ToString() ?? "1.0")}",
                                "Caption"));
            id.Children.Add(t);
            sp.Children.Add(id);
        }

        // ---- account (report §7.1 · parity with the desktop launcher)
        //
        // 🔴 READ-ONLY, AND DELIBERATELY SO. Signing in means a browser, an
        // OAuth round trip and a keyring write - none of which belong on a
        // screen driven from a sofa with a controller, and all of which the
        // desktop launcher already does properly. So the console SHOWS who is
        // signed in and what they own, and points at the one handoff for the
        // rest. A half-built sign-in here would be a second place that can
        // hold a token.
        sp = Section("חשבון", GlyphUser);
        if (!_shellLoaded)
        {
            sp.Children.Add(InfoRow(GlyphInfo, "טוען את פרטי החשבון…",
                "שואל את הלאנצ׳ר של שולחן העבודה"));
        }
        else if (!ShellBridge.Available())
        {
            sp.Children.Add(InfoRow(GlyphInfo, "לא ניתן לקרוא את פרטי החשבון",
                "הלאנצ׳ר המותקן ישן מכדי להישאל. עדכנו אותו והמידע יופיע כאן"));
        }
        else if (_account is null || !_account.SignedIn)
        {
            sp.Children.Add(InfoRow(GlyphUser, "לא מחוברים",
                "ההתחברות נעשית בלאנצ׳ר של שולחן העבודה. אחרי שתתחברו שם, הפרטים והרכישות יופיעו כאן"));
        }
        else
        {
            // 🔴 AN IDENTITY IS NOT A SETTINGS ROW. This was one InfoRow with the
            // name on top and the address underneath - the same glyph, the same
            // height and the same weight as "צלילי ממשק" two sections down. The
            // one thing on this page that answers "whose machine is this" looked
            // exactly like a preference. It gets a card of its own.
            sp.Children.Add(AccountCard(_account));

            if (_account.Purchases.Count > 0)
            {
                sp.Children.Add(Text(
                    _account.Purchases.Count == 1 ? "הרכישה שלך" : $"{_account.Purchases.Count} רכישות",
                    "H3", margin: new Thickness(0, 18, 0, 8)));

                // 🔴 ONE ROW PER PURCHASE, AND EACH ONE GOES SOMEWHERE. They used
                // to be joined with " · " into a single subtitle capped at six -
                // which turns the things you PAID FOR into a truncated string,
                // and a seventh purchase into a thing that silently is not
                // there. Every purchase carries a game id, so a title we can
                // resolve becomes a way into that game instead of a word.
                foreach (var (id, title) in _account.Purchases)
                {
                    var owned = _scanned.FirstOrDefault(x => x.Hub is not null && x.Hub.Id == id);
                    if (owned is not null)
                    {
                        var g2 = owned;
                        // 🔴 NO SUBTITLE ON THE COMMON CASE. Ten rows each
                        // repeating "בספרייה שלך - פתחו את הכרטיס" is the same
                        // sentence ten times: it doubles the height of the list,
                        // says nothing that differs between rows, and buries the
                        // one row that DOES differ. The accent tick already says
                        // "owned and here"; only the exception gets words.
                        sp.Children.Add(Nav(RowButton(GlyphCheck, title, null,
                            () => OpenBlade(g2),
                            glyphBrush: (Brush)FindResource("Accent"))));
                    }
                    else
                    {
                        sp.Children.Add(InfoRow(GlyphCheck, title,
                            "לא נמצא במחשב הזה - הרכישה שמורה בחשבון"));
                    }
                }
            }
            else if (_account.Reason.Length > 0)
            {
                // 🔴 SAY WHY. An empty list and a failed lookup look identical on
                // screen, and one of them means "you own nothing" while the
                // other means "we could not ask" - showing the first when the
                // truth is the second is the app lying about the user's money.
                sp.Children.Add(InfoRow(GlyphInfo, "לא ניתן לטעון את הרכישות",
                    _account.Reason));
            }
            else
            {
                sp.Children.Add(InfoRow(GlyphInfo, "אין רכישות בחשבון הזה",
                    "תרגומים בתשלום נרכשים באתר או בלאנצ׳ר של שולחן העבודה"));
            }
        }

        // ---- experience
        sp = Section("חוויה", GlyphImage);
        sp.Children.Add(Nav(Toggle("צלילי ממשק", "משוב קולי לניווט, בחירה והשקה",
            _settings.SoundEnabled, v =>
            {
                _settings.SoundEnabled = v;
                Sfx.Configure(v, _settings.SoundVolume);
                Save(); Sfx.Play(Sound.Select);
            })));
        sp.Children.Add(Nav(Toggle("אנימציות", "מעברים ותנועת מיקוד. כיבוי מוריד עומס במחשבים חלשים",
            _settings.AnimationsEnabled, v => { _settings.AnimationsEnabled = v; Save(); })));
        sp.Children.Add(Nav(Toggle("זכוכית", "רקע אקרילי של Windows. כיבוי = רקע אטום ומהיר יותר",
            _settings.GlassEnabled, v =>
            {
                _settings.GlassEnabled = v;
                Backdrop.Apply(this, v ? Backdrop.BACKDROP_ACRYLIC : Backdrop.BACKDROP_NONE);
                Save();
            })));
        sp.Children.Add(Nav(Toggle("נתוני חומרה בזמן אמת", "מעבד, זיכרון ומסך בראש המסך",
            _settings.ShowTelemetry, v => { _settings.ShowTelemetry = v; Save(); OnTick(); })));
        // Only offered when there is actually a film to play - a switch for a
        // thing that does not exist on this machine is just a confusing row.
        if (IntroPath() is not null)
            sp.Children.Add(Nav(Toggle("סרטון פתיחה", "מתנגן בזמן טעינת הספרייה. כל מקש מדלג עליו",
                _settings.IntroEnabled, v => { _settings.IntroEnabled = v; Save(); })));

        // ---- library
        sp.Children.Add(AccentRow());

        // ---- how big things are drawn, and how much of a card is drawn ------
        sp = Section("גודל ותצוגה", GlyphImage);

        // 🔴 THIS IS A REACH SETTING, NOT A TASTE ONE. The same shell is used on
        // a 24" monitor at desk range and on a 55" TV from a sofa - identical
        // pixels, nothing like the same apparent size - and no single tile size
        // is right for both. Winhanced and Big Picture both ship this for the
        // same reason.
        // The per-group sliders REPLACE this category's rows rather than sitting
        // under them: while you are tuning four tracks, a list of presets above
        // them is another set of controls fighting for the same decision.
        if (_sizesOpen)
        {
            BuildSizeSliders(sp);
        }
        else
        {
            sp.Children.Add(Nav(RowButton(GlyphImage, "רקע דינמי: " + AmbientStyleLabel(),
                "האור שנע אט מאחורי המסך - כמו בלאנצ׳ר הרגיל",
                PickAmbientStyle)));
            sp.Children.Add(Nav(RowButton(GlyphImage, "גודל התצוגה: " + UiScaleLabel(),
                "כרטיסיות, טקסט, שורות, כפתורים ורמזים - הכל יחד",
                PickUiScale)));
            sp.Children.Add(Nav(RowButton(GlyphGrid, "תצוגת כרטיסייה: " + CardStyleLabel(),
                CardStyleDetail(), PickCardStyle)));
        }

        sp = Section("ספרייה", GlyphGrid);
        // 🔴 FOUR ROWS THAT ALL SAY "a source for the universal library" carry
        // ZERO information - a repeated subtitle is the signature of a
        // machine-generated list, and it hides the one fact you actually want here:
        // did this source find anything on THIS machine? A count turns a dead
        // caption into the answer, and it comes free from the library we already
        // scanned.
        foreach (var (label, kinds, get, set) in new (string, GameSource[], Func<bool>, Action<bool>)[]
        {
            ("Steam",   new[]{GameSource.Steam},   () => _settings.SourceSteam,     v => _settings.SourceSteam = v),
            ("Epic",    new[]{GameSource.Epic},    () => _settings.SourceEpic,      v => _settings.SourceEpic = v),
            ("GOG",     new[]{GameSource.Gog},     () => _settings.SourceGog,       v => _settings.SourceGog = v),
            ("Ubisoft", new[]{GameSource.Ubisoft}, () => _settings.SourceUbisoft,   v => _settings.SourceUbisoft = v),
            ("Xbox / EA", new[]{GameSource.Xbox, GameSource.Ea}, () => _settings.SourceXbox, v => _settings.SourceXbox = v),
            ("אמולטורים", new[]{GameSource.Emulator}, () => _settings.SourceEmulators, v => _settings.SourceEmulators = v),
        })
        {
            var g = get; var s = set;
            int n = _all.Count(x => kinds.Contains(x.Source));
            string detail = !g() ? "כבוי - המשחקים מהמקור הזה לא מוצגים"
                          : n > 0 ? Games(n) + " בספרייה"
                                  : "לא נמצאו משחקים במחשב הזה";
            sp.Children.Add(Nav(Toggle(label, detail, g(),
                v => { s(v); Save(); _ = ReloadLibraryAsync(); })));
        }
        // The other half of "הסתר מהספרייה". Without a way back, hiding is a
        // one-way door - the entry is gone from every screen that could otherwise
        // offer to restore it, so this row is the ONLY route.
        int nHidden = _settings.Profiles.Count(pr => pr.Hidden);
        if (nHidden > 0)
            sp.Children.Add(Nav(RowButton(GlyphHide, "משחקים מוסתרים",
                // The VERB has to agree too - Games() alone gives the correct
                // "משחק אחד" and then a plural verb turns it back into a mistake.
                nHidden == 1 ? "משחק אחד לא מוצג בספרייה"
                             : Games(nHidden) + " לא מוצגים בספרייה", OpenHidden)));

        sp.Children.Add(Nav(RowButton(GlyphRefresh, "רענן ספרייה",
            $"{_all.Count} כותרים מ-{_all.Select(x => x.Source).Distinct().Count()} מקורות",
            () => _ = ReloadLibraryAsync())));

        // ---- controller (report §8.4)
        //
        // 🔴 THE HONEST VERSION OF WINHANCED'S PADDLE PAGE. Theirs targets
        // handhelds and on an ordinary PC it just says "No configurable paddles
        // on this device" - so the part that carries real value here is the part
        // a couch user actually needs: IS my controller seen, and which one is
        // it. A "remap paddles" button on a machine with no paddles would be a
        // control that cannot work, which is worse than saying so.
        sp = Section("שלט", GlyphGame);

        // What the FOOTER is drawing right now, and why. The prompts change
        // shape per device, so when they say ✕ instead of A the user should be
        // able to find out here that this is deliberate and what was detected.
        string kindSub = _padKind switch
        {
            PadKind.Ps5 => "הרמזים מוצגים כ-✕ ○ □ △ בלבן · L1/R1 · CREATE",
            PadKind.Ps4 => "הרמזים מוצגים כ-✕ ○ □ △ בצבע · L1/R1 · SHARE",
            PadKind.Xbox => "הרמזים מוצגים כ-A B X Y · LB/RB",
            _ => "הרמזים מוצגים כמקשים. געו בשלט והם יתחלפו אוטומטית",
        };

        // 🔴🔴 THE OVERRIDE IS THE FIX, NOT A PREFERENCE. A DualSense behind Steam
        // Input, DS4Windows or Windows' own pairing IS an Xbox pad to every API
        // on this machine — the Sony VID/PID never reaches us, XInput answers,
        // and the honest result is "Xbox". Detection is not broken there; it is
        // reporting the truth about the system. It is simply not the truth about
        // what the person is holding, and nothing we can probe will ever close
        // that gap. So the row that used to only RE-SCAN now also lets the user
        // say it outright, and their answer outranks every probe from then on.
        sp.Children.Add(Nav(RowButton(GlyphGame, "סגנון רמזי הכפתורים: " + PadStyleLabel(),
            _settings.PadStyle == "auto"
                ? $"זוהה אוטומטית: {KindNameOf(_padKind)} · {kindSub} · לחצו כדי לבחור ידנית"
                : $"{kindSub} · נבחר ידנית · לחצו כדי להחליף",
            PickPadStyle)));

        var pads = Interop.Gamepad.Probe();
        bool live = _pad?.Connected == true;
        if (pads.Count == 0 && !live)
        {
            sp.Children.Add(Nav(RowButton(GlyphGame, "לא זוהה שלט",
                "חברו שלט - השורה תתעדכן מעצמה. אפשר לנווט בכל המסכים גם עם המקלדת",
                () => { RedetectPad(); RenderTab(); })));
        }
        else
        {
            foreach (var pad in pads)
                sp.Children.Add(Nav(RowButton(GlyphGame, pad.Name,
                    pad.Kind + (pad.Wireless ? " · אלחוטי" : "") + " · מחובר ומזוהה",
                    () => { Sfx.Play(Sound.Select); ShowToast("השלט מחובר ופועל"); })));

            // 🔴 A PAD THAT DRIVES THE SHELL BUT ENUMERATES AS NOTHING IS STILL A
            // CONNECTED PAD. Probe() asks the two enumeration APIs; Connected is
            // set by the input poll that is at that moment moving the focus ring.
            // When they disagree the poll is the one holding the evidence, and
            // saying "no controller" while the user is steering with one is the
            // single least believable thing this screen can print.
            if (pads.Count == 0)
                sp.Children.Add(InfoRow(GlyphGame, "שלט מחובר ופועל",
                    "הקלט מגיע ועובד, אבל ההתקן לא מדווח על עצמו בשם - בחרו את הסגנון ידנית למעלה"));

            sp.Children.Add(Nav(RowButton(GlyphRefresh, "בדיקה מחדש",
                "סורק שוב אילו שלטים מחוברים", () => { RedetectPad(); RenderTab(); })));
        }
        // 🔴 A STATEMENT, NOT A BUTTON. This was Nav(RowButton(..., () => { })) —
        // focusable, and pressing A on it did literally nothing: no sound, no
        // toast, no change. A control that takes the ring and then answers
        // NOTHING reads as a broken app, which is a worse outcome than the
        // hidden setting this row exists to prevent. It is information, so it is
        // an InfoRow: still visible, still readable at 10ft, no longer promising
        // an action it cannot perform.
        sp.Children.Add(InfoRow(GlyphInfo, "מיפוי כפתורים אחוריים (Paddles)",
            "לא נתמך במחשב הזה - נדרש התקן ידני עם כפתורים אחוריים (ROG Ally, MSI Claw, Legion Go)"));

        // ---- behaviour
        sp = Section("מיפוי כפתורים", GlyphGame);
        BuildMappingSection(sp);

        sp = Section("התנהגות", GlyphSettings);
        sp.Children.Add(Nav(Toggle("השהיה וחידוש (Quick Resume)",
            "מקפיא משחק במקום לסגור אותו. מה המחיר: המשחק ממשיך להחזיק זיכרון",
            _settings.QuickResume, v => { _settings.QuickResume = v; Save(); })));
        sp.Children.Add(Nav(Toggle("שומר השקה חכם",
            "מזהה חלונות שחוסמים הפעלה (DirectX, אנטי-צ׳יט, EULA) ומקפיץ אותם. מה המחיר: נוגע בחלונות של תוכנות אחרות",
            _settings.LaunchWatcher, v => { _settings.LaunchWatcher = v; Save(); })));
        sp.Children.Add(Nav(Toggle("שמירה על זיכרון",
            $"אזהרה כשהזיכרון עובר {_settings.MemoryWarnPercent}%",
            _settings.MemoryGuard, v => { _settings.MemoryGuard = v; Save(); })));
        sp.Children.Add(Nav(Toggle("נוכחות ב-Discord",
            string.IsNullOrWhiteSpace(_settings.DiscordAppId)
                ? "כבוי - חסר מזהה אפליקציה של Discord בקובץ ההגדרות (ראו תחזוקה)"
                : _discord?.Status ?? "לא מחובר",
            _settings.DiscordPresence, v =>
            {
                _settings.DiscordPresence = v; Save();
                // Turning it ON is an explicit request: it must not sit out the
                // rest of a backoff window that was earned while it was off.
                _discordNextTry = DateTime.MinValue; _discordGap = 15;
                if (!v) { try { _discord?.Dispose(); } catch { } _discord = null; }
                _ = UpdatePresenceAsync();
            })));

        // ---- plugins (parity with the desktop launcher)
        //
        // ---- updates + beta (parity with the desktop launcher)
        sp = Section("עדכונים", GlyphDownload);
        if (ShellBridge.Available() && _beta is not null)
        {
            int n = _beta.Overrides.Count;
            sp.Children.Add(Nav(Toggle("גרסאות בטא של תרגומים",
                n == 0 ? "מקבלים גרסאות מוקדמות של תרגומים לפני שהן יציבות"
                       : n == 1 ? "מקבלים גרסאות מוקדמות · למשחק אחד יש הגדרה משלו"
                                : $"מקבלים גרסאות מוקדמות · ל-{n} משחקים יש הגדרה משלהם",
                _beta.Channel,
                v => _ = SetBetaAsync(v))));
        }
        if (ShellBridge.Available() && _update is not null)
        {
            // 🔴 REPORTS, NEVER INSTALLS - and not out of caution. The launcher's
            // installer KILLS BigLaunch.exe on purpose (it has to: the file it
            // replaces sits in the same folder and the console holds it open),
            // and it asks for UAC, which lives on the secure desktop where a
            // controller cannot reach. A button here would end this process
            // mid-press and then strand the user at a prompt they cannot answer.
            // So the console tells you, and the one handoff below is how to act.
            // 🔴 SHOW BOTH VERSIONS. The launcher offers an update when the
            // version is newer OR when only the build id differs - so the
            // offered version can legitimately be the same or even lower than
            // the installed one. Printing only the offered number would read
            // as a lie in exactly that case; printing both is always true.
            sp.Children.Add(InfoRow(_update.Available ? GlyphDownload : GlyphCheck,
                _update.Available
                    ? $"קיים עדכון ללאנצ׳ר · גרסה {Ltr(_update.Latest)}"
                    : $"הלאנצ׳ר מעודכן · גרסה {Ltr(_update.Current)}",
                _update.Available
                    ? $"מותקנת אצלכם {Ltr(_update.Current)} · ההתקנה נעשית בלאנצ׳ר של שולחן העבודה - היא סוגרת את ביג-לאנץ׳ ומבקשת הרשאת מנהל. המעבר נמצא בתחתית העמוד"
                    : "אין גרסה חדשה יותר"));
        }
        sp.Children.Add(Nav(RowButton(GlyphSync, "בדוק שוב מול הלאנצ׳ר",
            "מרענן חשבון, רכישות, תוספים ומצב עדכון",
            () =>
            {
                // Reset() as well as the flag: the common reason to press this
                // is "I just updated the launcher", and that is precisely the
                // answer the cached probe cannot give.
                ShellBridge.Reset();
                _shellLoaded = false;
                ShowToast("בודק…");
                _ = LoadShellAsync(true);
            })));

        // ---- maintenance
        sp = Section("תחזוקה", GlyphRefresh);
        var (files, bytes) = Catalog.ArtCacheStats();
        sp.Children.Add(Nav(RowButton(GlyphDelete, "נקה מטמון תמונות",
            files == 0 ? "המטמון ריק" : $"{files} קבצים · {DriveUsage.Fmt(bytes)}",
            () =>
            {
                int n = Catalog.ClearArtCache();
                // The decoded copies live in memory too; clearing the files while
                // keeping the bitmaps would show the user a cache they just
                // emptied still painting.
                lock (ImgCache) ImgCache.Clear();
                ShowToast($"נמחקו {n} קבצים");
                RenderTab();
            })));
        sp.Children.Add(Nav(RowButton(GlyphCamera, "תיקיית צילומי מסך", Capture.Folder,
            () => Storage.OpenFolder(Capture.Folder))));
        // 🔴 A SETTING THAT LIVES IN A FILE NEEDS A WAY TO REACH THAT FILE. The
        // Discord row above says the app id is set "in the settings file" — and
        // that was the whole instruction: no path, no button, on a screen the
        // user is driving with a controller from across a room. A dead-end
        // instruction is barely better than no instruction. This is one press.
        // ⚠ SINGULAR imperative — this is a BUTTON LABEL. The shell's voice is
        // already split cleanly and deliberately: a label names an action in the
        // singular ("נקה מטמון תמונות", "הרץ שוב את אשף ההגדרה", "פתח תיקייה"),
        // while a SENTENCE addressed to the user is polite plural ("חברו שלט
        // ולחצו כאן", "השאירו ריק"). Measured across the file: every plural is a
        // sentence and every label is singular. Keep it that way.
        sp.Children.Add(Nav(RowButton(GlyphFolder, "פתח את תיקיית ההגדרות",
            Catalog.StateDir, () => Storage.OpenFolder(Catalog.StateDir))));
        sp.Children.Add(Nav(RowButton(GlyphSettings, "הרץ שוב את אשף ההגדרה",
            "חמישה שלבים: ברוך הבא, מכשיר, ספריות, התאמה אישית, סיום",
            () => ShowOnboarding())));

        // ---- THE handoff used to be a settings category of its own.
        // It moved to the power menu (OpenPower), where it belongs: leaving for
        // the desktop is the same KIND of decision as sleeping, restarting or
        // quitting - "how do I get out of here" - and nobody looks for the way
        // out under Settings. A category holding exactly one row was also the
        // only one-row category in the rail.

        return SettingsShell(head, cats);
    }

    /// <summary>Lay the settings rail beside the selected category's pane.</summary>
    private FrameworkElement SettingsShell(
        StackPanel head, List<(string Name, string Glyph, StackPanel Panel)> cats)
    {
        if (cats.Count == 0) return Scroller(head);
        if (!cats.Any(c => c.Name == _setCat)) _setCat = cats[0].Name;

        var root = new Grid { Margin = new Thickness(48, 20, 48, 24) };
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(3, GridUnitType.Star) });

        // --- the rail (visual RIGHT) ------------------------------------------
        var rail = new StackPanel { Margin = new Thickness(0, 0, 0, 0) };
        rail.Children.Add(head);
        foreach (var c in cats)
        {
            var cat = c;
            bool on = cat.Name == _setCat;
            var btn = RowButton(cat.Glyph, cat.Name, null, () =>
            {
                if (_setCat == cat.Name) return;
                _setCat = cat.Name;
                RenderTab();
            });
            // The selected row keeps the accent so the pane never floats free of
            // the thing that opened it - the one piece of state a rail must show.
            //
            // ⚠ Built from the live AccentColor rather than a named brush: the
            // accent is REPLACED at runtime (Tokens.xaml says so), so a frozen
            // brush captured here would be the old colour after a theme change.
            if (on && TryFindResource("AccentColor") is Color ac)
                btn.Background = new SolidColorBrush(Color.FromArgb(0x2E, ac.R, ac.G, ac.B));
            rail.Children.Add(Nav(btn));
        }
        var railScroll = Scroller(rail);
        railScroll.Padding = new Thickness(0, 0, 18, 0);
        Grid.SetColumn(railScroll, 0);
        root.Children.Add(railScroll);

        // --- the pane (visual LEFT) -------------------------------------------
        var pane = cats.First(c => c.Name == _setCat);
        var body = new StackPanel();
        body.Children.Add(Text(pane.Name, "H2", margin: new Thickness(0, 0, 0, 14)));
        body.Children.Add(pane.Panel);
        var paneScroll = Scroller(body);
        paneScroll.Padding = new Thickness(0, 0, 0, 0);
        Grid.SetColumn(paneScroll, 1);
        root.Children.Add(paneScroll);
        return root;
    }

    private void Save() => _settings.Save();

    // =====================================================================
    //  building blocks
    // =====================================================================

    private TextBlock Text(string text, string style, Thickness? margin = null) => new()
    {
        Text = text,
        Style = (Style)FindResource(style),
        Margin = margin ?? new Thickness(0),
        TextWrapping = TextWrapping.Wrap,
    };

    private Border Card(UIElement content) => new()
    {
        Style = (Style)FindResource("GlassCard"),
        Margin = new Thickness(0, 0, 0, 10),
        Child = content,
    };

    /// <param name="onArt">
    /// 🔴 A TRANSLUCENT CHIP CANNOT GUARANTEE CONTRAST OVER BOX ART. The glass
    /// plate + muted grey text reads fine on our own dark surfaces and vanishes
    /// on a light cover - "לא מותקן" sat as grey-on-white across the middle of
    /// A Plague Tale's own wordmark. Box art is arbitrary imagery, so a badge
    /// drawn on it needs a SOLID plate and full-strength text, exactly like the
    /// accent pill beside it (which was always legible for that reason).
    /// </param>
    private UIElement Badge(string text, bool accent = false, bool onArt = false) => new Border
    {
        CornerRadius = (CornerRadius)FindResource("RadPill"),
        Background = accent ? (Brush)FindResource("Accent")
                   : onArt  ? new SolidColorBrush(Color.FromArgb(0xEB, 0x0C, 0x11, 0x18))
                            : (Brush)FindResource("GlassChipHi"),
        Padding = new Thickness(12, 4, 12, 4),
        Margin = new Thickness(0, 0, 8, 0),
        Child = new TextBlock
        {
            Text = text,
            Style = (Style)FindResource("Caption"),
            Foreground = accent ? new SolidColorBrush(Color.FromRgb(0x0E, 0x14, 0x1B))
                       : onArt  ? (Brush)FindResource("FgPrimary")
                                : (Brush)FindResource("FgSecondary"),
            // A badge is a short label that is often a number + a Latin unit
            // ("75.4 GB", "Steam"). Left in the RTL flow the unit jumps in front
            // of the value - the same neutral-resolution trap as the "%" readout
            // - so a badge that has no Hebrew at all is pinned LTR.
            FlowDirection = HasHebrew(text) ? FlowDirection.RightToLeft : FlowDirection.LeftToRight,
        },
    };

    /// <summary>True if the string contains a Hebrew letter (U+0590-05FF).</summary>
    private static bool HasHebrew(string s)
    {
        foreach (char c in s) if (c >= '֐' && c <= '׿') return true;
        return false;
    }

    private UIElement Empty(string title, string detail)
    {
        var sp = new StackPanel { Margin = new Thickness(0, 60, 0, 0), HorizontalAlignment = HorizontalAlignment.Center };
        sp.Children.Add(new TextBlock
        {
            Text = GlyphGame,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 44,
            Foreground = (Brush)FindResource("FgDim"),
            HorizontalAlignment = HorizontalAlignment.Center,
            Margin = new Thickness(0, 0, 0, 14),
        });
        sp.Children.Add(Text(title, "H3", margin: new Thickness(0, 0, 0, 6)));
        sp.Children.Add(Text(detail, "Subtext"));
        foreach (UIElement c in sp.Children) if (c is FrameworkElement f) f.HorizontalAlignment = HorizontalAlignment.Center;
        return sp;
    }

    private FrameworkElement Meter(string label, double percent, string detail)
    {
        var sp = new StackPanel { Margin = new Thickness(0, 0, 0, 12) };
        var head = new Grid();
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var l = Text(label, "Body"); Grid.SetColumn(l, 0);
        var r = Text(detail, "Subtext"); Grid.SetColumn(r, 1);
        head.Children.Add(l); head.Children.Add(r);
        sp.Children.Add(head);
        sp.Children.Add(new ProgressBar
        {
            Style = (Style)FindResource("Meter"),
            Minimum = 0, Maximum = 100,
            Value = Math.Clamp(percent, 0, 100),
            Margin = new Thickness(0, 7, 0, 0),
            Foreground = percent >= 90 ? (Brush)FindResource("Destructive")
                       : percent >= 75 ? new SolidColorBrush((Color)FindResource("GlowWarmColor"))
                       : (Brush)FindResource("Accent"),
        });
        return sp;
    }

    /// <summary>
    /// Let a styled TextBlock follow its Button's Foreground.
    ///
    /// 🔴 INHERITANCE LOSES TO AN EXPLICIT STYLE SETTER. The focused row uses
    /// Steam's invert - a white plate with dark text - and the ListRow trigger
    /// duly sets Foreground on the BUTTON. The glyph went dark, because it has
    /// no style; the title and subtitle stayed light grey, because Body/Caption
    /// set Foreground themselves, and a locally-set value always beats an
    /// inherited one. The result was a bright white row with near-invisible
    /// text - and it looked like a broken control rather than a colour rule.
    /// Binding to the ancestor makes the trigger reach them.
    /// </summary>
    private static TextBlock Inherit(TextBlock tb)
    {
        tb.SetBinding(TextBlock.ForegroundProperty, new Binding("Foreground")
        {
            RelativeSource = new RelativeSource(RelativeSourceMode.FindAncestor, typeof(ButtonBase), 1),
        });
        return tb;
    }

    private Button RowButton(string glyph, string title, string? detail, Action click,
                             UIElement? trailing = null, Brush? glyphBrush = null)
    {
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var g = new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 18,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 14, 0),
        };
        // A destructive row must ANNOUNCE itself before the click, not only
        // after it. The rows do not invert on focus, so a coloured glyph
        // stays coloured and reads as a warning at every state.
        if (glyphBrush is not null) g.Foreground = glyphBrush;
        Grid.SetColumn(g, 0);

        var col = new StackPanel();
        col.Children.Add(Inherit(new TextBlock
        {
            Text = title,
            Style = (Style)FindResource("Body"),
            FontWeight = FontWeights.Medium,
        }));
        // 🔴 A ROW WITH NO SUBTITLE IS A LEGITIMATE ROW. `detail` was typed
        // non-nullable and every caller happened to pass one - so the first
        // caller that did not (the settings rail, whose categories are one word
        // and need no explanation) threw a NullReferenceException INSIDE a click
        // handler, where App's global catch swallowed it. The page simply never
        // appeared: no dialog, no crash, the old screen still on display. Length
        // on a null is the whole bug; a null check is the whole fix.
        if (!string.IsNullOrEmpty(detail))
            col.Children.Add(Inherit(new TextBlock
            {
                Text = detail,
                Style = (Style)FindResource("Caption"),
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 3, 0, 0),
                Opacity = 0.72,   // secondary by OPACITY, so it inverts with the row
            }));
        Grid.SetColumn(col, 1);

        grid.Children.Add(g);
        grid.Children.Add(col);

        // The far edge carries the row's STATE. A wide row with everything
        // crowded at the reading-start edge leaves most of its width empty and
        // reads as a narrow ribbon inside a big box.
        if (trailing is not null)
        {
            if (trailing is FrameworkElement tf)
            {
                tf.VerticalAlignment = VerticalAlignment.Center;
                tf.Margin = new Thickness(18, 0, 0, 0);
            }
            Grid.SetColumn(trailing, 2);
            grid.Children.Add(trailing);
        }

        var b = new Button { Style = (Style)FindResource("ListRow"), Content = grid };
        b.Click += (_, _) => { Sfx.Play(Sound.Select); click(); };
        return b;
    }

    private Button Toggle(string title, string detail, bool value, Action<bool> set)
    {
        bool state = value;
        Button? btn = null;

        Grid Build()
        {
            var grid = new Grid();
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var col = new StackPanel();
            col.Children.Add(new TextBlock { Text = title, Style = (Style)FindResource("Body"), FontWeight = FontWeights.Medium });
            col.Children.Add(new TextBlock
            {
                Text = detail,
                Style = (Style)FindResource("Caption"),
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 3, 0, 0),
            });
            Grid.SetColumn(col, 0);

            var pill = new Border
            {
                Width = 52, Height = 28, CornerRadius = new CornerRadius(14),
                Background = state ? (Brush)FindResource("Accent") : (Brush)FindResource("GlassChipHi"),
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(16, 0, 0, 0),
                Child = new Border
                {
                    Width = 20, Height = 20, CornerRadius = new CornerRadius(10),
                    Background = new SolidColorBrush(Colors.White),
                    // 🔴 OFF SITS ON THE VISUAL RIGHT, ON TRAVELS TO THE VISUAL LEFT.
                    // In an RTL window the reading eye starts at the right, so the
                    // right seat is the resting/"nothing happening" one and the knob
                    // moves AWAY from it to turn on - the same relationship an LTR
                    // switch has, mirrored with the layout instead of against it.
                    // Layout space is itself mirrored here, so visual-left is
                    // HorizontalAlignment.Right.
                    HorizontalAlignment = state ? HorizontalAlignment.Right : HorizontalAlignment.Left,
                    Margin = new Thickness(4, 0, 4, 0),
                },
            };
            Grid.SetColumn(pill, 1);

            grid.Children.Add(col);
            grid.Children.Add(pill);
            return grid;
        }

        btn = new Button { Style = (Style)FindResource("ListRow"), Content = Build() };
        btn.Click += (_, _) =>
        {
            state = !state;
            btn!.Content = Build();
            Sfx.Play(Sound.Select);
            set(state);
        };
        return btn;
    }

    private Button CTA(string glyph, string label, Action click)
    {
        var sp = new StackPanel { Orientation = Orientation.Horizontal };
        sp.Children.Add(new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 16,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 10, 0),
        });
        sp.Children.Add(new TextBlock { Text = label, VerticalAlignment = VerticalAlignment.Center });

        var b = new Button { Style = (Style)FindResource("PrimaryCTA"), Content = sp };
        b.Click += (_, _) => click();
        return b;
    }

    /// <summary>
    /// The width a floating card may actually take.
    ///
    /// EVERY DIALOG CARRIED A HARDCODED WIDTH - 940, 900, 760 - written against
    /// this machine's 2560px window. At 1280x720 (the resolution a TV shell is
    /// most likely to be told to use) the widest cards ran past both edges, and
    /// the buttons on them went with it: the confirm row of a destructive
    /// dialog could sit off-screen with no way to scroll to it. The number
    /// stays as the INTENT and the viewport gets the final say.
    /// </summary>
    private double CardWidth(double want)
    {
        double room = ActualWidth > 0 ? ActualWidth : SystemParameters.PrimaryScreenWidth;
        // 72px of breathing room per side keeps the card reading as a floating
        // panel rather than a second window edge; 360 is the floor below which
        // a two-column row stops being laid out at all.
        return Math.Max(360, Math.Min(want, room - 144));
    }

    private Button Ghost(string glyph, string label, Action click, Thickness? margin = null)
    {
        var sp = new StackPanel { Orientation = Orientation.Horizontal };
        sp.Children.Add(new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 15,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 9, 0),
        });
        sp.Children.Add(new TextBlock { Text = label, VerticalAlignment = VerticalAlignment.Center });

        var b = new Button { Style = (Style)FindResource("GhostButton"), Content = sp, Margin = margin ?? new Thickness(0) };
        b.Click += (_, _) => click();
        return b;
    }

    /// <summary>A box-art tile — Winhanced's AppTileCard anatomy.</summary>
    // 🔴 THE COVER SIZE IS A READING DISTANCE, NOT A TASTE. Winhanced's own
    // library is SIX columns wide - a cover about 250px on a 1920 screen - and
    // that is what makes a title legible from a couch. Our first grid was nine
    // columns: more games per screen, and every wordmark too small to read at
    // 10ft. The home SHELVES keep the small tile (they are a peek strip, and
    // the name is printed beside them), the library grid gets the big one.
    // 🔴 SIZED FOR A COUCH, NOT A DESK. The default is the LIBRARY grid tile;
    // it moved 176x264 -> 224x336 (the same 2:3 box-art ratio) so a cover is
    // legible from across a room, which is the whole premise of this shell.
    /// <summary>
    /// The vertical air a tile needs around it so a FOCUSED tile is not sliced.
    ///
    /// 🔴 THIS IS CLEARANCE, NOT SPACING TASTE, AND IT IS WHY CARDS LOOKED CUT
    /// TOP AND BOTTOM. Focus does two things that both reach outside the tile's
    /// layout box: the whole card scales to 1.09 about its centre (h*0.09/2 per
    /// edge) and the Steam focus plate hangs 16px further out (16*1.09). A
    /// horizontal shelf is the acute case - its ScrollViewer's viewport height
    /// equals the strip height exactly, so anything past it is clipped rather
    /// than merely overlapped, and the plate's rounded corners came out square.
    /// Measured on a render: at h=420 the plate wanted 200..624 and got 224..601.
    ///
    /// It takes the NOMINAL height and does NOT multiply by UiScale: the display
    /// scale is one LayoutTransform over the whole shell now (see ApplyUiScale),
    /// which scales this margin by exactly the same factor it scales the tile.
    /// Multiplying here as well would apply the scale twice.
    /// </summary>
    private double TileBloomV(double h) => h * GroupEffective("tiles") * 0.045 + 18;

    private Button Tile(LibraryGame g, double w = 224, double h = 336)
    {
        w *= GroupEffective("tiles"); h *= GroupEffective("tiles");

        // 🔴 THE SIZE SETTING IS APPLIED HERE, NOT AT THE CALL SITES. Every shelf
        // passes its own w/h, so scaling at the three call sites means three
        // places to forget - and the fourth one added later is the bug. One
        // multiply, at the one place a tile is actually born.

        // "Text only" is a different OBJECT, not a smaller card: a wide, short
        // plate with the name in it. Building it as a stripped-down cover tile
        // was tried and reads as a broken card - a tall empty rectangle with a
        // word in the middle. A list row has to look like a list row.
        if (CardStyle == "text")
        {
            double tw = w * 1.55, th = 76;
            var plate = new Grid { Width = tw, Height = th };
            plate.Clip = new RectangleGeometry(new Rect(0, 0, tw, th), 12, 12);
            plate.Children.Add(new Border { Background = PlateFill() });
            plate.Children.Add(new Border
            {
                BorderBrush = (Brush)FindResource("HairlineBrush"),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(12),
            });
            var line = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(16, 0, 16, 0),
            };
            // The badge means "you can have this in Hebrew", so a translation
            // still in production says so instead of wearing the same mark.
            if (g.Hub is { Available: true }) line.Children.Add(Badge("עברית", accent: true));
            else if (g.Hub is not null) line.Children.Add(Badge(StageLabel(g.Hub.Availability)));
            line.Children.Add(new TextBlock
            {
                Text = g.Name,
                Style = (Style)FindResource("Body"),
                TextTrimming = TextTrimming.CharacterEllipsis,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(g.Hub is not null ? 10 : 0, 0, 0, 0),
                MaxWidth = tw - 60,
            });
            plate.Children.Add(line);
            var tb = new Button { Style = (Style)FindResource("Tile"), Content = plate, Tag = g };
            tb.Click += (_, _) => { Sfx.Play(Sound.Select); OpenBlade(g); };
            tb.GotKeyboardFocus += (_, _) => { _selected = g; SetBackground(g); Sfx.Play(Sound.Navigate); };
            return tb;
        }

        var grid = new Grid { Width = w, Height = h };

        // 🔴 ClipToBounds="True" on the Tile template's Border does NOT clip to
        // its CornerRadius - it clips to the RECTANGULAR bounds, so a cover image
        // painted over a rounded Border still renders with SQUARE corners. Every
        // card in the shell read as a bare rectangle for exactly this reason
        // while the style said radius 12. A rounded RectangleGeometry on the
        // content is the fix, and it is exact here because a tile is a fixed
        // size - no layout pass is needed to know the rect.
        grid.Clip = new RectangleGeometry(new Rect(0, 0, w, h), 12, 12);

        var prof = Profile(g);
        // Order matters: the user's own art wins, then the store's local cache,
        // then the hub cover — so a manual override is never silently ignored.
        var img = LoadImg(prof.CustomBoxArt ?? g.BoxArt ?? g.Hub?.Cover, 260);
        if (img is not null)
        {
            grid.Children.Add(new Image { Source = img, Stretch = Stretch.UniformToFill });
        }
        else
        {
            // 🔴 A COVER-LESS CARD MUST BE BRIGHTER THAN THE BACKDROP, NOT DARKER.
            // The first version plated it #1B222E→#0E141B - a perfectly reasonable
            // dark card, and almost exactly the shell's own background, so between
            // two neighbours with bright art it read as a HOLE in the row rather
            // than as a game. It needs the same anatomy a real cover gets: a plate
            // that separates, a specular rim that catches light, and a glyph so
            // the eye lands on something before it reads the title.
            grid.Children.Add(new Border { Background = PlateFill() });
            grid.Children.Add(new Border
            {
                BorderBrush = (Brush)FindResource("HairlineBrush"),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(12),
            });

            var col = new StackPanel { VerticalAlignment = VerticalAlignment.Center };

            // The game's own executable icon, when there is one - a real mark
            // beats a generic glyph, and it is the only artwork a store-less
            // install actually has. Falls through to the glyph when it has none.
            var exeIcon = Interop.AppIcons.ForFile(GameIconPath(g));
            if (exeIcon is not null)
            {
                var ic = new Image
                {
                    Source = exeIcon,
                    Width = 64, Height = 64,
                    HorizontalAlignment = HorizontalAlignment.Center,
                    Margin = new Thickness(0, 0, 0, 14),
                };
                RenderOptions.SetBitmapScalingMode(ic, BitmapScalingMode.HighQuality);
                col.Children.Add(ic);
            }
            else col.Children.Add(new TextBlock
            {
                Text = GlyphGrid,
                FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
                FontSize = 30,
                Opacity = 0.30,
                TextAlignment = TextAlignment.Center,
                Foreground = (Brush)FindResource("FgPrimary"),
                Margin = new Thickness(0, 0, 0, 12),
            });
            col.Children.Add(new TextBlock
            {
                Text = g.Name,
                Style = (Style)FindResource("Body"),
                TextWrapping = TextWrapping.Wrap,
                TextAlignment = TextAlignment.Center,
                Margin = new Thickness(14, 0, 14, 0),
            });
            grid.Children.Add(col);
        }

        // 🔴 THE BADGE CORNER IS DECIDED BY THE COVERS, NOT BY TASTE. Box art
        // puts its wordmark at the BOTTOM - every cover in this library does -
        // so a bottom badge lands on the game's own title. Top is measurably the
        // free corner. And HorizontalAlignment is LAYOUT space, which RTL
        // mirrors: "Right" here rendered on the visual LEFT, i.e. the far corner
        // from where an RTL eye starts. Left == visual right == the start corner.
        // TWO BADGES DID NOT FIT AND THE OUTER ONE WAS CUT IN HALF. A StackPanel
        // sized to its content and aligned to the edge simply grows past the
        // cover, and the tile clips it - so a game that was both running and
        // carried a stage label showed "|| something" with the label sliced
        // by the corner. A WrapPanel stretched to the cover width has a real
        // boundary to wrap against, and the second badge drops to its own line
        // instead of off the card.
        var badges = new WrapPanel
        {
            Orientation = Orientation.Horizontal,
            VerticalAlignment = VerticalAlignment.Top,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            Margin = new Thickness(8),
        };
        if (g.Hub is { Available: true }) badges.Children.Add(Badge("עברית", accent: true));
        else if (g.Hub is not null) badges.Children.Add(Badge(StageLabel(g.Hub.Availability)));
        // "לא מותקן" ON A GAME THAT IS MERELY PATCHING IS A LIE WITH A CONSEQUENCE.
        // Steam clears the installed bit while an update is downloading, so a
        // library the user has played for a year turns into a wall of "not
        // installed" the morning after a patch day - and the row underneath
        // offers to install it again, which queues a second copy. UpdatePending
        // is already read off the manifest (LibraryScanner); it just never
        // reached the screen.
        if (g.UpdatePending) badges.Children.Add(Badge("מתעדכן", onArt: true));
        else if (!g.Installed) badges.Children.Add(Badge("לא מותקן", onArt: true));
        else if (_sessions?.For(g.Key) is { } s) badges.Children.Add(Badge(s.Suspended ? "מושהה" : "פועל", accent: true));
        // "Art only" means exactly that - the cover, uncovered.
        if (CardStyle != "art") grid.Children.Add(badges);

        // The store mark rides in the cover's far-bottom corner (Winhanced's own
        // placement) so a cross-store shelf is readable at a glance. It only
        // earns its space on a BIG tile - on the small home shelf it would sit
        // on the wordmark and read as dirt. "Manual"/"Hub" are deliberately
        // skipped: those say nothing about WHERE the game came from, and the
        // Hebrew badge already carries the translated fact.
        if (CardStyle != "art" && w >= 200 && g.Source is not (GameSource.Manual or GameSource.Hub))
        {
            grid.Children.Add(new Border
            {
                VerticalAlignment = VerticalAlignment.Bottom,
                HorizontalAlignment = HorizontalAlignment.Right,
                Margin = new Thickness(10),
                Background = new SolidColorBrush(Color.FromArgb(0xB8, 0x0A, 0x0E, 0x14)),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(7, 3, 7, 4),
                Child = new TextBlock
                {
                    Text = g.SourceLabel,
                    FontSize = 11.5,
                    FontWeight = FontWeights.SemiBold,
                    Foreground = (Brush)FindResource("FgSecondary"),
                },
            });
        }

        var b = new Button { Style = (Style)FindResource("Tile"), Content = grid, Tag = g };
        b.Click += (_, _) => { Sfx.Play(Sound.Select); OpenBlade(g); };
        b.GotKeyboardFocus += (_, _) => { _selected = g; SetBackground(g); Sfx.Play(Sound.Navigate); };
        return b;
    }

    /// <summary>The tile that ends a home row: "all games" -> the library tab.</summary>
    /// <summary>
    /// The plate every art-less card sits on. Shared, because "the tile with no
    /// cover" and "the "all games" tile" are the same visual object with
    /// different contents - and the moment they were two literals they drifted
    /// (one read as a card, the other as a hole).
    /// </summary>
    private static LinearGradientBrush PlateFill() => new(
        Color.FromRgb(0x23, 0x26, 0x2E), Color.FromRgb(0x14, 0x1A, 0x24), 90);

    /// <summary>
    /// An executable worth taking an icon from: the store's resolved launch
    /// target first, then the biggest .exe in the install folder.
    ///
    /// 🔴 THE BIGGEST EXE, NOT THE FIRST. A game folder is full of installers,
    /// crash handlers and prerequisite stubs, and they sort before the game
    /// itself as often as not - "biggest" is a crude rule that happens to pick
    /// the actual game almost every time, and a wrong icon here is cosmetic.
    /// </summary>
    private static string? GameIconPath(LibraryGame g)
    {
        try
        {
            if (g.Exe is { Length: > 0 } exe && File.Exists(exe)) return exe;
            if (g.InstallDir is not { Length: > 0 } dir || !Directory.Exists(dir)) return null;
            string? best = null;
            long bestLen = 0;
            foreach (var f in Directory.EnumerateFiles(dir, "*.exe", SearchOption.TopDirectoryOnly))
            {
                var fi = new FileInfo(f);
                string n = fi.Name.ToLowerInvariant();
                if (n.Contains("unins") || n.Contains("setup") || n.Contains("crash") ||
                    n.Contains("redist") || n.Contains("vcredist") || n.Contains("launcher"))
                    continue;
                if (fi.Length > bestLen) { bestLen = fi.Length; best = f; }
            }
            return best;
        }
        catch { return null; }
    }

    private Button MoreTile(double w = 176, double h = 264)
    {
        // Scales with the cards it sits at the end of - a fixed-size "all games"
        // tile beside scaled covers is the one card in the row that is wrong.
        w *= GroupEffective("tiles"); h *= GroupEffective("tiles");
        if (CardStyle == "text") { w *= 1.55; h = 76; }
        var grid = new Grid { Width = w, Height = h };
        grid.Clip = new RectangleGeometry(new Rect(0, 0, w, h), 12, 12);
        grid.Children.Add(new Border { Background = PlateFill() });
        grid.Children.Add(new Border
        {
            BorderBrush = (Brush)FindResource("HairlineBrush"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(12),
        });

        var col = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
        col.Children.Add(new TextBlock
        {
            Text = GlyphGrid,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 34,
            Foreground = (Brush)FindResource("FgSecondary"),
            HorizontalAlignment = HorizontalAlignment.Center,
            Margin = new Thickness(0, 0, 0, 12),
        });
        var cap = Text("כל המשחקים", "Body");
        cap.TextAlignment = TextAlignment.Center;
        col.Children.Add(cap);
        grid.Children.Add(col);

        var b = new Button { Style = (Style)FindResource("Tile"), Content = grid };
        b.Click += (_, _) => { Sfx.Play(Sound.Select); SetTab("library"); };
        return b;
    }

    private GameProfile Profile(LibraryGame g) => _settings.ProfileFor(g.Key)!;

    /// <summary>
    /// Decoded art, kept.
    ///
    /// 🔴🔴 THIS USED TO RE-DECODE EVERY COVER ON EVERY RENDER. A screen is built
    /// from scratch each time it is shown, so switching a filter, changing a tab
    /// or coming back from a game re-read and re-decoded fifty-odd JPEGs from
    /// disk - the same bytes, to the same pixels, for the same tiles. The images
    /// are FROZEN, which means they are safe to share between every element and
    /// every thread that asks, so the only reason not to keep them was that
    /// nobody had.
    ///
    /// Keyed by path AND decode width: the same cover is legitimately decoded at
    /// a tile size and again at a blade size, and handing the small one to the
    /// big surface would show a soft cover on the one screen that fills itself
    /// with it.
    /// </summary>
    private static readonly Dictionary<string, BitmapImage> ImgCache = new();

    /// <summary>
    /// A bound, so a long session browsing a large library cannot grow the cache
    /// without limit. Cleared wholesale rather than by age: the cost of a cold
    /// re-decode is one frame, and an eviction policy is more machinery than the
    /// problem deserves.
    /// </summary>
    private const int ImgCacheMax = 400;

    private static BitmapImage? LoadImg(string? path, int decodeWidth = 0)
    {
        if (string.IsNullOrWhiteSpace(path)) return null;
        // A catalog reference may be an https URL (the hub's covers) rather than
        // a local file. ArtCache mirrors those to disk and returns null until
        // the first fetch lands, so this stays a pure file loader.
        path = ArtCache.Resolve(path);
        if (string.IsNullOrWhiteSpace(path)) return null;

        string key = decodeWidth + "|" + path;
        lock (ImgCache)
            if (ImgCache.TryGetValue(key, out var hit)) return hit;

        try
        {
            if (!File.Exists(path)) return null;
            var bi = new BitmapImage();
            bi.BeginInit();
            bi.UriSource = new Uri(path, UriKind.Absolute);
            // OnLoad: decode now and release the file, so art can never lock a
            // Steam cache file. DecodePixelWidth keeps a 4K hero off the heap.
            bi.CacheOption = BitmapCacheOption.OnLoad;
            if (decodeWidth > 0) bi.DecodePixelWidth = decodeWidth;
            bi.EndInit();
            bi.Freeze();

            lock (ImgCache)
            {
                if (ImgCache.Count >= ImgCacheMax) ImgCache.Clear();
                ImgCache[key] = bi;
            }
            return bi;
        }
        catch { return null; }
    }

    /// <summary>Forget one decoded image - for when the FILE changed under us
    /// (a custom cover picked in the art picker, or a fresh mirror landing).</summary>
    private static void ForgetImg(string? path)
    {
        if (string.IsNullOrWhiteSpace(path)) return;
        lock (ImgCache)
            foreach (var k in ImgCache.Keys.Where(k => k.EndsWith("|" + path, StringComparison.OrdinalIgnoreCase)).ToList())
                ImgCache.Remove(k);
    }

    // =====================================================================
    //  background + bloom
    // =====================================================================

    private bool _bgUseA = true;
    private string? _bgPath;
    private Image? _bgLive;
    private DispatcherTimer? _artRefresh;

    /// <summary>
    /// How strongly the hero art shows through, per view.
    ///
    /// On HOME the art IS the screen - Winhanced gives the focused game the full
    /// frame and relies on the scrim for legibility. Every other tab is a dense
    /// grid or a form, so the art drops back to a texture instead of competing
    /// with it. The scrims do the legibility work either way; this is purely
    /// "how much game is behind the content".
    /// </summary>
    private double ArtStrength => _tab == "home" ? 1.00 : 0.42;

    /// <summary>Re-apply the per-view strength after a tab change, without reloading the bitmap.</summary>
    private void RefreshArtStrength()
    {
        double to = ArtStrength;

        // 🔴 THE HEADER FADE HAS TO DIM WITH THE ART IT PROTECTS. That band is
        // there for ONE job: keep the tab labels legible when bright key art
        // runs under them. On a grid page the art is already down to 0.42, so a
        // fade left at full strength is dark stacked on dark — it stops reading
        // as "the art receding" and starts reading as a grey bar welded across
        // the top of the window, washing out the very labels it exists to
        // protect. Its strength is the art's strength; that is the whole rule.
        double hf = 0.20 + 0.80 * to;
        if (!_settings.AnimationsEnabled) { HeaderFade.BeginAnimation(OpacityProperty, null); HeaderFade.Opacity = hf; }
        else HeaderFade.BeginAnimation(OpacityProperty,
                 new DoubleAnimation(HeaderFade.Opacity, hf, (Duration)FindResource("DurSlow")));

        if (_bgLive is null || _bgLive.Source is null) return;
        if (!_settings.AnimationsEnabled) { _bgLive.BeginAnimation(OpacityProperty, null); _bgLive.Opacity = to; return; }
        _bgLive.BeginAnimation(OpacityProperty,
            new DoubleAnimation(_bgLive.Opacity, to, (Duration)FindResource("DurSlow")));
    }

    private void SetBackground(LibraryGame g)
    {
        // 🔴 HeroBlur FIRST turned every background into a smear. Steam ships
        // library_hero_blur.jpg for widgets that put text directly on top of it;
        // the shell already has its own directional scrim, so blurring underneath
        // it means paying twice and rendering art nobody can recognise. Sharp
        // hero first, the blurred copy only as a fallback.
        // A non-Steam title has no hero at all, and an empty 1920x1080 of flat
        // black is the worst thing the home screen can show. Falling through to
        // the portrait means the backdrop is heavily cropped - which is fine,
        // because behind the scrim it reads as the game's ambient colour, and
        // "the right colour" beats "nothing" every time.
        string? path = Profile(g).CustomHeroArt ?? g.HeroArt ?? g.HeroBlur ?? g.Header;

        // 🔴 A PORTRAIT IS NOT A BACKDROP. A non-Steam title has no hero at all,
        // and flat black is the worst thing the home screen can show - but a
        // 600x900 cover stretched to fill 1920x1080 renders its wordmark two feet
        // tall, which is worse. It is a legitimate SOURCE and an illegitimate
        // IMAGE, so it comes in as ambience instead: decoded at 24px and let the
        // upscale do the blurring. That is free (no per-frame BlurEffect over a
        // full-screen image during a crossfade) and it is what the art is
        // actually good for here - the game's colour, not its logo.
        bool ambient = path is null;
        if (ambient) path = Profile(g).CustomBoxArt ?? g.BoxArt ?? g.Hub?.Cover;

        // Already showing exactly this art.
        if (path == _bgPath && _bgLive?.Source is not null) return;

        // 🔴 THE BACKDROP IS AMBIENCE, SO EVERY SOURCE COMES IN SOFT - not just
        // the box-art fallback. A hero decoded at 1600 is a sharp photograph
        // behind the UI: it competes with the tiles for the eye, its own detail
        // fights the text, and the shell's dark-blue ground stops reading as the
        // ground at all. Decoding small and letting the upscale do the blurring
        // keeps the game's COLOUR and composition while the blue shows through
        // it - and it costs nothing per frame, unlike a full-screen BlurEffect
        // that would have to re-run during every crossfade.
        // 🔴 480, NOT 200. Softening the backdrop is right; destroying it is
        // not. Steam's library_hero.jpg is 3840x1240, so decoding it at 200 is a
        // ~19x upscale - far past "soft", into a smear with no composition left,
        // which is exactly why the backdrop stopped being recognisable as the
        // game and started looking like the cover. 480 is still an 8x upscale
        // (ambience, not a photograph) while keeping the shapes that make it
        // THAT game's backdrop. The box-art fallback stays at 24: it is a
        // portrait being used as colour, and it has no composition worth saving.
        // 🔴 DECODING SMALL IS NOT BLURRING. A 3840x1240 hero decoded to 480 and
        // then stretched back over 1920 is a 4x UPSCALE of a real image: every
        // edge in it survives as a hard, stair-stepped edge, which is exactly the
        // "bad JPEG / blocky pixels" look and nothing like a blur. Low resolution
        // preserves structure and destroys detail; a blur destroys structure and
        // is what turns a photograph into the regions of colour that are in it.
        // So the source is decoded big enough to have real colour (640) and the
        // softening is done by an actual Gaussian below, instead of being faked
        // by throwing pixels away.
        var img = LoadImg(path, ambient ? 24 : 640);

        // 🔴 NEVER MEMOIZE A MISS. A remote hero resolves to null until ArtCache
        // has mirrored it — and the old guard cached that null in _bgPath, so
        // when the image finally landed this method early-returned and the art
        // could never appear. That is exactly why the home screen stayed flat
        // while every tile around it had art.
        //
        // On a miss we also keep whatever is already on screen: the previous
        // game's backdrop is a better frame than a sudden empty panel while this
        // one is still downloading, and it is what Winhanced does between cards.
        if (img is null) return;

        _bgPath = path;
        var target = _bgUseA ? BgB : BgA;
        var other = _bgUseA ? BgA : BgB;
        _bgUseA = !_bgUseA;

        // Fant on the upscaled thumbnail: without it a 48px source scaled to
        // 1920 is visibly BLOCKY, which reads as a broken image rather than blur.
        // Fant on BOTH now: every source is upscaled from a small decode, and
        // without it the result is blocky rather than blurred.
        RenderOptions.SetBitmapScalingMode(target, BitmapScalingMode.Fant);

        target.Source = img;
        _bgLive = target;
        double to = ArtStrength;

        if (!_settings.AnimationsEnabled)
        {
            target.BeginAnimation(OpacityProperty, null);
            other.BeginAnimation(OpacityProperty, null);
            target.Opacity = to;
            other.Opacity = 0;
            return;
        }
        var d = (Duration)FindResource("DurSlow");
        target.BeginAnimation(OpacityProperty, new DoubleAnimation(target.Opacity, to, d));
        other.BeginAnimation(OpacityProperty, new DoubleAnimation(other.Opacity, 0, d));
    }

    /// <summary>
    /// Winhanced's BloomCanvas, in the one form a WPF window can do cheaply:
    /// two large static radial glows tinted with the system accent. Static on
    /// purpose — an animated full-screen blur is the documented FPS killer.
    /// </summary>
    /// <summary>
    /// The ambient backdrop, ported from the desktop launcher's own.
    ///
    /// The launcher does this in CSS: two radial-gradient blobs in the accent
    /// (`.accent-bg::before` / `::after`) that slowly DRIFT - a 26s and a 32s
    /// ease-in-out translate+scale loop - plus a "colourful" mode that swaps the
    /// single accent for a multi-colour wash and cycles its hue. Two different
    /// engines, so none of that CSS can be shared; this is the same design
    /// rebuilt as XAML animations.
    ///
    /// 🔴 ONLY transform AND GradientStop.Color ARE ANIMATED. That is the
    /// property the launcher's own comment calls out as the reason its version
    /// is GPU-cheap: no blur, no filter, nothing that forces a re-raster of a
    /// full-screen layer every frame. A BlurEffect here would cost the whole
    /// window every single frame, forever, behind everything else the shell
    /// draws - the exact trap the launcher already documented for QtWebEngine.
    ///
    /// The drift is killed when animations are off, which is both the
    /// accessibility answer and the weak-hardware one - the same rule the CSS
    /// applies under reduce-motion.
    /// </summary>
    private void BuildBloom()
    {
        Bloom.Children.Clear();
        var accent = (Color)FindResource("AccentColor");
        bool rainbow = _settings.AmbientStyle != "accent";   // colourful is the default

        // The launcher's colourful mode names these two exactly: a cyan blob and
        // a magenta one, which is what makes the wash read as more than a tint.
        Color a1 = rainbow ? Color.FromRgb(0x00, 0xFF, 0xE0) : accent;
        Color a2 = rainbow ? Color.FromRgb(0xFF, 0x4D, 0x8D) : accent;

        Ellipse Glow(double x, double y, double r, byte alpha, Color c)
        {
            var stop = new GradientStop(Color.FromArgb(alpha, c.R, c.G, c.B), 0);
            var brush = new RadialGradientBrush
            {
                GradientStops =
                {
                    stop,
                    // 0.7, matching the launcher's `transparent 70%`: the blob has
                    // to fade out well inside its own box or its edge shows as a
                    // circle instead of as light.
                    new GradientStop(Color.FromArgb(0, c.R, c.G, c.B), 0.70),
                },
            };
            var e = new Ellipse
            {
                Width = r, Height = r,
                Fill = brush,
                IsHitTestVisible = false,
                RenderTransformOrigin = new Point(0.5, 0.5),
                Tag = stop,
                // The blob DRIFTS and BREATHES constantly and re-colours slowly.
                // Cached, the drift and the scale are a blit of an existing
                // surface and only a colour change re-rasterises the gradient -
                // so the expensive work now happens at the hue animation's 10fps
                // instead of at every frame of the motion.
                CacheMode = new BitmapCache(),
            };
            Canvas.SetLeft(e, x); Canvas.SetTop(e, y);
            Bloom.Children.Add(e);
            return e;
        }

        var one = Glow(-260, -320, 1100, 46, a1);
        var two = Glow(SystemParameters.PrimaryScreenWidth - 520,
                       SystemParameters.PrimaryScreenHeight - 420, 900, 34, a2);

        if (!_settings.AnimationsEnabled) return;

        // The CSS keyframes state 0% and 100% identically with the extreme at
        // 50%, which is an AutoReverse over HALF the stated period - so a 26s
        // loop is a 13s animation that plays back.
        Drift(one, 1100, -0.06, 0.09, 1.00, 1.14, 13);
        Drift(two,  900,  0.08, -0.07, 1.05, 1.16, 16);

        if (rainbow)
        {
            HueCycle(one, 46);
            HueCycle(two, 34);
        }
    }

    /// <summary>One blob's translate+scale loop. The offsets are fractions of the
    /// blob's own size, exactly as the CSS percentages are.</summary>
    private static void Drift(Ellipse e, double size, double dx, double dy,
                              double from, double to, double seconds)
    {
        var scale = new ScaleTransform(from, from);
        var move = new TranslateTransform();
        e.RenderTransform = new TransformGroup { Children = { scale, move } };

        var ease = new SineEase { EasingMode = EasingMode.EaseInOut };
        var d = new Duration(TimeSpan.FromSeconds(seconds));

        DoubleAnimation An(double f, double t)
        {
            var a = new DoubleAnimation(f, t, d)
            {
                AutoReverse = true,
                RepeatBehavior = RepeatBehavior.Forever,
                EasingFunction = ease,
            };
            // 🔴 AN AMBIENT ANIMATION MUST NOT RUN AT DISPLAY RATE. This drift
            // takes THIRTEEN SECONDS to cross the screen; at 60fps that is 780
            // frames to move a blob a few hundred pixels, and every one of them
            // costs a composite of a full-screen layer. Nothing about a background
            // wash is improved by the other 45 frames a second - the motion is
            // below the rate at which anyone can see a step - and the budget it
            // frees belongs to the game the shell is about to launch.
            Timeline.SetDesiredFrameRate(a, 20);
            return a;
        }

        scale.BeginAnimation(ScaleTransform.ScaleXProperty, An(from, to));
        scale.BeginAnimation(ScaleTransform.ScaleYProperty, An(from, to));
        move.BeginAnimation(TranslateTransform.XProperty, An(0, dx * size));
        move.BeginAnimation(TranslateTransform.YProperty, An(0, dy * size));
    }

    /// <summary>The colourful mode's slow hue cycle. The launcher rotates the hue
    /// with a CSS filter; WPF has no cheap equivalent, so the gradient's own stop
    /// walks the same wheel instead - same effect, and still no re-raster.</summary>
    private static void HueCycle(Ellipse e, byte alpha)
    {
        if (e.Tag is not GradientStop stop) return;
        Color C(byte r, byte g, byte b) => Color.FromArgb(alpha, r, g, b);

        var k = new ColorAnimationUsingKeyFrames
        {
            Duration = new Duration(TimeSpan.FromSeconds(22)),
            RepeatBehavior = RepeatBehavior.Forever,
        };
        // 🔴 THE MOST EXPENSIVE FRAME IN THE SHELL. Re-colouring a gradient STOP
        // invalidates the whole brush, so every frame re-rasterises a 1100px
        // radial gradient - measured at roughly half a core when it ran at the
        // display's rate. A 22-second hue walk does not need 60 samples a second;
        // at 10 the step between two frames is a fraction of a percent of the
        // wheel, which is invisible, and the cost drops with the frame count.
        Timeline.SetDesiredFrameRate(k, 10);
        // The launcher's own conic stops, in order, closing back on the first.
        var wheel = new[]
        {
            C(0x00, 0xFF, 0xE0), C(0x7C, 0x3A, 0xED), C(0xFF, 0x4D, 0x8D),
            C(0xFF, 0xF7, 0x00), C(0x22, 0xC5, 0x5E), C(0x00, 0xFF, 0xE0),
        };
        for (int i = 0; i < wheel.Length; i++)
            k.KeyFrames.Add(new LinearColorKeyFrame(wheel[i],
                KeyTime.FromPercent(i / (double)(wheel.Length - 1))));

        stop.BeginAnimation(GradientStop.ColorProperty, k);
    }

    private string AmbientStyleLabel() =>
        _settings.AmbientStyle == "accent" ? "צבע המבטא" : "צבעוני";

    private void PickAmbientStyle() => Picker(
        "רקע דינמי",
        "האור שנע אט מאחורי המסך. התנועה עצמה כבויה כשהאנימציות כבויות.",
        new[]
        {
            ("rainbow", "צבעוני", "רחיצה רב-צבעית שמחליפה גון לאט · ברירת המחדל"),
            ("accent",  "צבע המבטא", "שני כתמי אור בצבע שבחרת"),
        },
        _settings.AmbientStyle == "accent" ? "accent" : "rainbow",
        key =>
        {
            _settings.AmbientStyle = key;
            _settings.Save();
            BuildBloom();
            RenderTab();
            ShowToast($"רקע דינמי: {AmbientStyleLabel()}");
        });

    // =====================================================================
    //  blade — game detail
    // =====================================================================

    private void OpenBlade(LibraryGame g)
    {
        _selected = g;
        _settings.LastGameKey = g.Key;
        _settings.SaveThrottled();
        SetBackground(g);

        _layer = "blade";
        ResetNav();
        _navViewStart = 0;
        Blade.Children.Clear();
        Blade.Visibility = Visibility.Visible;

        // 🔴 THE CONTENT IS A COLUMN ON THE READING SIDE, NOT A FULL-WIDTH SHEET.
        // Winhanced's detail panel keeps the copy in a band and lets the hero
        // fill the rest; spanning the frame made a 1700px-wide row whose label
        // and value ended up a screen apart.
        // The host Grid is pinned LTR so its scrim gradient cannot mirror, so the
        // panel has to flip itself back - otherwise every Hebrew row inside it
        // would lay out left-to-right.
        var panel = new Grid { Margin = new Thickness(96, 64, 96, 64), Width = CardWidth(900),
                               FlowDirection = FlowDirection.RightToLeft,
                               HorizontalAlignment = HorizontalAlignment.Right };
        panel.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        panel.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        // header: logo or title
        var head = new StackPanel();
        var logo = LoadImg(Profile(g).CustomLogo ?? g.Logo, 460);
        if (logo is not null)
            // 🔴 HorizontalAlignment IS LAYOUT SPACE, AND RTL MIRRORS IT.
            // "Right" put the logo on the visual LEFT, on the far side of the
            // screen from every other thing on this panel. Left == the reading
            // start here, which is where a title belongs.
            head.Children.Add(new Image { Source = logo, MaxHeight = 108, HorizontalAlignment = HorizontalAlignment.Left });
        else
            head.Children.Add(Text(g.Name, "H1"));

        var meta = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 12, 0, 0) };
        meta.Children.Add(Badge(g.SourceLabel));
        if (g.Hub is { Available: true }) meta.Children.Add(Badge("תרגום עברי", accent: true));
        else if (g.Hub is not null) meta.Children.Add(Badge("תרגום עברי · " + StageLabel(g.Hub.Availability)));
        if (g.SizeBytes > 0) meta.Children.Add(Badge(Ltr(g.SizeLabel)));
        if (g.LastPlayed is { } lp) meta.Children.Add(Badge($"שוחק {lp:dd/MM/yyyy}"));
        var prof = Profile(g);
        if (prof.PlaySeconds > 60) meta.Children.Add(Badge($"{prof.PlaySeconds / 3600}ש׳ {(prof.PlaySeconds % 3600) / 60}ד׳"));
        // ^ Hebrew unit letters, so this one is genuinely RTL and must NOT be fenced.
        head.Children.Add(meta);
        Grid.SetRow(head, 0);
        panel.Children.Add(head);

        // actions
        var body = new StackPanel { Margin = new Thickness(0, 26, 0, 0) };
        var row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 22) };

        var session = _sessions?.For(g.Key);
        bool hasPlay = true;
        if (session is { Suspended: true })
            row.Children.Add(Nav(CTA(GlyphPlay, "חידוש", () => ResumeSession(session))));
        else if (session is not null)
            row.Children.Add(Nav(CTA(GlyphPause, "השהיה", () => SuspendSession(session))));
        else if (g.Installed && g.Source != GameSource.Hub)
            row.Children.Add(Nav(CTA(GlyphPlay, "שחק", () => PlayGame(g))));
        else
            hasPlay = false;

        row.Children.Add(Nav(Ghost(prof.Favorite ? GlyphCheck : "",
            prof.Favorite ? "מועדף" : "הוסף למועדפים",
            () => { prof.Favorite = !prof.Favorite; Save(); SortLibrary(); OpenBlade(g); },
            new Thickness(12, 0, 0, 0))));

        // A RUNNING GAME HAD NO EXIT FROM THIS SHELL AT ALL. Play, suspend and
        // resume were all here; ENDING the thing was not - so a parked game the
        // user had finished with could only be dealt with by resuming it and
        // alt-tabbing away to quit, which is exactly the desktop trip this
        // console exists to remove. It sits AFTER favourites so focus can never
        // land on it first, and it asks before it acts: a suspended game holds
        // every byte of its unsaved progress in the memory this button frees.
        if (session is not null)
            row.Children.Add(Nav(Ghost(GlyphStop, "\u05E1\u05D2\u05D5\u05E8 \u05D0\u05EA \u05D4\u05DE\u05E9\u05D7\u05E7",
                () => Confirm(
                    $"\u05DC\u05E1\u05D2\u05D5\u05E8 \u05D0\u05EA {g.Name}?",
                    session.Suspended
                        ? "\u05D4\u05DE\u05E9\u05D7\u05E7 \u05DE\u05D5\u05E9\u05D4\u05D4 - \u05E1\u05D2\u05D9\u05E8\u05EA\u05D5 \u05EA\u05E4\u05E0\u05D4 \u05D0\u05EA \u05D4\u05D6\u05D9\u05DB\u05E8\u05D5\u05DF \u05E9\u05D4\u05D5\u05D0 \u05DE\u05D7\u05D6\u05D9\u05E7, \u05D0\u05D1\u05DC \u05DB\u05DC \u05DE\u05D4 \u05E9\u05DC\u05D0 \u05E0\u05E9\u05DE\u05E8 \u05D1\u05EA\u05D5\u05DB\u05D5 \u05D9\u05D0\u05D1\u05D3."
                        : "\u05D4\u05DE\u05E9\u05D7\u05E7 \u05E4\u05D5\u05E2\u05DC \u05E2\u05DB\u05E9\u05D9\u05D5. \u05DB\u05DC \u05DE\u05D4 \u05E9\u05DC\u05D0 \u05E0\u05E9\u05DE\u05E8 \u05D1\u05EA\u05D5\u05DB\u05D5 \u05D9\u05D0\u05D1\u05D3.",
                    "\u05E1\u05D2\u05D5\u05E8", destructive: true,
                    () => CloseSession(session),
                    back: () => OpenBlade(g)),
                new Thickness(12, 0, 0, 0))));

        body.Children.Add(row);

        if (g.Hub is { Tagline.Length: > 0 })
            body.Children.Add(Text(g.Hub.Tagline, "Body", margin: new Thickness(0, 0, 0, 18)));

        if (g.InstallDir.Length > 0)
            body.Children.Add(Nav(RowButton(GlyphFolder, "פתח תיקייה", g.InstallDir,
                () => Storage.OpenFolder(g.InstallDir))));

        // 🔴 THE TRANSLATION IS INSTALLED FROM HERE NOW, not "in the desktop app".
        // This row used to be a REPORT, which meant the one thing this whole
        // product exists for was the one thing the console could not do - the
        // user had to leave, and leaving is exactly what the separation rule
        // forbids. ModBridge runs the desktop launcher headlessly, so the
        // appliers, backups and purchase gate are unchanged; only the front end
        // is new. An older launcher has no --mod switch, so the row falls back
        // to reporting rather than offering a button that would do nothing.
        if (g.Hub is not null)
        {
            if (ModBridge.Available())
            {
                bool on = g.Hub.Installed;

                // 🔴 A PAID TRANSLATION NEEDS A WAY TO BUY IT, or the install
                // button is a dead end: the applier's purchase gate refuses,
                // and the user is left holding an error with nothing to press.
                // The catalog already carries the price, so the row can say so
                // BEFORE the click rather than after.
                // 🔴 WHEN THERE IS NO "שחק", THIS ROW IS THE PANEL'S PRIMARY
                // ACTION. A title that is not installed on this machine cannot
                // be played, so the blade opened with focus on "add to
                // favourites" — bookkeeping — while the one thing this shell
                // exists to do sat below it, unhighlighted. Nominating it only
                // when Play is absent keeps Play primary everywhere else.
                if (!hasPlay) _navPreferred = _nav.Count;

                if (!on && !g.Hub.Available)
                    // Not a button that installs something: a statement of where
                    // the translation is, and a way to follow it on the site.
                    body.Children.Add(Nav(RowButton(GlyphInfo, "תרגום עברי",
                        StageLabel(g.Hub.Availability) + " · עדיין לא ניתן להתקנה",
                        () =>
                        {
                            Sfx.Play(Sound.Select);
                            try
                            {
                                Process.Start(new ProcessStartInfo(
                                    $"https://hebrew-translation-hub.com/games/{g.Hub!.Id}")
                                { UseShellExecute = true });
                                // 🔴 AND GET OUT OF THE WAY - the same lesson the
                                // desktop hand-off already learned. A browser
                                // opening BEHIND a maximised borderless shell is
                                // a browser the user never sees: the toast says
                                // the page opened and the screen says nothing
                                // happened.
                                WindowState = WindowState.Minimized;
                                ShowToast("דף המשחק נפתח בדפדפן");
                            }
                            catch { ShowToast("פתיחת הדפדפן נכשלה"); }
                        })));
                else if (!on && g.Hub.PriceCents > 0)
                    body.Children.Add(Nav(RowButton(GlyphGlobe, "תרגום עברי",
                        $"בתשלום - {Price(g.Hub.PriceCents)}. פתיחת דף הרכישה באתר",
                        () =>
                        {
                            Sfx.Play(Sound.Select);
                            try
                            {
                                Process.Start(new ProcessStartInfo(
                                    $"https://hebrew-translation-hub.com/games/{g.Hub!.Id}")
                                { UseShellExecute = true });
                                // 🔴 AND GET OUT OF THE WAY - the same lesson the
                                // desktop hand-off already learned. A browser
                                // opening BEHIND a maximised borderless shell is
                                // a browser the user never sees: the toast says
                                // the page opened and the screen says nothing
                                // happened.
                                WindowState = WindowState.Minimized;
                                ShowToast("דף הרכישה נפתח בדפדפן");
                            }
                            catch { ShowToast("פתיחת הדפדפן נכשלה"); }
                        })));
                else
                    body.Children.Add(Nav(RowButton(on ? GlyphCheck : GlyphDownload, "תרגום עברי",
                        on ? "מותקן - לחצו כדי להסיר" : "זמין להתקנה",
                        () => RunMod(g, on ? "remove" : "install"))));

                // 🔴 THE BETA OPT-IN IS PER MOD, SO IT BELONGS ON THE MOD.
                // The desktop launcher keeps a global switch AND a per-game
                // override that outranks it, because "I want early builds" is
                // rarely true of a user's whole library - it is true of the one
                // game they are helping test. A single global toggle buried in
                // Settings cannot express that, so the override lives here,
                // next to the translation it governs.
                //
                // Three states, so it CYCLES rather than toggles: following the
                // global switch is not the same as being off, and collapsing
                // them would silently pin a game to "no betas" the first time
                // anyone touched the row.
                if (ShellBridge.Available() && _beta is not null && g.Hub is not null)
                {
                    string gid = g.Hub.Id;
                    bool? ov = _beta.Overrides.TryGetValue(gid, out bool v) ? v : null;
                    string label = ov switch
                    {
                        true => "מקבל גרסאות בטא",
                        false => "לא מקבל גרסאות בטא",
                        _ => _beta.Channel ? "לפי ההגדרה הכללית · מקבל בטא"
                                           : "לפי ההגדרה הכללית · לא מקבל בטא",
                    };
                    body.Children.Add(Nav(RowButton(GlyphChip, "גרסאות בטא למשחק הזה", label,
                        () => _ = CycleBetaAsync(g, gid, ov))));
                }

                // The in-game text language, for the titles that expose one.
                // It is a separate decision from "is the mod installed": the
                // files can be in place while the game is still set to English,
                // and that combination is exactly what looks like a failed
                // install to someone who just pressed Play.
                if (on)
                {
                    var langRow = RowButton(GlyphGlobe, "שפת המשחק",
                        _langLabel.TryGetValue(g.Key, out var lbl) ? lbl : "בודק…",
                        () => CycleLanguage(g));
                    _langDetail = DetailOf(langRow);
                    body.Children.Add(Nav(langRow));

                    // 🔴 THE REPAIR PATH. When an install goes wrong the desktop
                    // app offers "clear the translation cache"; without it here
                    // the console is a dead end - the one place a 10ft shell must
                    // never be, because the user has no keyboard to go around it.
                    body.Children.Add(Nav(RowButton(GlyphDelete, "ניקוי מטמון התרגום",
                        "מסיר את התרגום ומוחק את הקבצים השמורים. להתקנה חוזרת אם משהו השתבש",
                        () => Confirm("לנקות את מטמון התרגום?",
                                      "התרגום יוסר מהמשחק והקבצים השמורים יימחקו. אפשר להתקין שוב אחר כך.",
                                      "נקה", true, () => StartMod(g, "clearcache")),
                        glyphBrush: (Brush)FindResource("Destructive"))));
                    // Read it once per game. RefreshLanguage re-opens the blade
                    // when the answer lands, so an unconditional call here would
                    // re-enter itself for as long as the panel stayed open.
                    if (!_langLabel.ContainsKey(g.Key)) RefreshLanguage(g);
                }
            }
            else
            {
                body.Children.Add(Card(InfoRow(GlyphCheck, "תרגום עברי",
                    g.Hub.Installed
                        ? "מותקן. להתקנה ולעדכון נדרשת גרסה חדשה יותר של הלאנצ׳ר"
                        : "זמין. להתקנה נדרשת גרסה חדשה יותר של הלאנצ׳ר")));
            }
        }

        // 🔴 THE SCANNER FINDS APPS, NOT ONLY GAMES. Steam ships ShareX, DSX,
        // Wallpaper Engine and Borderless Gaming in the same list as Red Dead -
        // Winhanced's own hidden list is exactly this (Windows Security,
        // WinAppRuntime). Hiding is reversible and harms nothing, so it asks no
        // question; the way BACK lives in Settings, where you go when you notice
        // something is missing.
        body.Children.Add(Nav(RowButton(GlyphHide, "הסתר מהספרייה",
            "לא ייספר ולא יופיע בשום מסך. אפשר להחזיר מהגדרות \u2190 ספרייה",
            () =>
            {
                var prof = _settings.ProfileFor(g.Key);
                if (prof is not null) prof.Hidden = true;
                Save();
                SortLibrary();
                // The BLADE is its own layer, not a dialog - DismissDialog would
                // clear an empty host and leave the panel standing over a library
                // that had already re-rendered underneath it.
                CloseBlade();
                ShowToast($"{g.Name} הוסתר");
            })));

        // Collections — Steam Big Picture's library concept, kept local.
        {
            var mine = _settings.Collections.Where(c => c.Keys.Contains(g.Key))
                                            .Select(c => c.Name).ToList();
            body.Children.Add(Nav(RowButton(GlyphCollection, "אוספים",
                mine.Count > 0 ? string.Join(" · ", mine) : "המשחק לא נמצא באף אוסף",
                () => OpenCollections(g))));
        }

        // Launch options - Winhanced's Game Options -> General (Launch
        // Arguments, Executable Path). Not a power-user nicety here: this
        // project's own Watch Dogs 2 translation only renders when the game is
        // started with -eac_launcher, and until now there was nowhere to say so.
        //
        // Installed titles only: a catalog entry that is not on this machine has
        // nothing to launch, so the row could only ever report "no executable".
        if (g.Installed)
        {
            var p = Profile(g);
            string state = (p.LaunchArgs, p.CustomExe) switch
            {
                ({ Length: > 0 } a, { Length: > 0 })  => $"{Ltr(a)} · קובץ הפעלה מותאם",
                ({ Length: > 0 } a, _)                => Ltr(a),
                (_, { Length: > 0 })                  => "קובץ הפעלה מותאם",
                _                                     => "ארגומנטים וקובץ הפעלה - לא הוגדרו",
            };
            body.Children.Add(Nav(RowButton(GlyphSettings, "אפשרויות הפעלה", state,
                () => OpenLaunchOptions(g))));
        }

        // Choose Artwork. Offered for every game, installed or not - a catalog
        // entry with a poor cover is exactly the one worth replacing, and the
        // custom image is stored on the profile, so it survives installing the
        // game later.
        {
            var p = Profile(g);
            int set = (p.CustomBoxArt is { Length: > 0 } ? 1 : 0)
                    + (p.CustomHeroArt is { Length: > 0 } ? 1 : 0)
                    + (p.CustomLogo    is { Length: > 0 } ? 1 : 0);
            body.Children.Add(Nav(RowButton(GlyphImage, "בחירת תמונות",
                set == 0 ? "עטיפה, רקע ולוגו - תמונות ברירת המחדל"
                         : $"{set} מתוך 3 הוחלפו בתמונה משלכם",
                () => OpenArtwork(g))));
        }

        // Storage - measured on demand, cancellable.
        //
        // 🔴 ONLY WHEN THERE IS A FOLDER TO MEASURE. The row used to render for
        // every game and sit on "מחשב…" forever whenever InstallDir was empty,
        // because MeasureAsync is (correctly) never started for a title that is
        // not on this machine. A spinner that can never resolve is worse than no
        // row: it reads as a hang in the shell rather than as "nothing here".
        if (g.InstallDir.Length > 0)
        {
            var sizeRow = RowButton(GlyphChip, "מקום בכונן",
                g.SizeBytes > 0 ? Ltr(g.SizeLabel) : "מחשב…", () => { });
            body.Children.Add(Nav(sizeRow));
            if (g.SizeBytes <= 0) MeasureAsync(g, sizeRow);
        }

        if (g.Installed && g.Source is not (GameSource.Hub or GameSource.Manual))
            body.Children.Add(Nav(RowButton(GlyphDelete, "הסרה",
                "מועבר לחנות שהתקינה את המשחק - כדי שהיא לא תישאר עם רישום שגוי",
                // 🔴 THE SAME RULE AS THE POWER MENU: a click that can destroy
                // something asks first. Uninstall hands off to the store, which
                // runs its own confirmation - but by then the user has already
                // been thrown out of the console into another app, and "I only
                // wanted to see how big it was" is a real click on a couch.
                () => Confirm(
                    $"להסיר את {g.Name}?",
                    "ביג לאנץ' יפתח את " + g.SourceLabel + " כדי לבצע את ההסרה שם. " +
                    "המשחק והשמירות שלו יימחקו מהמחשב, ותצטרך להוריד אותו מחדש כדי לשחק.",
                    "פתח את החנות", destructive: true,
                    () => { if (!Storage.Uninstall(g)) ShowToast("לא נמצאה דרך הסרה"); },
                    back: () => OpenBlade(g)),
                glyphBrush: (Brush)FindResource("Destructive"))));

        // The action list sits on the same glass as every other floating surface.
        //
        // 🔴 IT WAS AN OPAQUE PLATE FOR A GOOD REASON, AND THAT REASON IS GONE.
        // The blade's own gradient stops around 96%, and a row is a 6% white
        // wash - so the library used to read straight through the list, with a
        // Steam logo sitting visibly inside the word "הסרה". The answer then was
        // to make the plate nearly opaque. The answer now is that opening the
        // blade BLURS the shell behind it (UpdateFrost), so there is no legible
        // artwork left to bleed through and the surface can be actual glass.
        var plate = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Padding = new Thickness(18, 16, 18, 8),
            Child = body,
        };

        var scroll = Scroller(plate);
        Grid.SetRow(scroll, 1);
        panel.Children.Add(scroll);
        Blade.Children.Add(panel);

        // ⚠ The legend must list what THIS layer really does. It still advertised
        // "X screenshot" after X became the quick menu - and the quick menu is
        // view-layer only, so the one hint on screen pointed at a dead button.
        SetHints(("A", "בחירה"), ("B", "סגירה"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusFirst());
        Animate(panel);
    }

    private async void MeasureAsync(LibraryGame g, Button row)
    {
        _sizeCts?.Cancel();
        _sizeCts = new CancellationTokenSource();
        var ct = _sizeCts.Token;
        try
        {
            long n = await Storage.FolderSizeAsync(g.InstallDir, ct);
            if (ct.IsCancellationRequested) return;
            g.SizeBytes = n;
            if (row.Content is Grid grid && grid.Children.Count > 1 &&
                grid.Children[1] is StackPanel col && col.Children.Count > 1 &&
                col.Children[1] is TextBlock t)
                t.Text = Ltr(DriveUsage.Fmt(n));   // same fence as the row it replaces
        }
        catch { }
    }

    private void CloseBlade()
    {
        Blade.Visibility = Visibility.Collapsed;
        Blade.Children.Clear();
        _layer = "view";
        // Come back to the cover you opened, not to the start of the row.
        _focusGameKey = _selected?.Key;
        Sfx.Play(Sound.Back);
        RenderTab();
    }

    // =====================================================================
    //  quick menu + power
    // =====================================================================

    // The volume row keeps a handle on itself so a step updates ONE line rather
    // than rebuilding the menu - a rebuild would re-run its entrance animation
    // and move the focus, which is exactly wrong for a control you hold down.
    private Button? _volRow;

    private static string VolumeCaption()
    {
        int v = Interop.Volume.Level();
        if (v < 0) return "";
        return Interop.Volume.Muted()
            ? "מושתק - לחצו כדי להחזיר קול"
            // The reading is fenced (see Ltr): a bare "30%" at the head of a
            // Hebrew sentence renders as "%30".
            : $"{Ltr(v + "%")} · חצים ימינה/שמאלה לשינוי, A להשתקה";
    }

    private void RefreshVolumeRow()
    {
        if (_volRow is null) return;
        if (DetailOf(_volRow) is { } d) d.Text = VolumeCaption();
        if (_volRow.Content is Grid gr)
            foreach (var c in gr.Children)
                if (c is TextBlock tb && tb.FontFamily.Source.StartsWith("Segoe"))
                { tb.Text = Interop.Volume.Muted() ? GlyphMute : GlyphSound; break; }
    }

    /// <summary>Left/Right on the focused volume row. True when it consumed the key.</summary>
    private bool VolumeStep(int delta)
    {
        if (_layer != "quick" || _volRow is null || !_volRow.IsKeyboardFocusWithin) return false;
        int v = Interop.Volume.Level();
        if (v < 0) return false;
        Interop.Volume.Set(v + delta);
        Sfx.Play(Sound.Navigate);
        RefreshVolumeRow();
        return true;
    }

    private void OpenQuickMenu()
    {
        _layer = "quick";
        ResetNav();
        _navViewStart = 0;
        QuickMenu.Children.Clear();
        QuickMenu.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            // A modal is a SOLID layer over a dim scrim — never glass on glass,
            // or it is unreadable over box art.
            Width = CardWidth(460),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text("תפריט מהיר", "H2", margin: new Thickness(0, 0, 0, 16)));

        var session = _sessions?.Sessions.FirstOrDefault();
        if (session is not null)
            sp.Children.Add(Nav(RowButton(session.Suspended ? GlyphPlay : GlyphPause,
                session.Suspended ? $"חידוש {session.Name}" : $"השהיית {session.Name}",
                session.Suspended ? "ממשיך בדיוק מאותה נקודה" : "מקפיא את המשחק ומשחרר מעבד",
                () => { if (session.Suspended) ResumeSession(session); else SuspendSession(session); CloseQuick(); })));

        // 🔴 THE ONE CONTROL A COUCH USER CANNOT REACH ANY OTHER WAY. Without it
        // the only route to the system volume is a keyboard media key or the
        // Windows mixer - i.e. getting up. Left/Right step it, A mutes; the row
        // is the value, so it never has to be opened to be read.
        int vol = Interop.Volume.Level();
        if (vol >= 0)
        {
            _volRow = RowButton(Interop.Volume.Muted() ? GlyphMute : GlyphSound, "עוצמת קול",
                VolumeCaption(), () => { Interop.Volume.ToggleMute(); RefreshVolumeRow(); BuildPillChips(); });
            sp.Children.Add(Nav(_volRow));
        }

        sp.Children.Add(Nav(RowButton(GlyphCamera, "צילום מסך", "נשמר בתיקיית התמונות",
            () => { CloseQuick(); TakeScreenshot(); })));
        sp.Children.Add(Nav(RowButton(GlyphSound, _settings.SoundEnabled ? "השתקת צלילים" : "הפעלת צלילים", "",
            () =>
            {
                _settings.SoundEnabled = !_settings.SoundEnabled;
                Sfx.Configure(_settings.SoundEnabled, _settings.SoundVolume);
                Save(); CloseQuick();
            })));
        // 🔴🔴 THE SYSTEM PANELS HAD NO ROUTE FOR A CONTROLLER. Volume, network and
        // Bluetooth live behind the header chips, and those chips are
        // deliberately NOT in the focus map (a stick should not have to walk
        // through status icons to reach the content). The consequence went
        // unnoticed because a mouse always worked: on a couch, with a pad, there
        // was NO WAY AT ALL to reach the Wi-Fi list - which is the exact
        // situation the Bluetooth panel's own comment describes as the reason it
        // exists ("a pad that will not pair, a download that will not start").
        // The quick menu is the pad's entry to everything else; it is the right
        // door for these three too.
        sp.Children.Add(Nav(RowButton(GlyphSound, "עוצמת קול והתקן פלט", "עוצמה כללית, לכל אפליקציה ובחירת רמקולים",
            () => { CloseQuick(); OpenVolumePanel(); })));
        sp.Children.Add(Nav(RowButton(GlyphWifi, "רשת", "חיבור ל-Wi-Fi ומצב החיבור",
            () => { CloseQuick(); OpenNetworkPanel(); })));
        if (Interop.BluetoothDevices.RadioPresent())
            sp.Children.Add(Nav(RowButton(GlyphBluetooth, "בלוטות׳", "התאמה וחיבור של שלטים ואוזניות",
                () => { CloseQuick(); OpenBluetoothPanel(); })));

        sp.Children.Add(Nav(RowButton(GlyphRefresh, "רענון ספרייה", "", () => { CloseQuick(); _ = ReloadLibraryAsync(); })));
        sp.Children.Add(Nav(RowButton(GlyphPower, "אפשרויות הפעלה", "שינה, הפעלה מחדש, כיבוי, יציאה",
            () => { CloseQuick(); _powerFocus = 0; OpenPower(); })));

        card.Child = sp;
        QuickMenu.Children.Add(card);
        // A was missing here, on a screen that is nothing BUT pressable rows -
        // the one legend on it told the user how to leave and not how to act.
        SetHints(("A", "בחירה"), ("B", "סגירה"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusFirst());
        Animate(card);
    }

    // ------------------------------------------------------------------ search

    private TextBox? _searchBox;
    private Panel? _searchResults;

    /// <summary>
    /// The search overlay. Winhanced puts "Search" in the footer legend of every
    /// screen and the library grid alike - with sixty titles it is the only way
    /// to reach a game that is not in the first row, and a couch UI has no
    /// scrollbar to drag. Entirely local: it filters the library already in
    /// memory and never asks a server anything.
    /// </summary>
    private void OpenSearch()
    {
        _layer = "search";
        ResetNav();
        _navViewStart = 0;
        SearchHost.Children.Clear();
        SearchHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            // A modal is a SOLID layer over a dim scrim - never glass on glass,
            // or it is unreadable over box art.
            // 940 so four 200px covers (218 pitch) fill a row exactly. Wider looked
            // generous and read as broken: a two-hit search left most of the card
            // empty, and you type until only a few titles match - so the COMMON
            // case has to look deliberate, not the maximum one.
            Width = CardWidth(940),
            HorizontalAlignment = HorizontalAlignment.Center,
            // 🔴 ANCHORED TO THE TOP, NOT CENTRED. A centred card re-centres every
            // time the result count changes, so the field slides up and down under
            // the caret WHILE YOU TYPE. Pinned high, the field never moves and the
            // results simply grow downward - which is also where the eye expects
            // them, and it leaves the shelf visible behind for context.
            VerticalAlignment = VerticalAlignment.Top,
            Margin = new Thickness(0, 120, 0, 0),
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();

        var head = new Grid { Margin = new Thickness(0, 0, 0, 14) };
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var glyph = new TextBlock
        {
            Text = GlyphSearch,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 22,
            Foreground = (Brush)FindResource("FgSecondary"),
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 14, 0),
        };
        Grid.SetColumn(glyph, 0);

        // The field carries no visible chrome of its own beyond a baseline: a
        // boxed input inside a card is a second surface, and the caret plus the
        // placeholder already say "type here".
        _searchBox = new TextBox
        {
            Background = Brushes.Transparent,
            BorderThickness = new Thickness(0, 0, 0, 2),
            BorderBrush = (Brush)FindResource("Accent"),
            Foreground = (Brush)FindResource("FgPrimary"),
            CaretBrush = (Brush)FindResource("Accent"),
            FontFamily = new FontFamily("Heebo, Segoe UI"),
            FontSize = 26,
            Padding = new Thickness(0, 0, 0, 8),
            VerticalAlignment = VerticalAlignment.Center,
        };
        _searchBox.TextChanged += (_, _) => RenderSearchResults();
        Grid.SetColumn(_searchBox, 1);

        head.Children.Add(glyph);
        head.Children.Add(_searchBox);
        sp.Children.Add(head);

        _searchResults = new WrapPanel { Orientation = Orientation.Horizontal };
        sp.Children.Add(_searchResults);

        card.Child = sp;
        SearchHost.Children.Add(card);
        RenderSearchResults();
        SetHints(("A", "פתיחה"), ("B", "סגירה"));
        // The FIELD takes focus, not the first result - you came here to type.
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => _searchBox?.Focus());
        Animate(card);
    }

    private void RenderSearchResults()
    {
        if (_searchResults is null) return;
        _searchResults.Children.Clear();
        ResetNav();
        _navViewStart = 0;

        string q = (_searchBox?.Text ?? "").Trim();
        if (q.Length == 0)
        {
            _searchResults.Children.Add(Text("התחילו להקליד שם של משחק", "Caption"));
            return;
        }

        // Search the text as typed first. Only if that finds nothing do we re-read
        // the keystrokes through the other keyboard layout - so an intentional
        // Hebrew query is never hijacked, and F-A-R on a Hebrew layout still
        // reaches "Far Cry 5" (see Services/KeyMap.cs).
        var hits = Find(q);
        string used = q;
        if (hits.Count == 0)
        {
            foreach (string alt in new[] { KeyMap.ToLatin(q), KeyMap.ToHebrew(q) })
            {
                if (alt.Length == 0 || alt == q) continue;
                hits = Find(alt);
                if (hits.Count > 0) { used = alt; break; }
            }
        }

        if (hits.Count == 0)
        {
            _searchResults.Children.Add(Text($"לא נמצא משחק בשם \u201c{q}\u201d", "Caption"));
            return;
        }

        // Saying WHICH query produced these results is the whole reason the layout
        // fallback is not confusing: you typed Hebrew, you are seeing Latin titles.
        if (used != q)
            _searchResults.Children.Add(Text($"מציג תוצאות עבור \u201c{used}\u201d", "Caption"));

        foreach (var g in hits)
        {
            var t = Tile(g, 200, 300);
            double sbv = TileBloomV(300);
            t.Margin = new Thickness(17, sbv, 17, sbv);
            var game = g;
            t.Click += (_, _) => { CloseSearch(); OpenBlade(game); };
            _searchResults.Children.Add(Nav(t));
        }
    }

    /// <summary>Rank: a title that STARTS with the query first, then the shortest -
    /// with sixty games "far" should surface Far Cry 5, not Farming Simulator 2019.</summary>
    private List<LibraryGame> Find(string q) => _all
        .Where(g => g.Name.Contains(q, StringComparison.OrdinalIgnoreCase))
        .OrderByDescending(g => g.Name.StartsWith(q, StringComparison.OrdinalIgnoreCase))
        .ThenBy(g => g.Name.Length)
        .Take(8)          // two rows of four - past that, keep typing
        .ToList();

    /// <summary>The primary CTA of a card - it is always registered last.</summary>
    private void ActivateLast()
    {
        if (_nav.LastOrDefault(Usable) is ButtonBase b)
            b.RaiseEvent(new RoutedEventArgs(ButtonBase.ClickEvent));
    }

    private void ActivateFirstResult()
    {
        var first = _nav.FirstOrDefault(Usable);
        if (first is ButtonBase b) b.RaiseEvent(new RoutedEventArgs(ButtonBase.ClickEvent));
    }

    private void CloseSearch()
    {
        SearchHost.Visibility = Visibility.Collapsed;
        SearchHost.Children.Clear();
        _searchBox = null;
        _searchResults = null;
        _layer = "view";
        RenderTab();
    }

    private void CloseQuick()
    {
        QuickMenu.Visibility = Visibility.Collapsed;
        QuickMenu.Children.Clear();
        _layer = "view";
        RenderTab();
    }

    /// <summary>
    /// Where B goes from the current dialog. A confirmation sets this to the
    /// menu that opened it, so "back" undoes ONE step instead of dumping the
    /// user all the way out to the library.
    /// </summary>
    private Action? _dialogBack;

    /// <summary>
    /// Power Options - Winhanced's own row set, decoded from its
    /// Dialogs/PowerMenuDialog.xbf: Sleep / Hibernate / divider / Restart /
    /// Shut down / divider / Quit.
    ///
    /// THE SUBTITLE IS THE SAFETY FEATURE, not decoration. Winhanced writes
    /// "Restart this device" and "Power off this device" against "Quit
    /// Winhanced - Exit application", so a glance tells you WHOSE power is
    /// about to be cut. A bare "Shut down" inside an app's own menu reads as
    /// "close the app" - exactly the wrong thing to be wrong about.
    ///
    /// Winhanced fires these immediately; we do not. On a controller a stick
    /// nudge plus A is two casual inputs, and this list ends in "turn the
    /// computer off" - so every row that touches the MACHINE goes through a
    /// confirmation first, with Cancel focused.
    /// </summary>
    private void OpenPower()
    {
        _layer = "dialog";
        _dialogBack = null;
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(470),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text("\u05D0\u05E4\u05E9\u05E8\u05D5\u05D9\u05D5\u05EA \u05D4\u05E4\u05E2\u05DC\u05D4", "H2", margin: new Thickness(0, 0, 0, 4)));
        // The caption describes the FIRST group only, and the divider is what
        // makes that readable - it used to be able to say "these actions touch
        // the machine" flatly because every row did. Now two do not, and a
        // caption that over-claims is how somebody picks shutdown meaning exit.
        sp.Children.Add(Text("\u05D4\u05E4\u05E2\u05D5\u05DC\u05D5\u05EA \u05DE\u05E2\u05DC \u05D4\u05E7\u05D5 \u05E0\u05D5\u05D2\u05E2\u05D5\u05EA \u05DC\u05DE\u05D7\u05E9\u05D1 \u05E2\u05E6\u05DE\u05D5, \u05D5\u05D4\u05E4\u05E2\u05D5\u05DC\u05D5\u05EA \u05DE\u05EA\u05D7\u05EA\u05D9\u05D5 \u05DC\u05D1\u05D9\u05D2 \u05DC\u05D0\u05E0\u05E5\u05F3 \u05D1\u05DC\u05D1\u05D3",
            "Caption", margin: new Thickness(0, 0, 0, 16)));

        sp.Children.Add(Nav(RowButton(GlyphSleep,
            "\u05DE\u05E6\u05D1 \u05E9\u05D9\u05E0\u05D4",
            "\u05E6\u05E8\u05D9\u05DB\u05EA \u05D7\u05E9\u05DE\u05DC \u05E0\u05DE\u05D5\u05DB\u05D4, \u05D7\u05D9\u05D3\u05D5\u05E9 \u05DE\u05D4\u05D9\u05E8",
            () => Confirm(
                "\u05DC\u05D4\u05E2\u05D1\u05D9\u05E8 \u05D0\u05EA \u05D4\u05DE\u05D7\u05E9\u05D1 \u05DC\u05E9\u05D9\u05E0\u05D4?",
                "\u05DB\u05DC \u05DE\u05D4 \u05E9\u05E4\u05EA\u05D5\u05D7 \u05D9\u05D9\u05E9\u05D0\u05E8 \u05E4\u05EA\u05D5\u05D7 \u05D5\u05D4\u05DE\u05D7\u05E9\u05D1 \u05D9\u05EA\u05E2\u05D5\u05E8\u05E8 \u05D1\u05DE\u05D4\u05D9\u05E8\u05D5\u05EA.",
                "\u05D4\u05E2\u05D1\u05E8 \u05DC\u05E9\u05D9\u05E0\u05D4", false,
                () => { Sfx.Play(Sound.Sleep); Run("rundll32.exe", "powrprof.dll,SetSuspendState 0,1,0"); }, back: OpenPower))));

        sp.Children.Add(Nav(RowButton(GlyphHibernate,
            "\u05DE\u05E6\u05D1 \u05EA\u05E8\u05D3\u05DE\u05D4",
            "\u05E6\u05E8\u05D9\u05DB\u05D4 \u05D0\u05E4\u05E1\u05D9\u05EA, \u05E9\u05D5\u05DE\u05E8 \u05D0\u05EA \u05D4\u05DE\u05E6\u05D1 \u05DC\u05D3\u05D9\u05E1\u05E7",
            () => Confirm(
                "\u05DC\u05D4\u05E2\u05D1\u05D9\u05E8 \u05D0\u05EA \u05D4\u05DE\u05D7\u05E9\u05D1 \u05DC\u05EA\u05E8\u05D3\u05DE\u05D4?",
                "\u05D4\u05DE\u05E6\u05D1 \u05D4\u05E0\u05D5\u05DB\u05D7\u05D9 \u05D9\u05D9\u05E9\u05DE\u05E8 \u05DC\u05D3\u05D9\u05E1\u05E7 \u05D5\u05D4\u05DE\u05D7\u05E9\u05D1 \u05D9\u05D9\u05DB\u05D1\u05D4 \u05DC\u05D2\u05DE\u05E8\u05D9. \u05D4\u05D4\u05EA\u05E2\u05D5\u05E8\u05E8\u05D5\u05EA \u05D0\u05D9\u05D8\u05D9\u05EA \u05D9\u05D5\u05EA\u05E8 \u05DE\u05E9\u05D9\u05E0\u05D4.",
                "\u05D4\u05E2\u05D1\u05E8 \u05DC\u05EA\u05E8\u05D3\u05DE\u05D4", false,
                () => { Sfx.Play(Sound.Sleep); Run("shutdown.exe", "/h"); }, back: OpenPower))));

        sp.Children.Add(Divider());

        sp.Children.Add(Nav(RowButton(GlyphRefresh,
            "\u05D4\u05E4\u05E2\u05DC\u05D4 \u05DE\u05D7\u05D3\u05E9 \u05E9\u05DC \u05D4\u05DE\u05D7\u05E9\u05D1",
            "\u05D4\u05DE\u05D7\u05E9\u05D1 \u05D9\u05D9\u05DB\u05D1\u05D4 \u05D5\u05D9\u05D9\u05D3\u05DC\u05E7 \u05E9\u05D5\u05D1",
            () => Confirm(
                "\u05DC\u05D4\u05E4\u05E2\u05D9\u05DC \u05DE\u05D7\u05D3\u05E9 \u05D0\u05EA \u05D4\u05DE\u05D7\u05E9\u05D1?",
                "\u05DB\u05DC \u05D4\u05EA\u05D5\u05DB\u05E0\u05D5\u05EA \u05D9\u05D9\u05E1\u05D2\u05E8\u05D5." + RunningWarning(),
                "\u05D4\u05E4\u05E2\u05DC \u05DE\u05D7\u05D3\u05E9", true,
                () => Run("shutdown.exe", "/r /t 0"), back: OpenPower))));

        sp.Children.Add(Nav(RowButton(GlyphPower,
            "\u05DB\u05D9\u05D1\u05D5\u05D9 \u05D4\u05DE\u05D7\u05E9\u05D1",
            "\u05D4\u05DE\u05D7\u05E9\u05D1 \u05D9\u05D9\u05DB\u05D1\u05D4 \u05DC\u05D2\u05DE\u05E8\u05D9",
            () => Confirm(
                "\u05DC\u05DB\u05D1\u05D5\u05EA \u05D0\u05EA \u05D4\u05DE\u05D7\u05E9\u05D1?",
                "\u05DB\u05DC \u05D4\u05EA\u05D5\u05DB\u05E0\u05D5\u05EA \u05D9\u05D9\u05E1\u05D2\u05E8\u05D5 \u05D5\u05D4\u05DE\u05D7\u05E9\u05D1 \u05D9\u05D9\u05DB\u05D1\u05D4." + RunningWarning(),
                "\u05DB\u05D1\u05D4 \u05D0\u05EA \u05D4\u05DE\u05D7\u05E9\u05D1", true,
                () => Run("shutdown.exe", "/s /t 0"), back: OpenPower))));

        sp.Children.Add(Divider());

        // The two rows below this divider are the ones that do NOT touch the
        // machine, which is exactly why they are fenced off from the four above
        // it. Ordered least-final first: handing off leaves the shell running
        // in the taskbar, quitting does not.
        sp.Children.Add(Nav(RowButton(GlyphMonitor,
            "\u05DE\u05E2\u05D1\u05E8 \u05DC\u05DC\u05D0\u05E0\u05E6\u05F3\u05E8 \u05E9\u05DC \u05E9\u05D5\u05DC\u05D7\u05DF \u05D4\u05E2\u05D1\u05D5\u05D3\u05D4",
            "\u05D6\u05D5 \u05D4\u05D3\u05E8\u05DA \u05D4\u05D9\u05D7\u05D9\u05D3\u05D4 \u05DC\u05E2\u05D1\u05D5\u05E8 \u05D1\u05D9\u05DF \u05E9\u05E0\u05D9 \u05D4\u05DE\u05E1\u05DB\u05D9\u05DD. \u05D1\u05D9\u05D2 \u05DC\u05D0\u05E0\u05E5\u05F3 \u05DC\u05D0 \u05E0\u05E1\u05D2\u05E8 - \u05D4\u05D5\u05D0 \u05DE\u05DE\u05EA\u05D9\u05DF \u05D1\u05E9\u05D5\u05E8\u05EA \u05D4\u05DE\u05E9\u05D9\u05DE\u05D5\u05EA",
            () => HandOff(null))));

        sp.Children.Add(Nav(RowButton(GlyphBack,
            "\u05D9\u05E6\u05D9\u05D0\u05D4 \u05DE\u05D1\u05D9\u05D2 \u05DC\u05D0\u05E0\u05E5\u05F3",
            "\u05E1\u05D5\u05D2\u05E8 \u05D0\u05EA \u05D4\u05D0\u05E4\u05DC\u05D9\u05E7\u05E6\u05D9\u05D4 \u05D1\u05DC\u05D1\u05D3. \u05D4\u05DE\u05D7\u05E9\u05D1 \u05E0\u05E9\u05D0\u05E8 \u05D3\u05DC\u05D5\u05E7.",
            QuitApp)));

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("B", "\u05D1\u05D9\u05D8\u05D5\u05DC"), ("A", "\u05D1\u05D7\u05D9\u05E8\u05D4"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusIndex(_powerFocus));
        Animate(card);
    }

    /// <summary>A suspended game dies with the machine - say so BEFORE it does.</summary>
    private string RunningWarning()
    {
        int n = _sessions?.Sessions.Count ?? 0;
        return n == 0 ? "" :
            "\n\n\u26A0 " + n + " \u05DE\u05E9\u05D7\u05E7\u05D9\u05DD \u05E4\u05EA\u05D5\u05D7\u05D9\u05DD \u05D0\u05D5 \u05DE\u05D5\u05E9\u05D4\u05D9\u05DD \u05D9\u05D9\u05E1\u05D2\u05E8\u05D5 \u05D5\u05D4\u05EA\u05E7\u05D3\u05DE\u05D5\u05EA \u05E9\u05DC\u05D0 \u05E0\u05E9\u05DE\u05E8\u05D4 \u05EA\u05D0\u05D1\u05D3.";
    }

    private void QuitApp()
    {
        int n = _sessions?.Sessions.Count ?? 0;
        if (n == 0) { Sfx.Play(Sound.Back); Close(); return; }
        Confirm(
            "\u05DC\u05E6\u05D0\u05EA \u05DE\u05D1\u05D9\u05D2 \u05DC\u05D0\u05E0\u05E5\u05F3?",
            n + " \u05DE\u05E9\u05D7\u05E7\u05D9\u05DD \u05DE\u05D5\u05E9\u05D4\u05D9\u05DD \u05D9\u05E9\u05D5\u05D7\u05E8\u05E8\u05D5 \u05D5\u05D9\u05DE\u05E9\u05D9\u05DB\u05D5 \u05DC\u05E8\u05D5\u05E5 \u05E8\u05D2\u05D9\u05DC. \u05D4\u05DE\u05D7\u05E9\u05D1 \u05DC\u05D0 \u05D9\u05D9\u05DB\u05D1\u05D4.",
            "\u05E6\u05D0", false, () => { Sfx.Play(Sound.Back); Close(); }, back: OpenPower);
    }

    /// <summary>
    /// A two-button confirmation. Cancel is FIRST and takes focus, so the
    /// dangerous option can never be reached by reflex - a controller user who
    /// mashes A lands on "cancel", the only safe default. B steps back to the
    /// power menu rather than closing the whole stack.
    /// </summary>
    private void Confirm(string title, string body, string confirmLabel,
                              bool destructive, Action onConfirm, Action? back = null)
    {
        Sfx.Play(destructive ? Sound.Warning : Sound.Select);

        // Whatever is focused right now IS the row that raised this - remember
        // it before the list is torn down, so B puts the cursor back.
        if (Keyboard.FocusedElement is FrameworkElement raiser)
        {
            int i = _nav.IndexOf(raiser);
            if (i >= 0) _powerFocus = i;
        }

        _layer = "dialog";
        // 🔴 CANCEL MUST RETURN WHERE THE USER CAME FROM. This was hardcoded
        // to the power menu because that is where confirmations started; the
        // first caller from anywhere else would have been dumped into a
        // shutdown screen it never opened.
        back ??= RenderTab;
        // Wrap it: dismissing is OUR job, the callback only chooses the
        // destination. Otherwise a back() that repaints a screen BEHIND the
        // card leaves the card on screen with nothing focused inside it.
        Action land = back;
        back = () => { DismissDialog(); _layer = "view"; land(); };
        _dialogBack = back;
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            BorderBrush = destructive ? (Brush)FindResource("Destructive")
                                      : (Brush)FindResource("HairlineBrush"),
            Width = CardWidth(520),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();

        var head = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 12) };
        head.Children.Add(new TextBlock
        {
            Text = destructive ? GlyphWarn : GlyphInfo,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 22,
            Foreground = destructive ? (Brush)FindResource("Destructive") : (Brush)FindResource("Accent"),
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 12, 0),
        });
        head.Children.Add(new TextBlock
        {
            Text = title,
            Style = (Style)FindResource("H2"),
            VerticalAlignment = VerticalAlignment.Center,
            TextWrapping = TextWrapping.Wrap,
        });
        sp.Children.Add(head);

        sp.Children.Add(new TextBlock
        {
            Text = body,
            Style = (Style)FindResource("Body"),
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 24),
        });

        var row = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Left };
        row.Children.Add(Nav(Ghost(GlyphBack, "\u05D1\u05D9\u05D8\u05D5\u05DC",
            () => { Sfx.Play(Sound.Back); back(); })));

        var go = new Button
        {
            Style = (Style)FindResource(destructive ? "DestructiveCTA" : "PrimaryCTA"),
            Content = new TextBlock { Text = confirmLabel, VerticalAlignment = VerticalAlignment.Center },
            Margin = new Thickness(12, 0, 0, 0),
        };
        go.Click += (_, _) => { _dialogBack = null; CloseDialog(); onConfirm(); };
        row.Children.Add(Nav(go));
        sp.Children.Add(row);

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("B", "\u05D1\u05D9\u05D8\u05D5\u05DC"), ("A", "\u05D0\u05D9\u05E9\u05D5\u05E8"));
        // Focus CANCEL, never the destructive button.
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusFirst());
        Animate(card);
    }

    /// <summary>
    /// One-of-N as a CARD, not as a press that steps to the next value.
    ///
    /// 🔴 A CYCLING ROW HIDES THE CHOICE IT IS OFFERING. It was defended as
    /// saving vertical space, and it does - but the cost is that the only way
    /// to find out what the options ARE is to press the row repeatedly and
    /// watch the label change, and the only way BACK to a value you have just
    /// stepped past is to go all the way round. With four or five values that
    /// is a guessing game played one press at a time, and on a pad it is worse,
    /// because A is also how you leave a row. So anything with more than two
    /// values now opens a list: every option visible at once, its consequence
    /// written next to it, the current one ticked and focused.
    ///
    /// Two-state things stay toggles - a switch already shows both states.
    /// </summary>
    private void Picker(string title, string body,
                        IReadOnlyList<(string Key, string Label, string Detail)> options,
                        string current, Action<string> pick, Action? back = null)
    {
        Sfx.Play(Sound.Select);

        // Remember the row that raised this so B puts the cursor back on it.
        if (Keyboard.FocusedElement is FrameworkElement raiser)
        {
            int ri = _nav.IndexOf(raiser);
            if (ri >= 0) _powerFocus = ri;
        }

        _layer = "dialog";
        back ??= RenderTab;
        Action land = back;
        back = () => { DismissDialog(); _layer = "view"; land(); };
        _dialogBack = back;
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            BorderBrush = (Brush)FindResource("HairlineBrush"),
            Width = CardWidth(620),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(new TextBlock
        {
            Text = title,
            Style = (Style)FindResource("H2"),
            TextWrapping = TextWrapping.Wrap,
        });
        if (body.Length > 0)
            sp.Children.Add(new TextBlock
            {
                Text = body,
                Style = (Style)FindResource("Caption"),
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 6, 0, 16),
            });

        int selected = 0;
        for (int i = 0; i < options.Count; i++)
        {
            var (key, label, detail) = options[i];
            bool on = key == current;
            if (on) selected = i;
            string k = key;
            // The tick is the ONLY difference between a chosen row and the rest:
            // no accent fill, because the focus ring is already doing that job
            // and two highlights on one list makes neither of them mean anything.
            sp.Children.Add(Nav(RowButton(on ? GlyphCheck : "", label, detail,
                // 🔴 pick FIRST, THEN CloseDialog. CloseDialog ends in a
                // RenderTab, so closing before applying rebuilt the whole page
                // from the value the user had just replaced - and then the pick
                // callback rebuilt it AGAIN from the new one. Two full rebuilds
                // back to back, each landing at scroll 0 and each animating the
                // restored focus back down: that is the shudder you see on the
                // way out of every picker. Applying first makes the render that
                // CloseDialog already does the ONLY one that is needed.
                () => { _dialogBack = null; pick(k); CloseDialog(); },
                glyphBrush: on ? (Brush)FindResource("Accent") : null)));
        }

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 16, 0, 0),
        };
        row.Children.Add(Nav(Ghost(GlyphBack, "ביטול", () => { Sfx.Play(Sound.Back); back(); })));
        sp.Children.Add(row);

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("B", "ביטול"), ("A", "בחירה"));
        // Land on what is ALREADY chosen, so "keep it as it is" costs no moves
        // and the list opens showing you where you currently stand.
        int focusAt = selected;
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusIndex(focusAt));
        Animate(card);
    }

    /// <summary>Winhanced's DividerStrokeColorDefaultBrush, between row groups.</summary>
    private UIElement Divider() => new Border
    {
        Height = 1,
        Background = (Brush)FindResource("HairlineBrush"),
        Margin = new Thickness(2, 8, 2, 14),
    };

    /// <summary>
    /// Membership picker. A collection is added and removed HERE, from the game
    /// itself, because that is where the user is standing when the thought
    /// occurs — a separate "manage collections" screen would mean leaving the
    /// game, remembering its name, and finding it again.
    /// </summary>
    private void OpenCollections(LibraryGame g)
    {
        Sfx.Play(Sound.Select);
        _layer = "dialog";
        _dialogBack = () => { DismissDialog(); _layer = "view"; OpenBlade(g); };
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(560),
            MaxHeight = 640,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text("אוספים", "H2", margin: new Thickness(0, 0, 4, 4)));
        sp.Children.Add(Text(g.Name, "Caption", margin: new Thickness(0, 0, 0, 16)));

        if (_settings.Collections.Count == 0)
            sp.Children.Add(Text("עוד אין אוספים. צור אחד וסנן איתו את הספרייה.",
                                 "Caption", margin: new Thickness(0, 0, 0, 12)));

        foreach (var c in _settings.Collections
                                   .OrderBy(c => c.Name, StringComparer.CurrentCulture).ToList())
        {
            var col = c;
            sp.Children.Add(Nav(Toggle(col.Name,
                Games(col.Keys.Count),
                col.Keys.Contains(g.Key),
                v =>
                {
                    if (v) { if (!col.Keys.Contains(g.Key)) col.Keys.Add(g.Key); }
                    else col.Keys.Remove(g.Key);
                    Save();
                })));
        }

        sp.Children.Add(Divider());
        sp.Children.Add(Nav(RowButton(GlyphAdd, "אוסף חדש",
            "תן לו שם וסנן איתו את הספרייה", () => PromptName(g))));

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 18, 0, 0),
        };
        row.Children.Add(Nav(Ghost(GlyphBack, "סיום",
            () => { Sfx.Play(Sound.Back); DismissDialog(); _layer = "view"; OpenBlade(g); })));
        sp.Children.Add(row);

        card.Child = Scroller(sp);
        DialogHost.Children.Add(card);
        SetHints(("A", "סימון"), ("B", "סיום"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusFirst());
        Animate(card);
    }

    /// <summary>Name a new collection. The field takes focus — you came to type.</summary>
    private void PromptName(LibraryGame g)
    {
        Sfx.Play(Sound.Select);
        _layer = "dialog";
        _dialogBack = () => { DismissDialog(); _layer = "view"; OpenCollections(g); };
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(520),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text("שם האוסף", "H2", margin: new Thickness(0, 0, 0, 14)));

        var box = new TextBox
        {
            Background = Brushes.Transparent,
            BorderThickness = new Thickness(0, 0, 0, 2),
            BorderBrush = (Brush)FindResource("Accent"),
            Foreground = (Brush)FindResource("FgPrimary"),
            CaretBrush = (Brush)FindResource("Accent"),
            FontFamily = new FontFamily("Heebo, Segoe UI"),
            FontSize = 24,
            Padding = new Thickness(0, 0, 0, 8),
            MaxLength = 40,
        };
        sp.Children.Add(box);

        void Commit()
        {
            string name = box.Text.Trim();
            if (name.Length == 0) { Sfx.Play(Sound.Warning); return; }
            // A duplicate name would make two chips indistinguishable and the
            // "col:" filter ambiguous — reuse the existing one instead.
            var col = CollectionOf(name);
            if (col is null) { col = new GameCollection { Name = name }; _settings.Collections.Add(col); }
            if (!col.Keys.Contains(g.Key)) col.Keys.Add(g.Key);
            Save();
            Sfx.Play(Sound.Select);
            DismissDialog(); _layer = "view"; OpenCollections(g);
        }
        box.KeyDown += (_, e) => { if (e.Key == Key.Enter) { e.Handled = true; Commit(); } };

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 22, 0, 0),
        };
        row.Children.Add(Nav(Ghost(GlyphBack, "ביטול",
            () => { Sfx.Play(Sound.Back); DismissDialog(); _layer = "view"; OpenCollections(g); })));
        var ok = new Button
        {
            Style = (Style)FindResource("PrimaryCTA"),
            Content = new TextBlock { Text = "צור", VerticalAlignment = VerticalAlignment.Center },
            Margin = new Thickness(12, 0, 0, 0),
        };
        ok.Click += (_, _) => Commit();
        row.Children.Add(Nav(ok));
        sp.Children.Add(row);

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("A", "צור"), ("B", "ביטול"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => box.Focus());
        Animate(card);
    }

    // Last known text-language label per game, so the row can render instantly
    // on re-open instead of showing "checking" every time.
    private readonly Dictionary<string, string> _langLabel = new();

    // 🔴 THE LIVE SUBTITLE OF THE LANGUAGE ROW - updated IN PLACE.
    // Refreshing it by re-opening the blade looked like a glitch: the rebuild
    // re-runs the panel's entrance fade, so for ~200ms the OLD text and the
    // NEW one are both on screen, overlapped ("checking..." on top of "not
    // supported"). A background probe must never re-render the screen the user
    // is reading - it changes one line.
    private TextBlock? _langDetail;

    /// <summary>The subtitle TextBlock inside a RowButton, so one line can be
    /// updated without rebuilding its page.</summary>
    private static TextBlock? DetailOf(Button row)
    {
        if (row.Content is not Grid grid) return null;
        foreach (var child in grid.Children)
            if (child is StackPanel sp && sp.Children.Count > 1 && sp.Children[1] is TextBlock tb)
                return tb;
        return null;
    }

    private static string LangLabel(string mode) => mode switch
    {
        "hebrew"  => "עברית",
        "english" => "אנגלית",
        _         => "אוטומטי",
    };

    /// <summary>
    /// Read the game's current text language in the background and update the
    /// row once. Reading is cheap and side-effect free, so it is done on open
    /// rather than making the user press a row to find out what it says.
    /// </summary>
    private async void RefreshLanguage(LibraryGame g)
    {
        if (g.Hub is null || !ModBridge.Available()) return;
        var res = await ModBridge.RunAsync("language", g.Hub.Id, null, null, CancellationToken.None);
        string label = "לא נתמך במשחק הזה";
        try
        {
            using var doc = JsonDocument.Parse(FirstJson(res.Raw));
            if (doc.RootElement.TryGetProperty("result", out var r))
            {
                bool supported = !r.TryGetProperty("supported", out var sup) || sup.ValueKind != JsonValueKind.False;
                if (supported)
                    label = LangLabel(r.TryGetProperty("mode", out var m) ? m.GetString() ?? "" : "");
            }
        }
        catch { }

        _langLabel[g.Key] = label;
        Dispatcher.Invoke(() =>
        {
            if (_layer == "blade" && _selected == g && _langDetail is not null)
                _langDetail.Text = label;
        });
    }

    /// <summary>The LAST json object printed - the terminal one.</summary>
    private static string FirstJson(string raw)
    {
        var lines = raw.Split('\n', StringSplitOptions.RemoveEmptyEntries);
        for (int i = lines.Length - 1; i >= 0; i--)
            if (lines[i].TrimStart().StartsWith("{")) return lines[i];
        return "{}";
    }

    /// <summary>
    /// Cycle auto -> Hebrew -> English. A cycle rather than a dialog: there are
    /// three values, the row already shows which one is current, and a menu for
    /// three items is a screen the user has to dismiss.
    /// </summary>
    private async void CycleLanguage(LibraryGame g)
    {
        if (g.Hub is null) return;
        string cur = _langLabel.TryGetValue(g.Key, out var l) ? l : "אוטומטי";
        if (cur.StartsWith("לא")) { Sfx.Play(Sound.Warning); ShowToast("המשחק הזה לא תומך בהחלפת שפה"); return; }

        string next = cur switch
        {
            "אוטומטי" => "hebrew",
            "עברית"   => "english",
            _         => "auto",
        };
        Sfx.Play(Sound.Select);
        _langLabel[g.Key] = LangLabel(next);
        if (_langDetail is not null) _langDetail.Text = LangLabel(next);   // answers the press at once

        var res = await ModBridge.RunAsync("language", g.Hub.Id, next, null, CancellationToken.None);
        if (!res.Ok)
        {
            Sfx.Play(Sound.Warning);
            ShowToast("החלפת השפה נכשלה");
        }
        RefreshLanguage(g);                             // re-read: the game decides, not us
    }

    /// <summary>
    /// Install or remove a Hebrew translation, without leaving the console.
    ///
    /// The work happens in the desktop launcher (see ModBridge); this is the
    /// part the user sees. It is a MODAL with no dismiss while it runs: an
    /// applier is mid-way through writing into a game folder, and a console
    /// that let you wander off to another screen would be inviting a second
    /// action on the same files.
    /// </summary>
    private async void RunMod(LibraryGame g, string op)
    {
        bool removing = op == "remove";

        // 2 APPLIERS ON ONE GAME FOLDER IS A CORRUPTED GAME. Nothing stopped a
        // second run: the row stays clickable behind the progress card, the pad
        // repeats, and a double press on "התקנה" started a second headless
        // worker that unpacks over the first one's files - or worse, backs up
        // the half-patched archive as if it were the original. The guard is on
        // the WORKER, not on the row, because the row is only one of the ways
        // in (the quick menu and the blade both reach here).
        if (_modBusy)
        {
            Sfx.Play(Sound.Warning);
            ShowToast("פעולה אחרת כבר רצה - יש להמתין לסיומה");
            return;
        }

        Sfx.Play(Sound.Select);

        // Removing is destructive enough to ask first - the same rule the power
        // menu and Uninstall already follow. Installing is not: it is additive,
        // reversible from this very row, and asking would only add a click.
        if (removing)
        {
            Confirm($"להסיר את התרגום מ{g.Name}?",
                    "קבצי המשחק יוחזרו למצבם המקורי מהגיבוי שנשמר בהתקנה. " +
                    "אפשר להתקין שוב בכל רגע.",
                    "הסר", destructive: true, () => StartMod(g, op));
            return;
        }
        StartMod(g, op);
        await Task.CompletedTask;
    }

    /// <summary>True while a headless applier is running. See RunMod.</summary>
    private bool _modBusy;

    /// <summary>Cancels the running applier. Non-null exactly while _modBusy.</summary>
    private CancellationTokenSource? _modCts;

    private async void StartMod(LibraryGame g, string op)
    {
        bool removing = op == "remove";
        string heading = op switch
        {
            "remove"     => "מסיר תרגום",
            "clearcache" => "מנקה מטמון",
            _            => "מתקין תרגום",
        };
        _modBusy = true;
        _modCts = new CancellationTokenSource();
        _layer = "dialog";

        // A DOOR WITH NO HANDLE. The back action was inert ON PURPOSE - a half
        // applied patch must not be abandoned by a stray B - but "you may not
        // leave" and "there is no way out at all" are different promises, and
        // only the second one was implemented. If the worker died or hung, the
        // console sat on a frozen progress bar with every button dead and no
        // path back short of killing the process. B now CANCELS, which kills the
        // worker so the launcher's own journal can roll the files back, and the
        // card carries the same action as a real button for the mouse.
        _dialogBack = CancelMod;
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(760),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text(heading, "H2",
                             margin: new Thickness(0, 0, 0, 2)));
        sp.Children.Add(Text(g.Name, "Caption", margin: new Thickness(0, 0, 0, 18)));

        var status = Text("מתחיל…", "Body", margin: new Thickness(0, 0, 0, 12));
        sp.Children.Add(status);

        var track = new Border
        {
            Height = 10,
            CornerRadius = new CornerRadius(5),
            Background = (Brush)FindResource("GlassChip"),
            Margin = new Thickness(0, 0, 0, 6),
        };
        var fill = new Border
        {
            Height = 10,
            CornerRadius = new CornerRadius(5),
            Background = (Brush)FindResource("Accent"),
            HorizontalAlignment = HorizontalAlignment.Left,
            Width = 0,
        };
        var trackGrid = new Grid();
        trackGrid.Children.Add(track);
        trackGrid.Children.Add(fill);
        sp.Children.Add(trackGrid);

        var pctText = Text("", "Caption", margin: new Thickness(0, 0, 0, 4));
        sp.Children.Add(pctText);

        var cancelRow = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 18, 0, 0),
        };
        cancelRow.Children.Add(Nav(Ghost(GlyphStop, "ביטול", CancelMod)));
        sp.Children.Add(cancelRow);

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("B", "ביטול"));
        Animate(card);

        var progress = new Progress<ModBridge.Tick>(t =>
        {
            if (t.Message.Length > 0 && status is TextBlock tb) tb.Text = t.Message;
            double w = Math.Max(0, Math.Min(100, t.Pct)) / 100.0 * (card.Width - 48);
            fill.Width = w;
            if (pctText is TextBlock pt) pt.Text = t.Pct > 0 ? Ltr($"{t.Pct:0}%") : "";
        });

        ModBridge.Result res;
        try
        {
            res = await ModBridge.RunAsync(op, g.Hub!.Id, x => ((IProgress<ModBridge.Tick>)progress).Report(x),
                                           _modCts.Token);
        }
        finally
        {
            // Cleared in a finally so a throw cannot leave the shell believing
            // an applier is still running and refusing every future install.
            _modBusy = false;
            _modCts?.Dispose();
            _modCts = null;
        }

        DismissDialog();
        _layer = "view";

        if (res.Ok)
        {
            Sfx.Play(Sound.Select);
            // The row above reads its state from the catalog, so the catalog has
            // to be re-read before the blade is drawn again - otherwise the user
            // is told the install succeeded by a row that still says "available".
            await ReloadLibraryAsync();
            ShowToast(res.Message.Length > 0 ? res.Message
                                             : (op switch { "remove" => "התרגום הוסר", "clearcache" => "המטמון נוקה", _ => "התרגום הותקן" }));
        }
        else
        {
            Sfx.Play(Sound.Warning);
            ShowToast(res.Message.Length > 0 ? res.Message : "הפעולה נכשלה");
            OpenBlade(g);
        }
    }

    /// <summary>
    /// Stop the running applier. Safe to call when nothing is running, because
    /// it is reachable from B on a card that may already have closed.
    /// </summary>
    private void CancelMod()
    {
        if (!_modBusy || _modCts is null) return;
        Sfx.Play(Sound.Back);
        ShowToast("מבטל…");
        try { _modCts.Cancel(); } catch { }
    }

    /// <summary>
    /// Game Options -> Choose Artwork. The storage and the render path already
    /// existed (CustomBoxArt / CustomHeroArt / CustomLogo are read by the cover,
    /// the blade backdrop, the logo and the collection grid) - only the way to
    /// SET them was missing, so this is the whole feature.
    ///
    /// It browses images that are ALREADY on the machine rather than opening a
    /// file dialog: a picker is a mouse surface, and a 10ft shell has to stay
    /// usable from the couch. The two places art actually lives are the game's
    /// own folder (many ship a cover or a logo) and the user's Pictures.
    /// </summary>
    private void OpenArtwork(LibraryGame g)
    {
        Sfx.Play(Sound.Select);
        _layer = "dialog";
        _dialogBack = () => { DismissDialog(); _layer = "view"; OpenBlade(g); };
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var prof = Profile(g);
        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(900),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text("בחירת תמונות", "H2", margin: new Thickness(0, 0, 0, 2)));
        sp.Children.Add(Text(g.Name, "Caption", margin: new Thickness(0, 0, 0, 18)));

        void Slot(string title, string hint, Func<string?> get, Action<string?> set)
        {
            string? cur = get();
            string detail = cur is { Length: > 0 } ? Ltr(IOPath.GetFileName(cur)) : hint;
            sp.Children.Add(Nav(RowButton(GlyphImage, title, detail,
                () => PickImage(g, title, chosen =>
                {
                    // Drop both the old and the new path from the decode cache:
                    // the user may well be replacing a file they just edited, and
                    // a cached decode would show them the picture they changed.
                    ForgetImg(get());
                    ForgetImg(chosen);
                    set(chosen);
                    Save();
                    DismissDialog(); _layer = "view";
                    OpenArtwork(g);
                    ShowToast(chosen is null ? "חזרה לתמונת ברירת המחדל" : "התמונה עודכנה");
                }))));
        }

        Slot("עטיפה", "תמונת ברירת המחדל", () => prof.CustomBoxArt, v => prof.CustomBoxArt = v);
        Slot("רקע", "תמונת ברירת המחדל", () => prof.CustomHeroArt, v => prof.CustomHeroArt = v);
        Slot("לוגו", "תמונת ברירת המחדל", () => prof.CustomLogo, v => prof.CustomLogo = v);

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 22, 0, 0),
        };
        row.Children.Add(Nav(Ghost(GlyphBack, "חזרה",
            () => { Sfx.Play(Sound.Back); DismissDialog(); _layer = "view"; OpenBlade(g); })));
        sp.Children.Add(row);

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("A", "בחר"), ("B", "חזרה"));
        Animate(card);
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusFirst());
    }

    /// <summary>
    /// The browser itself: every image we can find for this game, as a grid of
    /// real thumbnails. Choosing with the eyes is the point - a list of file
    /// names would make the user open each one to find out what it is.
    /// </summary>
    private void PickImage(LibraryGame g, string what, Action<string?> chosen)
    {
        Sfx.Play(Sound.Select);
        _layer = "dialog";
        _dialogBack = () => { DismissDialog(); _layer = "view"; OpenArtwork(g); };
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = 1180,
            MaxHeight = 820,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text(what, "H2", margin: new Thickness(0, 0, 0, 2)));
        sp.Children.Add(Text("תמונות שנמצאו במחשב", "Caption", margin: new Thickness(0, 0, 0, 16)));

        var found = FindImages(g);
        if (found.Count == 0)
        {
            sp.Children.Add(Empty("לא נמצאו תמונות",
                "מחפשים בתיקיית המשחק ובתיקיית התמונות של Windows. אפשר להעתיק לשם קובץ ולנסות שוב."));
        }
        else
        {
            var wrap = new WrapPanel { Margin = new Thickness(0, 0, 0, 8) };
            foreach (var f in found)
            {
                var thumb = LoadImg(f, 200);
                if (thumb is null) continue;   // unreadable/not an image after all
                var b = new Button
                {
                    Style = (Style)FindResource("Tile"),
                    Margin = new Thickness(0, 0, 12, 12),
                    Width = 170,
                    Content = new StackPanel
                    {
                        Children =
                        {
                            new Image
                            {
                                Source = thumb, Height = 110,
                                Stretch = Stretch.UniformToFill,
                                Margin = new Thickness(0, 0, 0, 6),
                            },
                            Text(Ltr(IOPath.GetFileName(f)), "Caption"),
                        },
                    },
                };
                string path = f;
                b.Click += (_, _) => chosen(path);
                wrap.Children.Add(Nav(b));
            }
            sp.Children.Add(new ScrollViewer
            {
                Content = wrap,
                VerticalScrollBarVisibility = ScrollBarVisibility.Disabled,
                MaxHeight = 560,
            });
        }

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 14, 0, 0),
        };
        row.Children.Add(Nav(Ghost(GlyphBack, "ביטול",
            () => { Sfx.Play(Sound.Back); DismissDialog(); _layer = "view"; OpenArtwork(g); })));
        row.Children.Add(Nav(Ghost(GlyphDelete, "ברירת מחדל", () => chosen(null))));
        sp.Children.Add(row);

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("A", "בחר"), ("B", "ביטול"));
        Animate(card);
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusFirst());
    }

    /// <summary>
    /// Candidate images: the game's own folder first (that is where a cover or a
    /// logo that BELONGS to this game lives), then Pictures.
    ///
    /// Depth- and count-capped on purpose: a game folder can hold tens of
    /// thousands of texture files, and a browser that stalls the shell while it
    /// walks them is worse than one that shows fewer results.
    /// </summary>
    private static List<string> FindImages(LibraryGame g)
    {
        var outp = new List<string>();
        string[] ext = { ".png", ".jpg", ".jpeg", ".webp", ".bmp" };

        void Scan(string dir, int depth, int cap)
        {
            if (outp.Count >= 60 || depth < 0 || !Directory.Exists(dir)) return;
            try
            {
                foreach (var f in Directory.EnumerateFiles(dir))
                {
                    if (outp.Count >= 60) return;
                    if (!ext.Contains(IOPath.GetExtension(f), StringComparer.OrdinalIgnoreCase)) continue;
                    // Skip icons and other tiny chrome - they are never artwork.
                    try { if (new FileInfo(f).Length < 8 * 1024) continue; } catch { continue; }
                    outp.Add(f);
                }
                if (depth == 0) return;
                int seen = 0;
                foreach (var d in Directory.EnumerateDirectories(dir))
                {
                    if (++seen > cap || outp.Count >= 60) return;
                    Scan(d, depth - 1, cap);
                }
            }
            catch { }
        }

        if (g.InstallDir is { Length: > 0 }) Scan(g.InstallDir, 2, 24);
        try
        {
            Scan(Environment.GetFolderPath(Environment.SpecialFolder.MyPictures), 1, 24);
        }
        catch { }
        return outp;
    }

    /// <summary>
    /// Game Options -> General: launch arguments + a custom executable.
    ///
    /// Two fields, no browse dialog: a file picker is a mouse surface, and this
    /// shell is driven with a pad. The path is shown pre-filled with the exe we
    /// already resolved, so the common edit is changing a few characters rather
    /// than typing a path from nothing.
    /// </summary>
    private void OpenLaunchOptions(LibraryGame g)
    {
        Sfx.Play(Sound.Select);
        _layer = "dialog";
        _dialogBack = () => { DismissDialog(); _layer = "view"; OpenBlade(g); };
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var prof = Profile(g);
        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(720),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text("אפשרויות הפעלה", "H2", margin: new Thickness(0, 0, 0, 2)));
        sp.Children.Add(Text(g.Name, "Caption", margin: new Thickness(0, 0, 0, 20)));

        TextBox Field(string label, string hint, string value)
        {
            sp.Children.Add(Text(label, "H3", margin: new Thickness(0, 0, 0, 2)));
            sp.Children.Add(Text(hint, "Caption", margin: new Thickness(0, 0, 0, 6)));
            var box = new TextBox
            {
                Text = value,
                Background = Brushes.Transparent,
                BorderThickness = new Thickness(0, 0, 0, 2),
                BorderBrush = (Brush)FindResource("Accent"),
                Foreground = (Brush)FindResource("FgPrimary"),
                CaretBrush = (Brush)FindResource("Accent"),
                FontFamily = new FontFamily("Heebo, Segoe UI"),
                FontSize = 18,
                Padding = new Thickness(0, 0, 0, 7),
                Margin = new Thickness(0, 0, 0, 20),
                // A command line and a Windows path are Latin: left in the RTL
                // flow a leading "-" or "C:" jumps to the wrong end of the line.
                FlowDirection = FlowDirection.LeftToRight,
                TextAlignment = TextAlignment.Left,
            };
            sp.Children.Add(box);
            return box;
        }

        // The example MUST be Ltr()-pinned: a switch opens with "-", a neutral
        // character, so inside a Hebrew sentence the bidi algorithm resolves it
        // to the RTL side and "-eac_launcher" renders as "eac_launcher-" - an
        // instruction that is wrong in exactly the way the user would then type.
        var argsBox = Field("ארגומנטים", "נוספים לשורת הפקודה בהפעלה. לדוגמה: " + Ltr("-eac_launcher"),
                            prof.LaunchArgs ?? "");
        var exeBox = Field("קובץ הפעלה", "השאירו ריק כדי להשתמש בקובץ שזוהה אוטומטית",
                           prof.CustomExe is { Length: > 0 } ? prof.CustomExe : "");

        // The store handle, read-only. It is resolved from the store's own
        // manifests, so it is not ours to edit - but it IS the thing that
        // explains why a game starts through Steam/Ubisoft rather than from a
        // file, and why arguments need a real executable to attach to.
        if (g.LaunchUri is { Length: > 0 } storeUri)
        {
            sp.Children.Add(Text("כתובת הפעלה בחנות", "H3", margin: new Thickness(0, 0, 0, 2)));
            sp.Children.Add(Text(Ltr(storeUri), "Caption", margin: new Thickness(0, 0, 0, 20)));
        }

        // What WILL run, once. A settings screen that cannot tell you the
        // outcome of your own edit is a guess with a Save button.
        var effect = Text("", "Caption", margin: new Thickness(0, 0, 0, 4));
        void Refresh()
        {
            string args = argsBox.Text.Trim(), exe = exeBox.Text.Trim();
            // ⚠️ MIRROR LibraryScanner.Launch()'s LADDER EXACTLY, including its
            // GuessExe fallback. A preview that stops one rung early reports
            // "no executable" for a game that launches perfectly - which is a
            // worse answer than showing nothing at all.
            string target =
                exe.Length > 0                                  ? exe
                : args.Length > 0 && g.Exe is { Length: > 0 }    ? g.Exe
                : g.LaunchUri is { Length: > 0 } u               ? u
                : g.Exe is { Length: > 0 } e2                    ? e2
                : g.InstallDir.Length > 0
                    ? LibraryScanner.GuessExe(g.InstallDir) ?? ""
                    : "";
            if (effect is TextBlock tb)
            {
                tb.Text = target.Length == 0 ? "לא זוהה קובץ הפעלה" : "יופעל: " + Ltr(target + (args.Length > 0 ? " " + args : ""));
                tb.TextWrapping = TextWrapping.Wrap;
            }
        }
        argsBox.TextChanged += (_, _) => Refresh();
        exeBox.TextChanged += (_, _) => Refresh();
        Refresh();
        sp.Children.Add(effect);

        void Commit()
        {
            string exe = exeBox.Text.Trim();
            // Saving a path that does not exist would turn Play into a silent
            // no-op later, far from here - refuse it now, while the field that
            // caused it is on screen.
            if (exe.Length > 0 && !File.Exists(exe))
            {
                Sfx.Play(Sound.Warning);
                ShowToast("קובץ ההפעלה לא נמצא");
                return;
            }
            prof.LaunchArgs = argsBox.Text.Trim();
            prof.CustomExe = exe;
            Save();
            Sfx.Play(Sound.Select);
            DismissDialog(); _layer = "view"; OpenBlade(g);
            ShowToast("אפשרויות ההפעלה נשמרו");
        }
        argsBox.KeyDown += (_, e) => { if (e.Key == Key.Enter) { e.Handled = true; Commit(); } };
        exeBox.KeyDown += (_, e) => { if (e.Key == Key.Enter) { e.Handled = true; Commit(); } };

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 22, 0, 0),
        };
        row.Children.Add(Nav(Ghost(GlyphBack, "ביטול",
            () => { Sfx.Play(Sound.Back); DismissDialog(); _layer = "view"; OpenBlade(g); })));
        if ((prof.LaunchArgs is { Length: > 0 }) || (prof.CustomExe is { Length: > 0 }))
            row.Children.Add(Nav(Ghost(GlyphDelete, "נקה",
                () => { argsBox.Text = ""; exeBox.Text = ""; Commit(); })));
        var ok = new Button
        {
            Style = (Style)FindResource("PrimaryCTA"),
            Content = new TextBlock { Text = "שמור", VerticalAlignment = VerticalAlignment.Center },
            Margin = new Thickness(12, 0, 0, 0),
        };
        ok.Click += (_, _) => Commit();
        row.Children.Add(Nav(ok));
        sp.Children.Add(row);

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("A", "שמור"), ("B", "ביטול"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => argsBox.Focus());
        Animate(card);
    }

    /// <summary>Restore hidden entries - the only way back, by design.</summary>
    private void OpenHidden()
    {
        Sfx.Play(Sound.Select);
        _layer = "dialog";
        _dialogBack = () => { DismissDialog(); _layer = "view"; RenderTab(); };
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(620),
            MaxHeight = 660,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text("משחקים מוסתרים", "H2", margin: new Thickness(0, 0, 4, 4)));
        sp.Children.Add(Text("החזרה תציג אותם שוב בספרייה", "Caption",
                             margin: new Thickness(0, 0, 0, 16)));

        var hidden = _settings.Profiles.Where(pr => pr.Hidden)
                              .OrderBy(pr => NameOfKey(pr.Key), StringComparer.CurrentCulture)
                              .ToList();
        if (hidden.Count == 0)
            sp.Children.Add(Text("אין כרגע משחקים מוסתרים", "Caption"));

        foreach (var pr in hidden)
        {
            var prof = pr;
            sp.Children.Add(Nav(RowButton(GlyphShow, NameOfKey(prof.Key), Ltr(prof.Key),
                () =>
                {
                    prof.Hidden = false;
                    Save();
                    SortLibrary();
                    ShowToast("הוחזר לספרייה");
                    OpenHidden();       // stay put: restoring several is one trip
                })));
        }

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Left,
            Margin = new Thickness(0, 18, 0, 0),
        };
        row.Children.Add(Nav(Ghost(GlyphBack, "סיום",
            () => { Sfx.Play(Sound.Back); DismissDialog(); _layer = "view"; RenderTab(); })));
        sp.Children.Add(row);

        card.Child = Scroller(sp);
        DialogHost.Children.Add(card);
        SetHints(("A", "החזרה"), ("B", "סיום"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusFirst());
        Animate(card);
    }

    /// <summary>The name survives in the raw scan even while the entry is
    /// filtered out of the library - that is the point of keeping _scanned.</summary>
    private string NameOfKey(string key) =>
        _scanned.FirstOrDefault(g => g.Key == key)?.Name ?? key;

    /// <summary>
    /// Winhanced's accent row: a fixed ramp yellow-orange-red-pink-purple, plus
    /// "follow Windows". A fixed set rather than a colour wheel, because every
    /// one of these is checked against the dark ground - a free picker mostly
    /// produces accents that fail on it, and a shell has exactly one accent.
    /// </summary>
    private UIElement AccentRow()
    {
        var box = new StackPanel { Margin = new Thickness(0, 4, 0, 0) };
        box.Children.Add(Text("צבע הדגשה", "Body", margin: new Thickness(4, 0, 4, 2)));
        box.Children.Add(Text("צובע מיקוד, כפתורים ותגיות בכל המסכים", "Caption",
                              margin: new Thickness(4, 0, 4, 10)));

        var row = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(4, 0, 4, 4),
        };

        // "" = follow Windows, and it comes FIRST because it is the default.
        foreach (var (hex, name) in new[]
        {
            ("",        "לפי Windows"),
            ("#FFD23F", "צהוב"),
            ("#FF8A3D", "כתום"),
            ("#F2564B", "אדום"),
            ("#EC4899", "ורוד"),
            ("#A855F7", "סגול"),
            ("#1A9FFF", "כחול"),
            ("#27C08A", "ירוק"),
        })
        {
            string h = hex;
            bool active = _settings.AccentHex == h;
            Color c = h.Length > 0 ? (Color)ColorConverter.ConvertFromString(h)
                                   : Backdrop.AccentColor();

            var dot = new Border
            {
                Width = 30, Height = 30,
                CornerRadius = new CornerRadius(15),
                Background = new SolidColorBrush(c),
                // The CURRENT one carries a ring - a swatch grid with no marked
                // selection is a palette, not a setting.
                BorderBrush = new SolidColorBrush(Color.FromArgb(active ? (byte)0xFF : (byte)0x33, 0xFF, 0xFF, 0xFF)),
                BorderThickness = new Thickness(active ? 3 : 1),
            };
            // "Follow Windows" shows the OS colour with a slash, so it never reads
            // as just another fixed swatch that happens to match.
            if (h.Length == 0)
                dot.Child = new TextBlock
                {
                    Text = GlyphSync,
                    FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
                    FontSize = 13,
                    Foreground = new SolidColorBrush(Color.FromRgb(0x0E, 0x14, 0x1B)),
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center,
                };

            var b = new Button
            {
                Style = (Style)FindResource("GhostButton"),
                Content = dot,
                Padding = new Thickness(6),
                Margin = new Thickness(0, 0, 8, 0),
                Tag = "accent",
            };
            System.Windows.Automation.AutomationProperties.SetHelpText(b, name);
            b.Click += (_, _) => SetAccent(h);
            row.Children.Add(Nav(b));
        }

        box.Children.Add(row);
        return box;
    }

    /// <summary>
    /// Repaint live. Accent lives in a DynamicResource, so every consumer follows
    /// the moment the colour changes - no restart, and no need to know who uses it.
    /// </summary>
    private void SetAccent(string hex)
    {
        _settings.AccentHex = hex;
        Save();

        Color c;
        try
        {
            c = hex.Length > 0 ? (Color)ColorConverter.ConvertFromString(hex)
                               : Backdrop.AccentColor();
        }
        catch { c = Backdrop.AccentColor(); }

        App.ApplyAccent(c);
        // The ambient blobs BAKE the accent into their gradient stops when they
        // are built, so a new accent does not reach them on its own - the
        // backdrop kept the old colour until the next launch.
        BuildBloom();

        Sfx.Play(Sound.Select);
        _focusTag = "accent";

        RenderTab();
    }

    /// <summary>
    /// "What's New" - the hub's own release feed, newest first.
    ///
    /// The card follows Winhanced's NewsCard shape (art, headline, date, source),
    /// but the art is the LINKED GAME's own box art rather than a stock hero
    /// image: it is the picture the reader already associates with the title, we
    /// ship it anyway, and it costs no extra fetch.
    /// </summary>
    private UIElement BuildNews()
    {
        var sp = new StackPanel { Margin = new Thickness(72, 0, 72, 40) };
        sp.Children.Add(Text("מה חדש", "H1", margin: new Thickness(0, 0, 0, 4)));

        var items = Catalog.News();
        if (items.Count == 0)
        {
            sp.Children.Add(Empty("אין עדיין עדכונים",
                "העדכונים נטענים דרך הלאנצ׳ר. פתחו אותו פעם אחת והם יופיעו כאן, גם ללא חיבור לאינטרנט."));
            return sp;
        }

        sp.Children.Add(Text($"{Updates(items.Count)} · הרשימה מתעדכנת דרך הלאנצ׳ר", "Caption",
                             margin: new Thickness(0, 0, 0, 18)));

        foreach (var n in items.Take(40))
        {
            // A news item that names a game we know becomes a shortcut to it -
            // reading about a translation and then having to go find the title
            // in the library is a dead end the feed can just close.
            var game = _scanned.FirstOrDefault(g => g.Hub is not null && g.Hub.Id == n.Link);

            var row = new Grid { Margin = new Thickness(0, 0, 0, 12) };
            // 🔴 114 = the 96 frame PLUS its own 18px gutter, and getting this
            // wrong is why the covers came out sliced down one edge. The art
            // Border carries Width=96 AND Margin(0,0,18,0); a 96-wide column
            // cannot hold both, so WPF resolves the overflow by SHRINKING the
            // element to 78 - a 96-wide frame silently became 78 wide, and the
            // 2:3 art UniformToFill'd into it lost 19% off the side. Nothing in
            // the code says 78 anywhere; it is a layout remainder.
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(96 + 18) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

            // 🔴🔴 96x144, NOT 96x128 — AND AN <Image>, NOT AN ImageBrush.
            //
            // Two separate defects, one line apart, both invisible in code review:
            //
            //  * CUT. Box art in this catalog is 2:3 (600x900). A 3:4 frame under
            //    UniformToFill has to crop 11% off the top and bottom to fill the
            //    width, and on a cover that is exactly where the title sits. The
            //    frame now matches the source ratio, so the fill is a no-op.
            //
            //  * MIRRORED. This was the ONLY ImageBrush left in the shell, and
            //    that is precisely why it was the only picture that came out
            //    backwards. A BRUSH is mapped in its element's own coordinate
            //    space, so RightToLeft mirrors it; an <Image> is a child element
            //    and is NOT mirrored. It is the same trap the scrim gradients
            //    already carry FlowDirection="LeftToRight" for — every Tile in
            //    the shell renders correctly because they all use <Image>.
            var art = new Border
            {
                Width = 96, Height = 144,
                CornerRadius = new CornerRadius(10),
                Background = (Brush)FindResource("GlassChip"),
                Margin = new Thickness(0, 0, 18, 0),
                ClipToBounds = true,
            };
            if (game is not null &&
                LoadImg(Profile(game).CustomBoxArt ?? game.BoxArt ?? game.Hub?.Cover, 200) is { } img)
                art.Child = new Image { Source = img, Stretch = Stretch.UniformToFill };
            else
                art.Child = new TextBlock
                {
                    Text = GlyphNews,
                    FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
                    FontSize = 26,
                    Foreground = (Brush)FindResource("FgDim"),
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center,
                };
            Grid.SetColumn(art, 0);
            row.Children.Add(art);

            var body = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
            var meta = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 6) };
            if (n.Badge.Length > 0) meta.Children.Add(Badge(n.Badge, accent: true));
            meta.Children.Add(new TextBlock
            {
                Text = PrettyDate(n.Date),
                Style = (Style)FindResource("Caption"),
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(10, 0, 0, 0),
            });
            body.Children.Add(meta);
            body.Children.Add(Text(n.Title, "H3", margin: new Thickness(0, 0, 0, 4)));
            if (n.Detail.Length > 0)
            {
                var d = Text(n.Detail, "Caption");
                if (d is TextBlock tb)
                {
                    tb.TextWrapping = TextWrapping.Wrap;
                    tb.LineHeight = 20;
                    // 🔴 NO MaxWidth here. A MaxWidth-constrained Stretch element is
                    // CENTRED by WPF inside a wider parent, so the detail block sat
                    // inset from the headline and its wrapped second line read as a
                    // centred caption. Letting it fill the column puts both edges on
                    // the same margin, which is what makes the feed scan as a column.
                }
                body.Children.Add(d);
            }
            Grid.SetColumn(body, 1);
            row.Children.Add(body);

            // 🔴 EVERY ITEM IS A STOP, EVEN THE ONES THAT LEAD NOWHERE. The old
            // rule here was "focusable only when it leads somewhere", on the
            // theory that highlighting a row whose A does nothing is worse than
            // scrolling past it. It is the other way round: the page scrolls by
            // MOVING FOCUS, so an unfocusable row is not merely un-pressable, it
            // is un-REACHABLE - the cursor jumps clean over it to the next item
            // with a game, taking the view with it, and a long announcement in
            // between can never be brought on screen to be read at all. So all
            // of them take focus; the ones with a destination open it, and the
            // rest answer A with the dead-end cue instead of pretending.
            var card = new Button
            {
                Style = (Style)FindResource("ListRow"),
                Content = row,
                Padding = new Thickness(16, 12, 16, 12),
                Margin = new Thickness(0, 0, 0, 10),
            };
            if (game is not null)
            {
                var g = game;
                card.Click += (_, _) => OpenBlade(g);
            }
            else card.Click += (_, _) => Sfx.Play(Sound.DeadEnd);
            sp.Children.Add(Nav(card));
        }
        return sp;
    }

    /// <summary>2026-08-09 reads as a machine field; "9 באוגוסט 2026" reads as a date.</summary>
    private static string PrettyDate(string iso)
    {
        if (DateTime.TryParse(iso, out var d))
        {
            string[] m = { "בינואר", "בפברואר", "במרץ", "באפריל", "במאי", "ביוני",
                           "ביולי", "באוגוסט", "בספטמבר", "באוקטובר", "בנובמבר", "בדצמבר" };
            return $"{d.Day} {m[d.Month - 1]} {d.Year}";
        }
        return iso;
    }

    /// <summary>Take the card down WITHOUT deciding where focus goes next -
    /// the caller is about to open something itself.</summary>
    private void DismissDialog()
    {
        DialogHost.Visibility = Visibility.Collapsed;
        DialogHost.Children.Clear();
        _dialogBack = null;
        RestoreDialogScrim();
    }

    /// <summary>The scrim is REMOVED by the anchored system panels, so it has to
    /// be put back on the way out - otherwise the next real confirmation opens
    /// over an undimmed screen and reads as part of the page behind it.</summary>
    private void RestoreDialogScrim() =>
        DialogHost.Background = new SolidColorBrush(Color.FromArgb(0xCC, 0, 0, 0));

    private void CloseDialog()
    {
        DialogHost.Visibility = Visibility.Collapsed;
        DialogHost.Children.Clear();
        _dialogBack = null;
        RestoreDialogScrim();

        // 🔴 A CONFIRMATION RAISED FROM THE GAME CARD LEAVES THE CARD ON SCREEN.
        // Landing on the "view" layer there was a lie the user could feel:
        // "הסרה" and "ניקוי מטמון התרגום" both dismissed back to a page that was
        // still hidden behind the panel, so the D-pad moved through covers
        // nobody could see and B did the library's back instead of closing the
        // card. Re-opening the card redraws it with whatever just changed and
        // rebuilds its own map. Visibility, not _layer, because _layer is
        // exactly the field that is wrong at this moment.
        if (Blade.Visibility == Visibility.Visible && _selected is not null) { OpenBlade(_selected); return; }

        _layer = "view";
        RenderTab();
    }

    private static void Run(string exe, string args)
    {
        try { Process.Start(new ProcessStartInfo(exe, args) { UseShellExecute = true, CreateNoWindow = true }); }
        catch { }
    }

    /// <summary>
    /// 🔴 A WARNING THAT LEADS NOWHERE IS JUST NOISE. This used to be a toast
    /// that named the game eating the RAM and then vanished, leaving the one
    /// person who could act on it with no control to press — the eviction API
    /// existed the whole time and nothing ever offered it. Quick Resume's own
    /// bargain is that a parked game keeps every byte of its state in memory,
    /// so "the memory is nearly full" and "you have a parked game" are the same
    /// sentence, and the fix belongs in the same breath as the warning.
    ///
    /// Closing a parked game DESTROYS everything since its last save, so this
    /// goes through the same confirmation every other destructive action does,
    /// with "cancel" holding focus.
    ///
    /// ⚠️ It must never barge in. This fires from a background tick, so it can
    /// land while the user is mid-dialog, in the search box or reading the quick
    /// menu — a modal stealing the screen from something they opened themselves
    /// would be worse than the problem it reports. Anywhere but a plain view, it
    /// stays a toast; with no parked game to close there is nothing to offer, so
    /// it stays a toast then too.
    /// </summary>
    private void OnMemoryWarning(int pct)
    {
        var candidate = _sessions?.EvictionCandidate();
        if (candidate is null)
        {
            Sfx.Play(Sound.Warning);
            ShowToast($"{GlyphWarn}  הזיכרון בשימוש {pct}%");
            return;
        }

        if (_layer != "view")
        {
            Sfx.Play(Sound.Warning);
            ShowToast($"{GlyphWarn}  זיכרון {pct}% - {candidate.Name} מושהה ותופס מקום");
            return;
        }

        Confirm(
            $"הזיכרון כמעט מלא ({pct}%)",
            $"{candidate.Name} מושהה - הוא לא צורך מעבד, אבל הוא עדיין מחזיק את כל " +
            "הזיכרון שלו. סגירתו תפנה אותו מיד, אבל כל מה שלא נשמר במשחק יאבד.",
            $"סגור את {candidate.Name}", destructive: true,
            () => CloseSession(candidate));
    }

    // =====================================================================
    //  boot intro — the loading screen is a film, the way Big Steam opens
    // =====================================================================

    private DispatcherTimer? _introGuard;
    private bool _introDone;

    /// <summary>
    /// Where the opener may live, in order. The state dir comes FIRST so the
    /// person running this can drop in their own film and keep it across every
    /// rebuild and reinstall - the app folder is republished, that one is not.
    /// </summary>
    private static string? IntroPath()
    {
        foreach (var p in new[]
        {
            IOPath.Combine(Catalog.StateDir, "biglaunch_intro.mp4"),
            IOPath.Combine(AppContext.BaseDirectory, "Assets", "intro.mp4"),
        })
        {
            try { if (File.Exists(p)) return p; } catch { }
        }
        return null;
    }

    /// <summary>
    /// Put the opener up and start it. Returns false when there is nothing to
    /// play, so the caller can fall back to the old audio cue.
    ///
    /// 🔴 EVERY EXIT LEADS OUT. A full-screen video is the easiest place in a
    /// shell to strand somebody: a codec the machine does not have, a file that
    /// is half-copied, a decoder that stalls. So the end of the film, a failure,
    /// a keypress, a pad button, a click and a hard timer ALL land on the same
    /// single dismissal - and the timer is armed even if playback never starts.
    /// </summary>
    private bool TryStartIntro()
    {
        // Both of these mean the ctor's guess was wrong (the file went away, or
        // the switch changed) and the black cover is still up - so take it down.
        if (!_settings.IntroEnabled) { IntroHost.Visibility = Visibility.Collapsed; return false; }
        string? path = IntroPath();
        if (path is null) { IntroHost.Visibility = Visibility.Collapsed; return false; }

        try
        {
            _introDone = false;
            _layer = "intro";
            IntroHost.Visibility = Visibility.Visible;
            FooterBar.Visibility = Visibility.Collapsed;   // no legend over a film

            // The film carries its own audio. Muting it when the user has turned
            // the shell's sounds off is the only reading of that switch that is
            // not a surprise at full volume.
            IntroVideo.Volume = _settings.SoundEnabled ? Math.Clamp(_settings.SoundVolume, 0, 1) : 0;
            IntroVideo.IsMuted = !_settings.SoundEnabled;
            IntroVideo.MediaEnded += (_, _) => EndIntro();
            IntroVideo.MediaFailed += (_, _) => EndIntro();
            IntroVideo.Source = new Uri(path);
            IntroVideo.Play();

            // 🔴 NO SKIP HINT ON SCREEN. It was defended as "a full-screen video
            // with no visible exit is the one thing a 10ft shell must never show",
            // and that reasoning is sound for a film somebody is TRAPPED in - but
            // this one is eight seconds, every key and every pad button already
            // ends it, and a line of caption text burned across the bottom of the
            // product's own title card costs it every single launch to teach a
            // thing that is discovered on the first one.
            // 🔴 THE FILM DECIDES WHEN IT IS OVER, NOT A CONSTANT. A flat 20s
            // backstop silently truncated any opener longer than that, which is
            // the opposite of "the shell opens when the film ends". Once the
            // decoder reports a real duration the backstop moves to just past
            // it; until then the constant still covers a decoder that never
            // starts at all.
            IntroVideo.MediaOpened += (_, _) =>
            {
                try
                {
                    if (_introGuard is null) return;
                    var nd = IntroVideo.NaturalDuration;
                    if (!nd.HasTimeSpan) return;
                    _introGuard.Interval = nd.TimeSpan + TimeSpan.FromSeconds(3);
                    _introGuard.Stop();
                    _introGuard.Start();
                }
                catch { }
            };

            // The backstop for a film that never opens at all.
            _introGuard = new DispatcherTimer { Interval = TimeSpan.FromSeconds(20) };
            _introGuard.Tick += (_, _) => EndIntro();
            _introGuard.Start();
            return true;
        }
        catch
        {
            EndIntro();
            return false;
        }
    }

    private void Intro_Click(object sender, MouseButtonEventArgs e) => EndIntro();

    /// <summary>Dismiss the opener - idempotent, because five things call it.</summary>
    private void EndIntro()
    {
        if (_introDone) return;
        _introDone = true;

        _introGuard?.Stop();
        _introGuard = null;

        // Release the decoder. A 4K stream left open costs memory and a GPU
        // queue for the whole session, for a nine-second film nobody sees again.
        try { IntroVideo.Stop(); IntroVideo.Close(); IntroVideo.Source = null; } catch { }

        // Fade rather than cut: the shell underneath is already drawn, so a hard
        // swap reads as a flicker where a dissolve reads as the film ending.
        var fade = new DoubleAnimation(1, 0, TimeSpan.FromMilliseconds(420));
        fade.Completed += (_, _) =>
        {
            IntroHost.Visibility = Visibility.Collapsed;
            IntroHost.Opacity = 1;
        };
        IntroHost.BeginAnimation(OpacityProperty, fade);

        FooterBar.Visibility = Visibility.Visible;
        if (_layer == "intro") _layer = "view";
        FocusFirst();
    }

    // =====================================================================
    //  onboarding — the report's five steps
    // =====================================================================

    private int _onboardStep;

    private void ShowOnboarding()
    {
        _onboardStep = 0;
        _layer = "onboard";
        OnboardHost.Visibility = Visibility.Visible;
        RenderOnboarding();
    }

    private void RenderOnboarding()
    {
        ResetNav();
        _navViewStart = 0;
        OnboardHost.Children.Clear();

        var (title, detail, body) = _onboardStep switch
        {
            0 => ("ברוך הבא לביג לאנץ׳",
                  "מסך משחקים אחד לכל החנויות שמותקנות אצלך - מותאם לשלט ולמסך גדול.",
                  (UIElement?)null),
            1 => ("המכשיר שלך", DeviceSummary(), null),
            2 => ("ספריות המשחקים", "אלה המקורות שנמצאו במחשב. אפשר לשנות בכל רגע בהגדרות.", SourcesSummary()),
            3 => ("התאמה אישית", "צלילים, אנימציות וזכוכית - הכול ניתן לכיבוי אם המחשב חלש.", null),
            _ => ("הכול מוכן", "אפשר להתחיל. הכפתור היחיד שמחזיר ללאנצ׳ר הרגיל נמצא בהגדרות.", null),
        };

        var card = new StackPanel
        {
            MaxWidth = CardWidth(720),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };

        // StepIndicator
        var steps = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Center, Margin = new Thickness(0, 0, 0, 30) };
        for (int i = 0; i < 5; i++)
            steps.Children.Add(new Border
            {
                Width = i == _onboardStep ? 34 : 10, Height = 10,
                CornerRadius = new CornerRadius(5),
                Margin = new Thickness(4, 0, 4, 0),
                Background = i <= _onboardStep ? (Brush)FindResource("Accent") : (Brush)FindResource("GlassChipHi"),
            });
        card.Children.Add(steps);

        card.Children.Add(Text(title, "H1", margin: new Thickness(0, 0, 0, 12)));
        card.Children.Add(Text(detail, "Body", margin: new Thickness(0, 0, 0, 22)));
        if (body is not null) card.Children.Add(body);

        var nav = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Center, Margin = new Thickness(0, 30, 0, 0) };
        nav.Children.Add(Nav(CTA(_onboardStep == 4 ? GlyphCheck : "",
            _onboardStep == 4 ? "התחל" : "הבא", () =>
            {
                if (_onboardStep == 4)
                {
                    _settings.OnboardingDone = true;
                    Save();
                    OnboardHost.Visibility = Visibility.Collapsed;
                    OnboardHost.Children.Clear();
                    _layer = "view";
                    Sfx.Play(Sound.Startup);
                    SetTab("home");
                    return;
                }
                _onboardStep++;
                Sfx.Play(Sound.Select);
                RenderOnboarding();
            })));
        if (_onboardStep > 0)
            nav.Children.Add(Nav(Ghost(GlyphBack, "חזרה", () => { _onboardStep--; Sfx.Play(Sound.Back); RenderOnboarding(); },
                new Thickness(12, 0, 0, 0))));
        card.Children.Add(nav);

        OnboardHost.Children.Add(card);
        // Page one has nowhere to go back TO, so it does not advertise a back.
        if (_onboardStep > 0) SetHints(("A", "המשך"), ("B", "חזרה"));
        else SetHints(("A", "המשך"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusFirst());
        Animate(card);
    }

    private string DeviceSummary()
    {
        _tel.Sample();
        var drives = Storage.Drives();
        string bat = Telemetry.Battery() is { } b ? $" · סוללה {b:0}%" : " · מחובר לחשמל";
        return $"זיכרון {_tel.RamTotalGb:0.#} GB · {drives.Count} כוננים{bat}" +
               (_pad?.Connected == true ? " · שלט מחובר" : " · לא זוהה שלט");
    }

    private UIElement SourcesSummary()
    {
        var sp = new StackPanel();
        foreach (var grp in _all.GroupBy(g => g.Source).OrderByDescending(g => g.Count()))
        {
            if (grp.Key == GameSource.Hub) continue;
            sp.Children.Add(Text($"{grp.First().SourceLabel} - {Titles(grp.Count())}", "Body",
                margin: new Thickness(0, 0, 0, 6)));
        }
        if (sp.Children.Count == 0) sp.Children.Add(Text("עדיין לא נמצאו משחקים", "Subtext"));
        return sp;
    }

    // =====================================================================
    //  actions
    // =====================================================================

    private void Primary(LibraryGame g)
    {
        if (g.Installed && g.Source != GameSource.Hub) PlayGame(g);
        else OpenBlade(g);
    }

    /// <summary>A row that reports state and is deliberately NOT clickable —
    /// used wherever the honest answer is "this is managed elsewhere".</summary>
    /// <summary>
    /// The signed-in identity, as a card rather than a row: a monogram disc in
    /// the live accent, the name at heading weight, the address under it and a
    /// state pill. Nothing here is pressable - signing in and out both happen in
    /// the desktop launcher - so it is deliberately built from plain elements
    /// and never takes focus; a card that highlights and does nothing is the
    /// same lie a dead row is.
    /// </summary>
    private UIElement AccountCard(ShellBridge.Account a)
    {
        var grid = new Grid { Margin = new Thickness(4, 2, 4, 2) };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        // The monogram falls back to the glyph when the name starts with
        // something that has no sensible single letter (an address, a digit).
        string initial = "";
        foreach (char c in a.Name)
            if (char.IsLetter(c)) { initial = char.ToUpperInvariant(c).ToString(); break; }

        var disc = new Border
        {
            Width = 58, Height = 58,
            CornerRadius = new CornerRadius(29),
            Background = (Brush)FindResource("Accent"),
            Margin = new Thickness(0, 0, 18, 0),
            VerticalAlignment = VerticalAlignment.Center,
            Child = initial.Length > 0
                ? new TextBlock
                {
                    Text = initial,
                    FontSize = 25,
                    FontWeight = FontWeights.SemiBold,
                    Foreground = new SolidColorBrush(Colors.White),
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center,
                }
                : new TextBlock
                {
                    Text = GlyphUser,
                    FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
                    FontSize = 24,
                    Foreground = new SolidColorBrush(Colors.White),
                    HorizontalAlignment = HorizontalAlignment.Center,
                    VerticalAlignment = VerticalAlignment.Center,
                },
        };
        Grid.SetColumn(disc, 0);
        grid.Children.Add(disc);

        var col = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
        col.Children.Add(new TextBlock
        {
            Text = a.Name,
            Style = (Style)FindResource("H3"),
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        if (a.Email.Length > 0)
            col.Children.Add(new TextBlock
            {
                // An address is a Latin token in a Hebrew line: fenced, or the
                // dot and the @ mirror into nonsense.
                Text = Ltr(a.Email),
                Style = (Style)FindResource("Caption"),
                Margin = new Thickness(0, 4, 0, 0),
                TextTrimming = TextTrimming.CharacterEllipsis,
            });
        Grid.SetColumn(col, 1);
        grid.Children.Add(col);

        var pill = Badge("מחוברים", accent: true);
        if (pill is FrameworkElement fe) fe.VerticalAlignment = VerticalAlignment.Center;
        Grid.SetColumn((UIElement)pill, 2);
        grid.Children.Add((UIElement)pill);

        return Card(grid);
    }

    private UIElement InfoRow(string glyph, string title, string detail)
    {
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var g = new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 17,
            Foreground = (Brush)FindResource("Accent"),
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 14, 0),
        };
        Grid.SetColumn(g, 0);

        var col = new StackPanel();
        col.Children.Add(new TextBlock { Text = title, Style = (Style)FindResource("Body"), FontWeight = FontWeights.Medium });
        col.Children.Add(new TextBlock
        {
            Text = detail,
            Style = (Style)FindResource("Caption"),
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 3, 0, 0),
        });
        Grid.SetColumn(col, 1);

        grid.Children.Add(g);
        grid.Children.Add(col);
        return grid;
    }

    private void PlayGame(LibraryGame g)
    {
        Sfx.Play(Sound.Launch);
        _settings.LastGameKey = g.Key;
        Save();

        var proc = LibraryScanner.Launch(g, _settings);
        if (proc is null && g.LaunchUri is null)
        {
            Sfx.Play(Sound.DeadEnd);
            ShowToast("לא נמצא קובץ הפעלה - אפשר להגדיר אותו ידנית");
            return;
        }

        _watcher?.Arm();
        var s = _sessions!.Track(g, proc);
        ShowToast($"{g.Name} - מופעל");
        WatchForBlockedLaunch(s);
        _ = UpdatePresenceAsync();

        if (Blade.Visibility == Visibility.Visible) CloseBlade();
    }

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);

    private static bool ForegroundIsOurs()
    {
        try
        {
            GetWindowThreadProcessId(GetForegroundWindow(), out uint pid);
            return pid == (uint)Environment.ProcessId;
        }
        catch { return false; }
    }

    /// <summary>
    /// A launch that produces nothing usually means the STORE is asking
    /// something - behind us.
    ///
    /// 🔴🔴 A MAXIMISED BORDERLESS SHELL HIDES THE DIALOG THAT IS BLOCKING IT.
    /// Steam and the others raise their own windows (an update prompt, a EULA,
    /// a "which launch option" chooser) WITHOUT stealing focus, so they open
    /// underneath this window and the user is left staring at a console where
    /// nothing is happening and no key helps. If the game has not appeared after
    /// a few seconds and we are STILL the foreground window - nothing else took
    /// over - then either something is waiting behind us or the launch failed
    /// silently, and both are better served by stepping aside than by covering
    /// them up.
    ///
    /// The foreground test is the whole safety of this: if the game did come up,
    /// or the user went somewhere themselves, we are not in front and this does
    /// nothing at all.
    /// </summary>
    private void WatchForBlockedLaunch(GameSession s)
    {
        var t = new DispatcherTimer { Interval = TimeSpan.FromSeconds(8) };
        t.Tick += (_, _) =>
        {
            t.Stop();
            if (s.Confirmed) return;                      // the game is up - nothing to do
            if (!_sessions!.Sessions.Contains(s)) return;  // the session already ended
            if (!ForegroundIsOurs()) return;               // something else is in front

            ShowToast("המשחק עדיין לא עלה - ייתכן שהחנות מבקשת משהו. ממזערים כדי להראות");
            WindowState = WindowState.Minimized;
        };
        t.Start();
    }

    /// <summary>Bring the console back when a game ends - a shell that stays
    /// minimised after the thing it launched has closed has left the user on a
    /// desktop they never asked for.</summary>
    private void RestoreShell()
    {
        try
        {
            if (WindowState == WindowState.Minimized) WindowState = WindowState.Maximized;
            Activate();
        }
        catch { }
    }

    /// <summary>
    /// Land a session action back on whatever the user is ACTUALLY looking at.
    ///
    /// 🔴🔴 RenderTab() HERE REBUILT THE PAGE BEHIND AN OPEN CARD. Suspend and
    /// resume are pressed FROM the card, and RenderTab starts with ResetNav() -
    /// so pressing "השהיה" left the panel on screen with its D-pad map replaced
    /// by the hidden library's, and the stick started walking through covers
    /// nobody could see. Re-opening the card instead redraws it with the new
    /// state AND rebuilds its own map, which is the pattern the favourites
    /// toggle beside it already used.
    ///
    /// ⚠ It keys on Blade.Visibility, not on _layer, because a confirmation
    /// dismisses itself back to the "view" layer WITHOUT touching the panel
    /// underneath - so after "סגור את המשחק" the field says view while the card
    /// is still the thing on screen. Visibility is the honest signal.
    /// </summary>
    private void AfterSessionChange()
    {
        if (Blade.Visibility == Visibility.Visible && _selected is not null) { OpenBlade(_selected); return; }
        // The quick menu's own handler closes itself right after this, and
        // CloseQuick renders on the way out - rendering here as well would
        // build the page twice and throw the first one away.
        if (_layer == "quick") return;
        RenderTab();
    }

    private void SuspendSession(GameSession s)
    {
        if (!_settings.QuickResume) { ShowToast("השהיה כבויה בהגדרות"); return; }
        ShowToast(_sessions!.Suspend(s) ? $"{s.Name} הושהה" : "לא ניתן להשהות את המשחק הזה");
        AfterSessionChange();
    }

    private void ResumeSession(GameSession s)
    {
        ShowToast(_sessions!.Resume(s) ? $"{s.Name} חודש" : "לא ניתן לחדש");
        AfterSessionChange();
    }

    /// <summary>
    /// End a session and free its memory — the eviction path the coordinator
    /// has always had and nothing ever called.
    ///
    /// The bookkeeping is deliberately left to the coordinator's own tick: it
    /// already banks playtime, raises Exited and drops the row the moment the
    /// process really dies, and a second copy of that logic here would be one
    /// more place to get the playtime double-counted. All this does is ask.
    /// </summary>
    private void CloseSession(GameSession s)
    {
        ShowToast(_sessions!.Close(s) ? $"{s.Name} נסגר" : "לא ניתן לסגור את המשחק");
        AfterSessionChange();
    }

    private void TakeScreenshot()
    {
        string? p = Capture.Take();
        ShowToast(p is null ? "צילום המסך נכשל" : "צילום מסך נשמר");
    }

    /// <summary>
    /// THE handoff — deliberately the ONLY route from the console back to the
    /// desktop launcher, and it lives in Settings. Nothing else in this shell
    /// opens TranslationManager.exe behind the user's back.
    /// </summary>
    private void HandOff(string? gameId)
    {
        if (!Catalog.OpenDesktop(gameId))
        {
            Sfx.Play(Sound.DeadEnd);
            ShowToast("לא נמצא הלאנצ׳ר במחשב");
            return;
        }
        // 🔴 AND GET OUT OF ITS WAY. This window is a MAXIMIZED BORDERLESS shell,
        // so "opening" the launcher behind it looked like nothing happening at
        // all - a toast, and the same full-screen console still covering the
        // desktop. Minimising IS the crossing; it does not close the console
        // (that would break the one-way-out rule), it parks it in the taskbar
        // so the user can come straight back.
        WindowState = WindowState.Minimized;
        ShowToast("הלאנצ׳ר נפתח - ביג לאנץ׳ ממתין בשורת המשימות");
    }

    // ---- Discord: connect ONCE was not enough -----------------------------
    //
    // ORDER OF LAUNCH DECIDED WHETHER THE FEATURE EXISTED. The connect ran a
    // single time at boot and never again, so a user whose shell starts with
    // Windows - before Discord finishes loading - simply had no rich presence,
    // for the whole session, with a settings row that said "לא מחובר" and no
    // way to retry short of restarting the console. The same hole swallowed
    // every Discord restart and every update it installs on itself.
    //
    // The retry is BACKED OFF rather than periodic: someone who does not run
    // Discord at all must not pay ten pipe probes a minute forever, so the gap
    // doubles to five minutes and stays there, and resets the moment a connect
    // succeeds. And it stops entirely while the presence toggle is off.
    private DateTime _discordNextTry = DateTime.MinValue;
    private int _discordGap = 15;
    private bool _discordBusy;

    private async Task ConnectDiscordAsync()
    {
        if (!_settings.DiscordPresence || string.IsNullOrWhiteSpace(_settings.DiscordAppId)) return;
        if (_discord is { Connected: true } || _discordBusy) return;
        if (DateTime.UtcNow < _discordNextTry) return;

        _discordBusy = true;
        _discordNextTry = DateTime.UtcNow.AddSeconds(_discordGap);
        _discordGap = Math.Min(300, _discordGap * 2);
        try
        {
            // A dead client is disposed before a new one replaces it - the old
            // pipe handle is what a "connected" flag would otherwise keep alive.
            try { _discord?.Dispose(); } catch { }
            _discord = new DiscordRpc(_settings.DiscordAppId);
            if (await _discord.ConnectAsync())
            {
                _discordGap = 15;
                await UpdatePresenceAsync();
            }
        }
        catch { }
        finally { _discordBusy = false; }
    }

    private async Task UpdatePresenceAsync()
    {
        if (!_settings.DiscordPresence) return;
        // A write that failed cleared Connected; this is where that is noticed.
        if (_discord is null or { Connected: false }) { await ConnectDiscordAsync(); return; }
        try
        {
            var s = _sessions?.Sessions.FirstOrDefault(x => !x.Suspended);
            if (s is null) await _discord.SetActivityAsync("בביג לאנץ׳", null, null);
            else await _discord.SetActivityAsync($"משחק ב-{s.Name}", null, s.StartedUtc);
        }
        catch { }
    }

    // =====================================================================
    //  toast
    // =====================================================================

    private DispatcherTimer? _toastTimer;

    private void ShowToast(string text)
    {
        ToastText.Text = text;
        Toast.Visibility = Visibility.Visible;
        if (_settings.AnimationsEnabled)
            Toast.BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, (Duration)FindResource("DurQuick")));
        else Toast.Opacity = 1;

        _toastTimer?.Stop();
        _toastTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(3.2) };
        _toastTimer.Tick += (_, _) => { _toastTimer!.Stop(); HideToast(); };
        _toastTimer.Start();
    }

    private void HideToast()
    {
        if (!_settings.AnimationsEnabled) { Toast.Visibility = Visibility.Collapsed; return; }
        var a = new DoubleAnimation(Toast.Opacity, 0, (Duration)FindResource("DurQuick"));
        a.Completed += (_, _) => Toast.Visibility = Visibility.Collapsed;
        Toast.BeginAnimation(OpacityProperty, a);
    }

    // =====================================================================
    //  focus tree
    // =====================================================================

    private T Nav<T>(T el) where T : FrameworkElement
    {
        _nav.Add(el);
        return el;
    }

    private static bool Usable(FrameworkElement e) =>
        e.IsVisible && e.IsEnabled && e.ActualWidth > 0 && e.ActualHeight > 0;

    private void FocusFirst()
    {
        // 🔴 "FIRST" IS NOT ALWAYS "MOST USEFUL". A view is built in reading
        // order, so the control that happens to be registered first is an
        // accident of layout - on a game that is not installed that made
        // "add to favourites" the loudest, pre-focused thing on the panel while
        // the one action that matters (install the Hebrew translation) sat
        // quietly below it. A view may nominate the action its CURRENT state
        // makes primary; when it does not, first-in-content still wins.
        if (_navPreferred >= 0 && _navPreferred < _nav.Count && Usable(_nav[_navPreferred]))
        {
            _nav[_navPreferred].Focus();
            return;
        }
        // Skip the chrome: the tab pills are reachable with "up" and the
        // bumpers, but a view must open with focus on its CONTENT.
        var first = _nav.Skip(_navViewStart).FirstOrDefault(Usable);
        if (first is not null) { first.Focus(); return; }

        // 🔴 A VIEW WITH NOTHING TO PRESS MUST NOT LAND ON THE **FIRST** TAB.
        // "ביצועים" is a readout — no buttons at all — so the old fallback took
        // the first usable control in the whole map, which is the leftmost pill:
        // the ring sat on "בית" while "ביצועים" was the open tab, and A on a
        // pad would have navigated Home from a screen the user had just opened.
        // Falling back to the pill for the CURRENT tab keeps the ring where the
        // user actually is, and re-activating it is a documented no-op.
        var own = _nav.FirstOrDefault(c => c is RadioButton { Tag: string k } && k == _tab && Usable(c));
        (own ?? _nav.FirstOrDefault(Usable))?.Focus();
    }

    /// <summary>Focus the n-th navigable element, falling back to the first.</summary>
    private void FocusIndex(int i)
    {
        if (i > 0 && i < _nav.Count && Usable(_nav[i])) { _nav[i].Focus(); return; }
        FocusFirst();
    }

    private Rect RectOf(FrameworkElement e)
    {
        try { return e.TransformToVisual(Root).TransformBounds(new Rect(e.RenderSize)); }
        catch { return Rect.Empty; }
    }

    /// <summary>
    /// True when a text-entry control owns the keyboard.
    ///
    /// 🔴 A PasswordBox IS NOT A TextBox. Every guard here used to test TextBox
    /// alone, which was complete right up until the Wi-Fi panel added a password
    /// field: typing a key into it would have been fine, but Backspace would have
    /// closed the dialog and Left/Right would have moved the focus ring off the
    /// field — i.e. the one moment a user is definitely typing is the one moment
    /// the shell stopped listening. One predicate, so a THIRD kind of field can
    /// never re-open the same hole.
    /// </summary>
    private static bool IsTextEntry() =>
        Keyboard.FocusedElement is TextBox or PasswordBox;

    /// <summary>
    /// Nearest focusable in a direction, scored on the rectangle GAP rather
    /// than centre distance — so a full-width row directly below a small
    /// button is still "down", which centre-distance gets wrong.
    ///
    /// 🔴 RTL: this window is RightToLeft, so LAYOUT x grows toward the visual
    /// LEFT. Pressing Right therefore looks for a SMALLER x. Verified by
    /// reading the ORDER of the items, never by looking at a screenshot.
    /// </summary>
    private void Move(Pad dir)
    {
        // Put the volume claim HERE and not only in the key handler, so it holds
        // for the CONTROLLER too - the pad routes through Move(), and a control
        // that answers the keyboard but not the stick is the worse half of a
        // 10ft shell.
        // 🔴 THE HANDLE FOLLOWS THE KEY, WHICH IN A MIRRORED TRACK INVERTS THE SIGN.
        // Every slider in this shell fills from the RIGHT, so the low end is on
        // the right and the high end on the left. Mapping "right" to "+" made
        // the handle travel left when you pressed right - the exact complaint.
        // Windows mirrors its own sliders' arrow keys for the same reason: what
        // a direction key promises is a DIRECTION, not an arithmetic sign.
        if (dir == Pad.Left && VolumeStep(+5)) return;
        if (dir == Pad.Right && VolumeStep(-5)) return;

        // Same claim for a value row inside a system panel (master volume, an app's
        // level). It has to sit beside the one above rather than inside the panel
        // code, because THIS is the single door both the keyboard and the pad come
        // through - a slider that answers one and not the other is a bug the user
        // reads as "the stick is broken".
        if ((dir == Pad.Left || dir == Pad.Right) && StepFocusedRow(dir == Pad.Left ? +5 : -5)) return;

        var items = _nav.Where(Usable).ToList();
        if (items.Count == 0) return;

        var current = items.FirstOrDefault(i => i.IsKeyboardFocused);
        if (current is null) { items[0].Focus(); return; }

        Rect a = RectOf(current);
        FrameworkElement? best = null;
        double bestScore = double.MaxValue;

        foreach (var e in items)
        {
            if (ReferenceEquals(e, current)) continue;
            Rect b = RectOf(e);
            if (b.IsEmpty) continue;

            double dx = b.X - a.X, dy = b.Y - a.Y;
            double primary, cross;

            switch (dir)
            {
                case Pad.Up:
                    if (b.Bottom > a.Top + 1) continue;
                    primary = a.Top - b.Bottom; cross = Gap(a.Left, a.Right, b.Left, b.Right); break;
                case Pad.Down:
                    if (b.Top < a.Bottom - 1) continue;
                    primary = b.Top - a.Bottom; cross = Gap(a.Left, a.Right, b.Left, b.Right); break;
                case Pad.Right:                       // RTL: visual right = smaller x
                    if (b.Right > a.Left + 1) continue;
                    primary = a.Left - b.Right; cross = Gap(a.Top, a.Bottom, b.Top, b.Bottom); break;
                case Pad.Left:
                    if (b.Left < a.Right - 1) continue;
                    primary = b.Left - a.Right; cross = Gap(a.Top, a.Bottom, b.Top, b.Bottom); break;
                default: continue;
            }

            // Cross-axis drift is penalised heavily: moving "down" must not
            // teleport across the screen just because something is closer.
            double score = Math.Max(primary, 0) + cross * 3.2;
            if (score < bestScore) { bestScore = score; best = e; }
        }

        if (best is null)
        {
            SmoothScroll.Trace($"move {dir} DEAD-END from {a.Top:0}..{a.Bottom:0} " +
                               $"x{a.Left:0}..{a.Right:0} of {items.Count} usable");
            Sfx.Play(Sound.DeadEnd);
            return;
        }
        SmoothScroll.Trace($"move {dir} -> {RectOf(best).Top:0}..{RectOf(best).Bottom:0} score={bestScore:0}");
        best.Focus();

        // 🔴 BringIntoView STOPS the moment the focused row is on screen, so
        // anything placed BELOW the last focusable element - a footer, a brand
        // block, a closing note - is unreachable with a controller: the page
        // never scrolls those last pixels. MEASURED on settings (outer extent
        // 2241, viewport 909): landing on the last row leaves the offset ~74px
        // short of the end, and forcing ScrollToEnd afterwards - at Input AND at
        // ContextIdle priority - was overwritten both times by WPF's own
        // focus-driven scroll. So this is a LAYOUT rule, not a scrolling one:
        // A PAGE MUST NOT PUT CONTENT AFTER ITS LAST FOCUSABLE ROW.
        //
        // 🔴 AND BECAUSE IT STOPS AT "BARELY ON SCREEN", THE ROW LANDS EXACTLY
        // INSIDE THE EDGE FADE. Seen on the game blade the moment its scroller
        // got the dissolve: arrowing down to a row near the bottom left it
        // focused - blue ring and all - while the fade was busy making it
        // half-transparent. A focus ring on a fading element is the worst of
        // both, and the fade is not the thing to weaken: the ramp exists so
        // content reads as continuing past the edge, and shrinking it to dodge
        // this would just bring the guillotine back.
        //
        // So ASK FOR MORE THAN THE ELEMENT. BringIntoView(Rect) takes a region in
        // the element's own coordinates, so inflating it vertically makes WPF
        // scroll until the real row clears the fade entirely. Inflated on BOTH
        // sides deliberately - one rule then covers moving down into the bottom
        // ramp and up into the top one - and it clamps harmlessly at either end.
        //
        // ⚠ A page inside a tab host never reaches this: SmoothScroll.Bring
        // handles RequestBringIntoView on the content, recomputes the offset from
        // the element's own rect and marks it Handled. This is what parks rows on
        // the scrollers that are NOT hosts - the blade above all - which is also
        // why the distance is taken from SmoothScroll rather than repeated here.
        double clear = SmoothScroll.FocusTailroom;
        best.BringIntoView(new Rect(
            0, -clear, best.ActualWidth, best.ActualHeight + clear * 2));
    }

    private static double Gap(double a1, double a2, double b1, double b2)
    {
        if (b2 < a1) return a1 - b2;
        if (b1 > a2) return b1 - a2;
        return 0;                       // overlapping on this axis = perfectly aligned
    }

    // =====================================================================
    //  input
    // =====================================================================

    // Where the pointer was when we last hid it, so a real mouse movement can be
    // told from the pointer simply being where it was left.
    private Point _cursorAt;

    /// <summary>
    /// Hide the pointer while the pad is driving, bring it back the moment the
    /// mouse moves.
    ///
    /// 🔴 A MOUSE POINTER PARKED IN THE MIDDLE OF A 10FT SCREEN IS A DEAD PIXEL
    /// NOBODY CAN EXPLAIN. Nothing in this shell moves it, so it sits wherever
    /// it was left - over a cover, in the middle of a film - for as long as the
    /// session lasts, and from a sofa it reads as a rendering fault rather than
    /// as a cursor. It comes back on the first real movement, because the one
    /// thing worse than a stray pointer is a missing one.
    /// </summary>
    private void HidePointer()
    {
        if (Mouse.OverrideCursor == Cursors.None) return;
        try
        {
            _cursorAt = Mouse.GetPosition(this);
            Mouse.OverrideCursor = Cursors.None;
        }
        catch { }
    }

    private void ShowPointer()
    {
        if (Mouse.OverrideCursor != Cursors.None) return;
        try { Mouse.OverrideCursor = null; } catch { }
    }

    private void OnPad(Pad p)
    {
        // 🔴🔴 THE PAD BELONGS TO WHATEVER IS IN FRONT, AND THAT IS USUALLY THE GAME.
        //
        // The input poll runs for as long as this process does, and nothing here
        // asked whether the shell was the active window - so every stick flick
        // and every button press DURING A GAME was still walking the focus ring
        // around a screen nobody could see. Harmless-looking until you consider
        // what a hidden "A" does: it activates whatever that invisible cursor is
        // sitting on, which can be another game's Play button or the confirm
        // step of a removal. A shell in the background must be deaf.
        //
        // No escape chord is claimed here on purpose: the buttons a running game
        // does not use are the game's to define, and fighting it for Guide is how
        // an overlay ends up eating inputs mid-fight.
        //
        // ⚠ NOT a bare !IsActive. Windows hands activation away for reasons that
        // have nothing to do with a game - a toast, an installer, a stray click -
        // and a shell that goes deaf on any of them strands a person holding a
        // controller with no way back. The condition is "something we launched is
        // running AND we are not in front", which is the only case where the pad
        // demonstrably belongs to someone else.
        if (!IsActive && _sessions is { Sessions.Count: > 0 }) return;

        RefreshPadKind(usedPad: true);
        HidePointer();

        // Same rule as the keyboard: any button skips the opener, and only that.
        if (_layer == "intro") { EndIntro(); return; }

        // A rebind screen has to be able to eat the very button that would
        // otherwise close it, so the capture gets first refusal on every press.
        if (CapturePad(p)) return;

        // The four directions are movement and are never rebindable; everything
        // else is looked up in the map (see MainWindow.Mapping.cs).
        if (p is Pad.Up or Pad.Down or Pad.Left or Pad.Right) { Move(p); return; }
        if (ActionForPad(p) is { } act) InvokeAction(act);
    }

    /// <summary>
    /// A control that re-renders the page UNDER ITSELF must come back with focus
    /// still on it - otherwise cycling the sort once throws you to the top of the
    /// library and the second press is unreachable. Set before RenderTab, consumed
    /// once by the focus pass.
    /// </summary>
    private string? _focusTag;

    /// <summary>
    /// The game to put the cursor back on after the next render.
    ///
    /// 🔴 CLOSING A GAME PANEL DROPPED YOU AT THE FIRST TILE IN THE ROW. The
    /// screen is rebuilt on the way out, and a rebuilt screen focuses its first
    /// element - so backing out of the fourth cover to look at the fifth put you
    /// at the first, every time, and the further along the shelf you were the
    /// worse it got. _focusTag already existed for named controls, but a tile's
    /// Tag is the GAME object, not a string, so no tile could ever match it.
    /// </summary>
    private string? _focusGameKey;

    // States only — the storefront chips are appended by FilterOrder() from
    // SourceChips(), because which stores exist depends on the machine.
    private static readonly string[] FilterKeys = { "all", "installed", "uninst", "recent", "fav", "translated" };

    private void CycleFilter(int delta)
    {
        var keys = FilterOrder();
        int i = Array.IndexOf(keys, _filter);
        if (i < 0) i = 0;
        SetFilter(keys[(i + delta + keys.Length) % keys.Length]);
        Sfx.Play(Sound.Navigate);
        RenderTab();
    }

    /// <summary>
    /// 🔴🔴 ORDER THE TYPE TESTS MOST-DERIVED FIRST. RadioButton IS a ButtonBase
    /// (RadioButton : ToggleButton : ButtonBase), so a `is ButtonBase` test
    /// written first swallows every toggle and the `is RadioButton` line below
    /// it is UNREACHABLE. The tab pills and the library filter chips are both
    /// RadioButtons that act on Checked, not on Click — so raising Click left
    /// IsChecked untouched and A/Enter did literally nothing on either surface,
    /// on the keyboard AND on the pad. It looked like a focus bug (the pill lit
    /// up, so the input clearly arrived) rather than a dispatch bug, which is
    /// exactly why it survived: the only visible symptom was "the tab
    /// highlights but the screen doesn't change".
    /// </summary>
    private void ActivateFocused()
    {
        switch (Keyboard.FocusedElement)
        {
            // A radio is a CHOICE: re-activating the current one is a no-op by
            // design, never a re-render.
            case RadioButton r:
                if (r.IsChecked != true) r.IsChecked = true;
                return;
            case ToggleButton t:
                t.IsChecked = t.IsChecked != true;
                return;
            case ButtonBase b:
                b.RaiseEvent(new RoutedEventArgs(ButtonBase.ClickEvent));
                return;
        }
    }

    /// <summary>
    /// B / Escape. 🔴 At the ROOT it deliberately does NOT return to the
    /// desktop launcher: the ONLY route back is the single button in Settings.
    /// So the root B opens the quick menu instead of leaving.
    /// </summary>
    private void Back()
    {
        switch (_layer)
        {
            case "intro": EndIntro(); return;
            case "blade": CloseBlade(); return;
            case "quick": Sfx.Play(Sound.Back); CloseQuick(); return;
            case "search": Sfx.Play(Sound.Back); CloseSearch(); return;
            case "dialog":
                Sfx.Play(Sound.Back);
                // A confirmation returns to the menu that raised it; a plain
                // dialog closes. One step back, never a jump to the library.
                if (_dialogBack is { } back) { _dialogBack = null; back(); return; }
                CloseDialog();
                return;
            case "onboard":
                // 🔴 THE LEGEND PROMISED B = חזרה AND B DID NOTHING. The wizard's
                // back lived only in its own on-screen button, so the one hint
                // printed at the bottom of a first-run user's very first screen
                // was a lie. There is no way back OUT of page one - onboarding
                // is not skippable - so page one stays silent instead of
                // pretending, and the hint below is hidden to match.
                if (_onboardStep > 0) { _onboardStep--; Sfx.Play(Sound.Back); RenderOnboarding(); }
                return;
            default:
                // A SUB-PAGE IS A LEVEL, EVEN WHEN IT IS NOT A DIALOG. The size
                // sliders replace the settings rows in place - deliberately, you
                // have to see the shell resize while you drag - which meant the
                // shell had no idea it was one level deeper, and B threw the user
                // from the sliders all the way out to Home. Everything else on
                // that screen steps back one; this one screen skipped a floor.
                if (_sizesOpen && _tab == "settings")
                {
                    _settings.Save();          // the last notch becomes final here
                    _sizesOpen = false;
                    Sfx.Play(Sound.Back);
                    RenderTab();
                    return;
                }
                if (_tab != "home") { SetTab("home"); return; }
                OpenQuickMenu();
                return;
        }
    }

    /// <summary>
    /// 🔴🔴 THIS IS A **PREVIEW** (TUNNELING) HANDLER, DELIBERATELY. A console
    /// shell owns its D-pad: navigation must not depend on which control happens
    /// to hold focus. On the bubbling KeyDown it did - the moment the content was
    /// wrapped in a ScrollViewer, the ScrollViewer's own arrow-key handling ate
    /// every arrow, marked it handled, and Move() stopped being called at all.
    /// Focus still crept, because WPF's default directional navigation was doing
    /// it, which is why it looked like "the nav sometimes works": one press moved,
    /// the next did nothing. Tunneling puts the shell first, before any control.
    /// </summary>
    private void OnKeyDown(object sender, KeyEventArgs e)
    {
        RefreshPadKind(usedPad: false);

        // ANY key skips the opener - and nothing else happens on that press.
        // Letting it fall through would fire the shell's own binding for that
        // key against a screen the user has not seen yet.
        if (_layer == "intro") { EndIntro(); e.Handled = true; return; }

        // 🔴🔴 A FIELD THAT HOLDS THE KEYBOARD OWNS EVERY PRINTABLE KEY.
        // This switch claims LETTER keys for the shell (Y = search, X = quick
        // menu) and marks them handled - so while the search box was open, 'y'
        // and 'x' never reached it. On a Hebrew layout those two keys are ט and
        // ס: two ordinary letters that simply could not be typed into the one
        // screen in this shell whose entire purpose is typing, with nothing on
        // screen to explain why.
        //
        // Guarding each letter case one at a time is how that hole reopens the
        // next time a binding is added, so the rule lives ABOVE the switch: while
        // a field has focus the shell keeps only the keys that mean "move",
        // "commit" or "leave", and every other key belongs to the field.
        if (IsTextEntry() && e.Key is not (Key.Up or Key.Down or Key.Left or Key.Right
                or Key.Enter or Key.Escape or Key.Back or Key.F5 or Key.F12))
        {
            // 🔴 RETURNING WITHOUT HANDLING LETS Tab WALK OUT OF THE MODAL.
            // Every other key here is a character and belongs to the field, so
            // falling through to WPF is exactly right - but Tab is not a
            // character, it is WPF's OWN focus command, and the overlay hosts
            // are siblings of the page in the visual tree. So one Tab inside the
            // search box moved the ring onto a control on the screen BEHIND the
            // overlay: invisible focus, and the next Enter pressing something
            // the user could not see. Tab is swallowed while a field has the
            // keyboard; moving between the fields of a card is what the arrows
            // already do. (KeyboardNavigation.TabNavigation=Cycle on the hosts
            // is the belt to this braces - see OnLoaded.)
            if (e.Key is Key.Tab) e.Handled = true;
            return;
        }

        // A rebind screen eats the key that would otherwise dismiss it.
        if (CaptureKey(e.Key)) { e.Handled = true; return; }

        // 🔴 THE REBOUND KEYS ARE CHECKED BEFORE THE BUILT-IN SWITCH, NOT INSTEAD
        // OF IT. Arrows, Enter and Escape carry behaviour that is contextual
        // rather than a plain command - Enter commits a field, Escape leaves a
        // layer, the arrows move a caret when one exists - and that logic lives
        // in the cases below and has to keep running. So only a key the user has
        // actually MOVED lands here; a key still sitting on its default falls
        // through to the case that has always handled it.
        if (e.Key is not (Key.Up or Key.Down or Key.Left or Key.Right
                          or Key.Enter or Key.Space or Key.Escape)
            && ActionForKey(e.Key) is { } mapped)
        {
            InvokeAction(mapped);
            e.Handled = true;
            return;
        }

        switch (e.Key)
        {
            case Key.Up: Move(Pad.Up); break;
            case Key.Down: Move(Pad.Down); break;
            // Keyboard arrows are VISUAL; Move() speaks layout space, which is
            // mirrored under RTL — so left/right are swapped here on purpose.
            // ⚠ While the search field holds focus, left/right belong to the
            // CARET. Stealing them for navigation makes the one screen in the
            // shell that accepts typing impossible to edit.
            case Key.Left:
                if (IsTextEntry()) return;
                // A focused volume row OWNS left/right (claimed inside Move, so
                // the controller gets the same behaviour).
                Move(Pad.Left); break;
            case Key.Right:
                if (IsTextEntry()) return;
                Move(Pad.Right); break;
            case Key.Enter or Key.Space:
                if (IsTextEntry())
                {
                    if (e.Key == Key.Space) return;      // a space is a character
                    // 🔴 ONLY THE SEARCH FIELD MEANS "open the top hit". Any other
                    // field (naming a collection) owns its own Enter, so this must
                    // stand aside instead of firing the first button on the card -
                    // which in a name prompt is CANCEL, silently discarding the name.
                    if (_layer != "search") return;
                    ActivateFirstResult();               // Enter opens the top hit
                    break;
                }
                ActivateFocused(); break;
            // ⚠ Backspace is BOUND TO "back" on a controller shell - which in a
            // text field means you cannot fix a typo, the search just closes. Only
            // Escape leaves while the field has focus.
            case Key.Back:
                if (IsTextEntry()) return;
                Back(); break;
            case Key.Escape: Back(); break;
            case Key.F5: _ = ReloadLibraryAsync(); break;
            case Key.F12: TakeScreenshot(); break;

            // 🔴 THE FOOTER PROMISED TWO BINDINGS THE KEYBOARD DID NOT HAVE.
            // The legend reads "Y תפריט מהיר" and the blade's reads
            // "X צילום מסך", but the only route to either was a physical pad -
            // so on a keyboard the shell advertised controls that did nothing.
            // The letters mirror the pad face buttons deliberately: the legend
            // is the documentation, and it has to be true on both inputs.
            case Key.Y: if (_layer == "view") OpenSearch(); break;
            // 🔴 THE BUTTON MAP FOLLOWS WINHANCED'S OWN FOOTER LEGEND, which the
            // planning report transcribes verbatim: "Y -> Search". So Y searches
            // here too, and the quick menu takes X - their remaining face button
            // is labelled "Close", and closing is exactly what this shell must NOT
            // put on a face button (one deliberate way out, from Settings only).
            // The screenshot lost its face button and kept the quick-menu row + F12;
            // it was never worth a dedicated button on every screen.
            case Key.X: if (_layer == "view") OpenQuickMenu(); break;
            case Key.Tab:
                if (_layer == "view") CycleTab(Keyboard.Modifiers == ModifierKeys.Shift ? -1 : 1);
                break;
            // The library's category row was advertised as LT/RT and bound to
            // NOTHING on a keyboard - the strip printed two trigger names at a
            // user who had no triggers. PageUp/PageDown because they are the one
            // pair that means "previous/next group" on every keyboard layout;
            // a letter key would move under a Hebrew layout.
            case Key.PageUp:
                if (_layer == "view" && _tab == "library") CycleFilter(-1);
                break;
            case Key.PageDown:
                if (_layer == "view" && _tab == "library") CycleFilter(+1);
                break;
            default: return;
        }
        e.Handled = true;
    }
}
