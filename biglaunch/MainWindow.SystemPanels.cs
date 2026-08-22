using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using BigLaunch.Interop;
using BigLaunch.Services;

namespace BigLaunch;

/// <summary>
/// The three system panels the header pill opens: Volume, Network and Bluetooth.
///
/// 🔴🔴 WHY THESE ARE BUILT IN AND NOT A HAND-OFF TO WINDOWS. An earlier pass put
/// the network and Bluetooth STATE in Settings and sent the user to
/// ms-settings: to act on it. That is wrong for the one situation this shell
/// exists for: a full-screen console on a TV, a controller in hand, and a pad
/// that will not connect or a download that will not start. Opening a Windows
/// panel there drops the user onto a desktop they cannot drive from the couch —
/// the console loses focus, the mouse is across the room, and the thing they
/// came to fix is now two context switches away. Winhanced puts a real panel
/// behind each of these icons for exactly this reason, and the report lists
/// them as must-haves.
///
/// Everything here is Win32/COM against the machine's own stack (see
/// Interop/AudioMixer, Interop/Wifi, Interop/BluetoothDevices). Nothing is
/// copied from Winhanced: the panels are re-implemented from their observable
/// layout in our own controls, with our own tokens and in Hebrew.
///
/// The ONE thing that stays a hand-off is turning a Bluetooth RADIO on, which
/// Win32 genuinely cannot do (it needs the WinRT Radio API, which would drag a
/// ~20MB projection into a 2MB single-file exe). That row says so instead of
/// pretending, and it is the only one.
/// </summary>
public partial class MainWindow
{
    // Which panel is open, so a refresh after an action re-opens the right one.
    private string? _sysPanel;
    // Focus index inside the open panel — a list you just acted on must not
    // throw the cursor back to the top on every refresh.
    private int _sysFocus;

    // Rows that own Left/Right (the sliders). Rebuilt with the panel.
    private readonly Dictionary<FrameworkElement, Action<int>> _stepRows = new();

    // Discovery state. Both scans BLOCK, so they run on a worker and the panel
    // re-renders when they land.
    private bool _btScanning;
    private List<BtDevice> _btFound = new();
    private bool _netScanning;

    // ------------------------------------------------------------------ shell

    /// <summary>
    /// The card every system panel is drawn in: a title row, a scrollable body,
    /// and the same solid-over-scrim treatment every other modal here uses.
    ///
    /// A modal is a SOLID layer over a dim scrim — never glass on glass, or it
    /// is unreadable over box art.
    /// </summary>
    private (Border card, StackPanel body) SystemCard(string title, string glyph)
    {
        // 🔴🔴 THE FOCUS MAP IS CLEARED **HERE**, BEFORE THE PANEL IS BUILT.
        //
        // It used to be cleared in ShowSystemPanel, which every panel calls at
        // the END - after it has already registered every one of its rows with
        // Nav(). So the map was wiped a moment after it was filled, _nav was
        // empty, and Move() returned on its first line: the volume, network and
        // Bluetooth panels could not be driven by the keyboard or the pad AT
        // ALL. A mouse still worked, which is exactly why it survived - a click
        // needs no focus map, and every check of these panels had been a click.
        //
        // The symptom that exposed it was not "the arrows do nothing", it was
        // "the panel will not scroll to its own last row": the search row sits
        // below four paired devices, and with no focus there was nothing for the
        // scroller to follow. Every panel starts by calling this method, so this
        // is the one place that is guaranteed to run before the rows exist.
        ResetNav();
        _navViewStart = 0;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(560),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var root = new StackPanel();

        // ⚠ COLUMN 0 IS THE VISUAL RIGHT under this window's RTL flow, so the
        // back affordance takes it — in Hebrew "back" is where the reading
        // starts. The title is centred between the two marks and the panel's own
        // glyph takes the far column: the reference's balance, mirrored to this
        // window's direction rather than copied as a pixel order.
        var head = new Grid { Margin = new Thickness(0, 0, 0, 16) };
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var back = new Button
        {
            Style = (Style)FindResource("GhostIcon"),
            Content = new TextBlock
            {
                Text = GlyphBack,
                FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
                FontSize = 18,
            },
            VerticalAlignment = VerticalAlignment.Center,
        };
        back.Click += (_, _) => { Sfx.Play(Sound.Back); _dialogBack?.Invoke(); };
        // Column 0 is the visual RIGHT here, which is where a Hebrew reader
        // starts and therefore where "back" belongs. The reference image puts
        // its arrow on the left because the reference is an English, LTR app -
        // copying that pixel position would put our back mark at the END of the
        // line instead of the start.
        Grid.SetColumn(back, 0);
        head.Children.Add(back);

        var t = Text(title, "H2");
        t.VerticalAlignment = VerticalAlignment.Center;
        t.HorizontalAlignment = HorizontalAlignment.Center;
        Grid.SetColumn(t, 1);
        head.Children.Add(t);

        var mark = new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 22,
            Foreground = (Brush)FindResource("FgSecondary"),
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 6, 0),
        };
        Grid.SetColumn(mark, 2);
        head.Children.Add(mark);

        root.Children.Add(head);

        var body = new StackPanel();
        // 🔴 A PANEL THAT LISTS DEVICES HAS NO FIXED HEIGHT. Twelve networks or
        // one — the card must not grow past the screen, so the body scrolls and
        // the card does not. Without the cap a long list pushed the card off the
        // top and bottom of a 1080p screen with no way to reach either end.
        var sv = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Hidden,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Focusable = false,
            MaxHeight = 620,
            Content = body,
        };
        SmoothScroll.AttachWheel(sv);
        SmoothScroll.AttachEdgeFade(sv);
        // The panel scrolls, so it has to follow the focus - see AttachFollowFocus.
        SmoothScroll.AttachFollowFocus(sv, body, _settings.AnimationsEnabled);
        root.Children.Add(sv);

        card.Child = root;
        return (card, body);
    }

    /// <summary>Stand a system panel up on the dialog layer.</summary>
    private void ShowSystemPanel(string key, Border card, Action back)
    {
        // Was this panel already on screen? Every refresh rebuilds the card, and
        // a rebuild must not be allowed to look like a new arrival.
        bool reopened = _sysAnchorFor == key;
        _sysPanel = key;
        _layer = "dialog";
        _dialogBack = () =>
        {
            _sysPanel = null;
            _stepRows.Clear();
            _sysAnchor = null;      // the next open measures where it belongs again
            _sysAnchorFor = null;
            CloseDialog();
        };
        // NOT ResetNav() - see SystemCard. The rows were registered while the
        // panel was being built, and clearing the map here is what emptied it.
        DialogHost.Children.Clear();

        // 🔴 A STATUS PANEL IS NOT A MODAL, SO IT MUST NOT BLACK THE SCREEN OUT.
        // Volume, network and Bluetooth are glances: you open one, read or nudge
        // a value, and leave. Dimming the whole shell for that says "everything
        // stops now" about a thing that changes nothing you were looking at -
        // and it hides the very screen whose volume you are setting. A real
        // modal (a confirmation, a picker) keeps its scrim; these three become
        // a glass card that grows FROM the chip that opened them, over an
        // untouched screen, and the shadow is what separates it instead.
        DialogHost.Background = System.Windows.Media.Brushes.Transparent;
        AnchorToChip(card, key);
        DialogHost.Visibility = Visibility.Visible;
        DialogHost.Children.Add(card);
        SetHints(("B", "סגירה"), ("A", "בחירה"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => FocusIndex(_sysFocus));

        // 🔴 A REFRESH IS NOT AN ARRIVAL. Every value change rebuilds this card,
        // and replaying the entrance animation on each one made the panel pulse
        // and shift under the user's own thumb - hold the volume key down and it
        // shrank, faded and re-grew on every step. It animates when it ARRIVES
        // and never again while it is up.
        if (!reopened) Animate(card);
    }

    /// <summary>
    /// Park a panel under the header chip that raised it, in LAYOUT space.
    ///
    /// Both the transform and Margin are read in the same (mirrored) coordinate
    /// space, so this needs no RTL special-case - the one thing it must do is
    /// CLAMP, because a chip near the edge would otherwise push a 560-wide card
    /// half off the screen.
    /// </summary>
    private Thickness? _sysAnchor;
    private string? _sysAnchorFor;

    private void AnchorToChip(Border card, string key)
    {
        card.HorizontalAlignment = HorizontalAlignment.Left;
        card.VerticalAlignment = VerticalAlignment.Top;
        card.Effect = (Effect)FindResource("ShadowPanel");
        // The fill, the edge and the shadow all come from GlassPanelCard now, and
        // nothing here overrides them: this panel is made of the same material as
        // every other floating surface, and what keeps a device list readable
        // over box art is Frost() blurring the shell behind it, not a heavier
        // tint on this one card.

        // 🔴🔴 THE POSITION IS DECIDED ONCE, WHEN THE PANEL OPENS.
        //
        // This used to re-measure the header chip on every refresh - and the
        // header REDRAWS ITSELF every two seconds for the live CPU/RAM readout,
        // which replaces the chip element. The panel then held a chip that was
        // no longer in the tree, `IsVisible` came back false, and the catch-all
        // fallback parked it in the opposite corner: open the volume panel on
        // the left, touch nothing, and two seconds later it had jumped across
        // the screen. Every later refresh could flip it again.
        //
        // A floating panel that moves while you are using it is the single most
        // unstable thing a shell can do, so the answer is not a better fallback:
        // it is that the position is computed at OPEN and then frozen for as
        // long as that panel is up. Closing it clears the anchor (see the back
        // action in ShowSystemPanel), so the next open measures afresh.
        if (_sysAnchorFor == key && _sysAnchor is { } kept)
        {
            card.Margin = kept;
            return;
        }

        double w = double.IsNaN(card.Width) ? 560 : card.Width;
        double left = 24, top = 84;
        try
        {
            if (_lastChip is { IsVisible: true } chip)
            {
                var p = chip.TransformToAncestor(Root).Transform(new Point(0, 0));
                left = p.X;
                top = p.Y + chip.ActualHeight + 10;
            }
        }
        catch { /* an anchor that is gone falls back to the corner, once */ }

        double maxLeft = Math.Max(24, Root.ActualWidth - w - 24);
        card.Margin = new Thickness(Math.Clamp(left, 24, maxLeft), Math.Max(24, top), 0, 0);
        _sysAnchor = card.Margin;
        _sysAnchorFor = key;
    }

    /// <summary>
    /// Re-draw the open panel in place, keeping the cursor where it was.
    ///
    /// 🔴 A LIST YOU JUST ACTED ON MUST NOT SNAP BACK TO THE TOP. Pairing the
    /// fourth device and finding the ring on the first row again reads as "the
    /// press did nothing", which is the exact failure this shell keeps having to
    /// design out.
    /// </summary>
    private void RefreshSystemPanel()
    {
        if (_sysPanel is null) return;
        if (Keyboard.FocusedElement is FrameworkElement f)
        {
            int i = _nav.IndexOf(f);
            if (i >= 0) _sysFocus = i;
        }
        switch (_sysPanel)
        {
            case "volume": OpenVolumePanel(keepFocus: true); break;
            case "network": OpenNetworkPanel(keepFocus: true); break;
            case "bluetooth": OpenBluetoothPanel(keepFocus: true); break;
        }
    }

    // ------------------------------------------------------------------ slider

    /// <summary>
    /// A value row: a title, a filled track and a percentage, on one focusable
    /// row. Left/Right step it, A runs <paramref name="press"/>, and a mouse can
    /// click anywhere on the track.
    ///
    /// It is a Button and not a WPF Slider on purpose — every other row on this
    /// screen is a Button, so the focus ring, the hit target and the D-pad
    /// geometry all match. A Slider would take focus with different visuals and
    /// swallow Left/Right before Move() ever saw them.
    /// </summary>
    private Button SliderRow(string glyph, string title, int value, Action<int> set,
                             Action? press = null, ImageSource? icon = null)
    {
        int v = Math.Clamp(value, 0, 100);   // mutable: the step handler owns it

        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        // The program's OWN icon when we could get one, the glyph when we could
        // not. The two are the same size on purpose, so a list that mixes them
        // still lines up.
        FrameworkElement mark = icon is not null
            ? new Image
            {
                Source = icon,
                Width = 22,
                Height = 22,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(0, 0, 12, 0),
            }
            : new TextBlock
            {
                Text = glyph,
                FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
                FontSize = 18,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(0, 0, 14, 0),
            };
        if (mark is Image img) RenderOptions.SetBitmapScalingMode(img, BitmapScalingMode.HighQuality);

        // 🔴 MUTE LIVES ON THE SPEAKER, NOT ON THE WHOLE ROW. Clicking anywhere
        // in the row used to toggle it, so reaching for the track with a mouse
        // silenced the thing you were trying to set. The mark becomes its own
        // small button; the row's Click still mutes, which is what the pad's A
        // needs, and a pad has no way to click a track by accident.
        FrameworkElement lead = mark;
        if (press is not null)
        {
            var mb = new Button
            {
                Style = (Style)FindResource("GhostIcon"),
                Content = mark,
                Focusable = false,
                VerticalAlignment = VerticalAlignment.Center,
                ToolTip = null,
            };
            mark.Margin = new Thickness(0);
            mb.Click += (_, e) =>
            {
                Sfx.Play(Sound.Select);
                press();
                RefreshSystemPanel();
            };
            lead = mb;
        }
        Grid.SetColumn(lead, 0);
        grid.Children.Add(lead);

        var col = new StackPanel();
        if (!string.IsNullOrEmpty(title))
            col.Children.Add(Inherit(new TextBlock
            {
                Text = title,
                Style = (Style)FindResource("Body"),
                FontWeight = FontWeights.Medium,
                TextTrimming = TextTrimming.CharacterEllipsis,
            }));

        // One slider shape for the whole shell — track, fill, round knob and the
        // value bubble over it (MainWindow.Glass.cs). Building it here instead of
        // hand-rolling a second track is the only way the size sliders in
        // settings and the volume sliders here can stay the same object.
        GlassSlider? sl = null;
        TextBlock? pctRef = null;
        var slider = BuildSlider(scrub: frac =>
        {
            // Dragging writes straight through to the device and updates this
            // row only - the panel is not rebuilt (see the step handler below
            // for why that matters).
            int nv = (int)Math.Round(frac * 100);
            if (nv == v) return;
            set(nv);
            v = nv;
            sl!.Set(nv / 100.0, nv + "%");
            if (pctRef is not null) pctRef.Text = nv + "%";
        });
        sl = slider;
        slider.Set(v / 100.0, v + "%");
        var track = slider.Root;
        col.Children.Add(track);
        Grid.SetColumn(col, 1);
        grid.Children.Add(col);

        var pct = new TextBlock
        {
            Text = v + "%",
            Style = (Style)FindResource("Caption"),
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(16, 0, 0, 0),
            FlowDirection = FlowDirection.LeftToRight,
        };
        Inherit(pct);
        pctRef = pct;
        Grid.SetColumn(pct, 2);
        grid.Children.Add(pct);

        var b = new Button { Style = (Style)FindResource("ListRow"), Content = grid };
        BindBubble(slider, b);
        // Pressing the row toggles mute, which changes the glyph AND the title -
        // that is a structural change, so it still redraws the panel.
        b.Click += (_, _) => { Sfx.Play(Sound.Select); press?.Invoke(); RefreshSystemPanel(); };

        // 🔴🔴 A STEP UPDATES THIS ROW, IT DOES NOT REBUILD THE PANEL.
        //
        // Every arrow press used to call RefreshSystemPanel(), which threw the
        // whole card away and built a new one: the panel re-anchored, re-ran its
        // entrance animation and re-created every row, so holding the key down
        // made the window pulse and shift under the user's thumb. It also made
        // the slider's own motion impossible - a brand-new slider has no
        // previous value to animate FROM, so every step was an instant jump.
        //
        // Nothing structural changes when a level moves, so the row simply
        // writes its new value into the controls it already owns.
        _stepRows[b] = delta =>
        {
            int nv = Math.Clamp(v + delta, 0, 100);
            // Still play at the ends: the slider answers a dead press with its
            // rubber-band, and a silent key is what makes one feel dropped.
            set(nv);
            v = nv;
            slider.Set(nv / 100.0, nv + "%");
            pct.Text = nv + "%";
            Sfx.Play(Sound.Navigate);
        };
        return b;
    }

    /// <summary>
    /// Left/Right on a focused slider row. True when it consumed the key, so
    /// Move() stops before it walks the cursor off the row the user is holding.
    /// </summary>
    /// <summary>
    /// Left/right belongs to the focused row when that row is a slider.
    ///
    /// This used to return false unless a system panel was open, because the
    /// volume row was the only slider in the shell. The per-group size sliders
    /// are the second, and they live on an ordinary page - so the claim is now
    /// asked of whichever surface is actually in front: a panel owns it while
    /// one is open, the page owns it otherwise. Checking both lists blindly
    /// would let a panel's stale row answer for the page underneath it.
    /// </summary>
    private bool StepFocusedRow(int delta)
    {
        foreach (var (el, step) in (_sysPanel is not null ? _stepRows : _pageSteps))
            if (el.IsKeyboardFocusWithin) { step(delta); return true; }
        return false;
    }

    // ------------------------------------------------------------------ volume

    /// <summary>
    /// Volume: the system level, which output device it goes to, and a per-app
    /// mixer. All three are things a full-screen console user cannot otherwise
    /// reach — the Windows mixer is behind the game.
    /// </summary>
    private void OpenVolumePanel(bool keepFocus = false)
    {
        if (!keepFocus) _sysFocus = 0;
        _stepRows.Clear();
        var (card, sp) = SystemCard("עוצמת קול", GlyphSound);

        int master = Interop.Volume.Level();
        bool muted = Interop.Volume.Muted();

        if (master < 0)
        {
            sp.Children.Add(InfoRow(GlyphWarn, "אין התקן שמע פעיל",
                "Windows לא מדווח על התקן פלט זמין"));
        }
        else
        {
            // No title on the master row: the panel is already called "עוצמת קול",
            // and a row that repeats its own panel's name is the single most
            // common way a settings screen ends up looking crowded.
            sp.Children.Add(Nav(SliderRow(muted ? GlyphMute : GlyphSound,
                muted ? "מושתק" : "",
                muted ? 0 : master,
                p => Interop.Volume.Set(p),
                // 🔴 REDRAW THE HEADER NOW, NOT ON THE NEXT TICK. The chips are
                // rebuilt by a two-second timer, so muting left the old speaker
                // glyph on screen for up to two seconds - long enough to press
                // it again thinking the first press had missed.
                () => { Interop.Volume.ToggleMute(); BuildPillChips(); })));
            sp.Children.Add(Text("חצים ימינה/שמאלה לשינוי · A להשתקה",
                "Caption", margin: new Thickness(0, 2, 0, 0)));
        }

        // ---- output device
        //
        // 🔴 ONE ROW THAT OPENS A LIST, NOT THE LIST ITSELF. Every output device
        // laid out as its own row makes a machine with four of them (speakers,
        // headset, monitor, virtual cable) push the app mixer off the bottom of
        // the panel — and the mixer is what people actually come here for. The
        // current device is the only one worth permanent space; the rest are a
        // press away.
        var devices = AudioMixer.OutputDevices();
        sp.Children.Add(Divider());
        if (devices.Count == 0)
        {
            // 🔴 AN EMPTY SECTION MUST SAY IT IS EMPTY. Rendering nothing when a
            // list comes back empty makes a working panel look half-built, and
            // it hides the difference between "this machine has one output" and
            // "the enumeration failed" - which is exactly the ambiguity that
            // made this section read as missing rather than as broken.
            sp.Children.Add(InfoRow(GlyphWarn, "לא נמצאו התקני פלט",
                string.IsNullOrEmpty(AudioMixer.LastError)
                    ? "Windows לא החזיר רשימת התקנים"
                    : "Windows לא החזיר רשימת התקנים · " + AudioMixer.LastError));
        }
        else
        {
            var active = devices.FirstOrDefault(d => d.IsDefault) ?? devices[0];
            sp.Children.Add(Nav(RowButton(
                GlyphSound, "התקן הפלט", Ltr(active.Name),
                () =>
                {
                    if (devices.Count == 1) { ShowToast("יש רק התקן פלט אחד"); return; }
                    var opts = devices
                        .Select(d => (Key: d.Id, Label: Ltr(d.Name), Detail: d.IsDefault ? "בשימוש עכשיו" : ""))
                        .ToList();
                    Picker("התקן הפלט", "לאן הצליל יוצא", opts, active.Id,
                        id =>
                        {
                            var pickd = devices.First(d => d.Id == id);
                            if (!pickd.IsDefault)
                            {
                                if (AudioMixer.SetDefaultOutput(id)) ShowToast("הפלט הועבר אל " + pickd.Name);
                                else { Sfx.Play(Sound.Warning); ShowToast("לא ניתן להחליף התקן פלט במחשב הזה"); }
                            }
                            OpenVolumePanel();
                        },
                        back: () => OpenVolumePanel());
                },
                trailing: Chevron())));
        }

        // ---- per-app mixer
        // 🔴 SORTED, BECAUSE THE AUDIO STACK'S ORDER IS NOT STABLE. Windows hands
        // sessions back in whatever order it enumerated them, so two refreshes a
        // second apart could swap two rows - and the row the user was aiming at
        // moved out from under the cursor mid-press. Name order is arbitrary but
        // CONSTANT, which is the only property that matters here.
        var sessions = AudioMixer.Sessions()
            .OrderBy(x => x.Name, StringComparer.CurrentCultureIgnoreCase)
            .ToList();
        sp.Children.Add(Divider());
        sp.Children.Add(Text("עוצמה לכל אפליקציה", "H3", margin: new Thickness(0, 6, 0, 8)));
        if (sessions.Count == 0)
        {
            sp.Children.Add(InfoRow(GlyphInfo, "אין אפליקציה שמשמיעה עכשיו",
                "אפליקציה מופיעה כאן ברגע שהיא מנגנת משהו"));
        }
        else
        {
            foreach (var s in sessions)
            {
                var sess = s;
                sp.Children.Add(Nav(SliderRow(
                    sess.Muted ? GlyphMute : GlyphGame,
                    Ltr(sess.Name),
                    sess.Muted ? 0 : sess.Volume,
                    p => AudioMixer.SetSessionVolume(sess.Id, p),
                    () => AudioMixer.SetSessionMute(sess.Id, !sess.Muted),
                    // A muted row keeps the crossed-speaker glyph: the state is
                    // the thing worth showing there, not which app it is.
                    icon: sess.Muted ? null : AppIcons.ForProcess(sess.ProcessId))));
            }
        }

        ShowSystemPanel("volume", card, () => OpenVolumePanel());
    }

    /// <summary>The "there is more behind this row" mark. It points the way the
    /// panel would open in THIS window's direction, so it never argues with the
    /// layout the way a hard-coded ">" would.</summary>
    private UIElement Chevron() => new TextBlock
    {
        Text = GlyphBack,
        FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
        FontSize = 14,
        Foreground = (Brush)FindResource("FgDim"),
        VerticalAlignment = VerticalAlignment.Center,
    };

    private UIElement CheckMark() => new TextBlock
    {
        Text = GlyphCheck,
        FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
        FontSize = 16,
        Foreground = (Brush)FindResource("Accent"),
        VerticalAlignment = VerticalAlignment.Center,
    };

    // ----------------------------------------------------------------- network

    /// <summary>
    /// Network: the Wi-Fi radio, the wired link, and the networks in range with
    /// the one you are on marked. Joining a secured network opens a key field
    /// rather than sending the user to Windows.
    /// </summary>
    private void OpenNetworkPanel(bool keepFocus = false)
    {
        if (!keepFocus) _sysFocus = 0;
        _stepRows.Clear();
        bool wired = Wifi.EthernetConnected();
        var (card, sp) = SystemCard("רשת", wired ? GlyphEthernet : GlyphWifi);

        if (wired)
            sp.Children.Add(InfoRow(GlyphEthernet, "רשת קווית · מחובר",
                "חיבור קווי גובר על Wi-Fi כששניהם פעילים"));

        if (!Wifi.Available())
        {
            if (!wired)
                sp.Children.Add(InfoRow(GlyphWarn, "אין חיבור לרשת",
                    "בלי רשת אין הורדות, אין תרגומים ואין תמונות עטיפה"));
            sp.Children.Add(InfoRow(GlyphInfo, "אין מתאם Wi-Fi במחשב הזה",
                "הפאנל מציג רק את החיבור הקווי"));
            ShowSystemPanel("network", card, () => OpenNetworkPanel());
            return;
        }

        bool radio = Wifi.RadioOn();
        sp.Children.Add(Nav(Toggle("Wi-Fi",
            radio ? "מופעל" : "כבוי · הדלקה כדי לראות רשתות",
            radio,
            v =>
            {
                if (!Wifi.SetRadio(v))
                {
                    Sfx.Play(Sound.Warning);
                    // The HARDWARE kill switch is not software-settable, and a
                    // toggle that silently springs back is the worst of both.
                    ShowToast(v
                        ? "לא ניתן להדליק · ייתכן שמתג החומרה מכובה"
                        : "לא ניתן לכבות את המתאם");
                }
                Dispatcher.BeginInvoke(DispatcherPriority.Background, () => RefreshSystemPanel());
            })));

        if (!radio)
        {
            ShowSystemPanel("network", card, () => OpenNetworkPanel());
            return;
        }

        sp.Children.Add(Divider());
        sp.Children.Add(Text("רשתות זמינות", "H3", margin: new Thickness(0, 6, 0, 8)));

        var nets = Wifi.Networks();
        string? here = Wifi.ConnectedSsid();

        if (_netScanning)
            sp.Children.Add(InfoRow(GlyphSync, "סורק...", "מחפש רשתות בסביבה"));
        else if (nets.Count == 0)
            sp.Children.Add(InfoRow(GlyphInfo, "לא נמצאו רשתות", "לחצו על רענון"));

        foreach (var n in nets)
        {
            var net = n;
            bool on = here is not null && string.Equals(here, net.Ssid, StringComparison.Ordinal);
            string detail = net.Security + " · " + Ltr(net.SignalPercent + "%")
                          + (on ? " · מחובר" : net.HasProfile ? " · נשמר" : "");
            sp.Children.Add(Nav(RowButton(
                GlyphWifi, Ltr(net.Ssid), detail,
                () => JoinNetwork(net, on),
                trailing: on ? CheckMark() : null)));
        }

        sp.Children.Add(Divider());
        sp.Children.Add(Nav(RowButton(GlyphRefresh, "רענון רשתות",
            "סריקה חוזרת של הסביבה", ScanNetworks)));

        ShowSystemPanel("network", card, () => OpenNetworkPanel());
    }

    /// <summary>Signal strength as a glyph, so the list is readable at 10ft
    /// without reading a number.</summary>
    private static string SignalGlyph(int pct) => pct >= 75 ? ""   // full
                                                : pct >= 50 ? ""   // 3 bars
                                                : pct >= 25 ? ""   // 2 bars
                                                            : "";  // 1 bar

    /// <summary>
    /// A scan takes a couple of seconds inside the driver, so it runs on a
    /// worker and the panel shows a scanning row meanwhile. Blocking the UI
    /// thread here would freeze the whole console.
    /// </summary>
    private void ScanNetworks()
    {
        if (_netScanning) return;
        _netScanning = true;
        RefreshSystemPanel();
        Task.Run(() =>
        {
            try { Wifi.Scan(); System.Threading.Thread.Sleep(3200); }
            catch { }
            Dispatcher.BeginInvoke(() =>
            {
                _netScanning = false;
                if (_sysPanel == "network") RefreshSystemPanel();
            });
        });
    }

    private void JoinNetwork(WifiNetwork net, bool connected)
    {
        if (connected)
        {
            Confirm("להתנתק מ-" + net.Ssid + "?",
                "המחשב יישאר ללא חיבור אלחוטי.",
                "התנתק", false,
                () => { Wifi.Disconnect(); OpenNetworkPanel(); },
                back: () => OpenNetworkPanel());
            return;
        }

        // A saved profile already holds the key; asking for it again would be a
        // password prompt for something the machine already knows.
        if (net.HasProfile || net.Security == "Open") { StartJoin(net, null); return; }
        AskWifiKey(net);
    }

    private void StartJoin(WifiNetwork net, string? key)
    {
        if (!Wifi.Connect(net.Ssid, key))
        {
            Sfx.Play(Sound.Warning);
            ShowToast("החיבור ל-" + net.Ssid + " נכשל");
            OpenNetworkPanel();
            return;
        }
        ShowToast("מתחבר ל-" + net.Ssid + "...");
        OpenNetworkPanel();
        // WlanConnect is asynchronous: it returns the moment the request is
        // accepted, long before the link is up. Re-read the state a few seconds
        // later so the list shows the truth instead of the request.
        _ = Task.Run(async () =>
        {
            await Task.Delay(4000);
            _ = Dispatcher.BeginInvoke(() => { if (_sysPanel == "network") RefreshSystemPanel(); });
        });
    }

    /// <summary>
    /// The network key prompt.
    ///
    /// ⚠ A PasswordBox is NOT a TextBox, and the key handler's text-entry guards
    /// test for TextBox — see IsTextEntry() in MainWindow.xaml.cs, which this
    /// field is the reason for. Without it Backspace closes the panel instead of
    /// deleting a character.
    /// </summary>
    private void AskWifiKey(WifiNetwork net)
    {
        Sfx.Play(Sound.Select);
        _sysPanel = null;
        _layer = "dialog";
        _dialogBack = () => { DismissDialog(); _layer = "view"; OpenNetworkPanel(); };
        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var card = new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            Width = CardWidth(480),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
        };

        var sp = new StackPanel();
        sp.Children.Add(Text("התחברות ל-" + net.Ssid, "H2", margin: new Thickness(0, 0, 0, 4)));
        sp.Children.Add(Text(net.Security + " · הזינו את מפתח הרשת",
            "Caption", margin: new Thickness(0, 0, 0, 14)));

        var pw = new PasswordBox
        {
            FontSize = 20,
            Padding = new Thickness(14, 10, 14, 10),
            Margin = new Thickness(0, 0, 0, 16),
            FlowDirection = FlowDirection.LeftToRight,
            Background = new SolidColorBrush(Color.FromArgb(0x30, 0xFF, 0xFF, 0xFF)),
            Foreground = (Brush)FindResource("FgPrimary"),
            BorderThickness = new Thickness(0),
        };
        sp.Children.Add(Nav(pw));

        var row = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Left };
        var cancel = new Button
        {
            Style = (Style)FindResource("ListRow"),
            Content = new TextBlock { Text = "ביטול", VerticalAlignment = VerticalAlignment.Center },
        };
        cancel.Click += (_, _) => { Sfx.Play(Sound.Back); DismissDialog(); _layer = "view"; OpenNetworkPanel(); };
        row.Children.Add(Nav(cancel));

        var go = new Button
        {
            Style = (Style)FindResource("ListRow"),
            Content = new TextBlock { Text = "התחבר", VerticalAlignment = VerticalAlignment.Center },
            Margin = new Thickness(12, 0, 0, 0),
        };
        go.Click += (_, _) =>
        {
            string key = pw.Password;
            DismissDialog();
            _layer = "view";
            StartJoin(net, string.IsNullOrEmpty(key) ? null : key);
        };
        row.Children.Add(Nav(go));
        sp.Children.Add(row);

        card.Child = sp;
        DialogHost.Children.Add(card);
        SetHints(("B", "ביטול"), ("A", "אישור"));
        Dispatcher.BeginInvoke(DispatcherPriority.Loaded, () => pw.Focus());
        Animate(card);
    }

    // --------------------------------------------------------------- bluetooth

    /// <summary>
    /// Bluetooth: what is paired, what is in range, and pairing/removing —
    /// which is the whole reason a couch user opens this at all (a pad that
    /// will not connect).
    /// </summary>
    private void OpenBluetoothPanel(bool keepFocus = false)
    {
        if (!keepFocus) _sysFocus = 0;
        _stepRows.Clear();
        var (card, sp) = SystemCard("Bluetooth", GlyphBluetooth);

        if (!BluetoothDevices.RadioPresent())
        {
            sp.Children.Add(InfoRow(GlyphWarn, "אין Bluetooth במחשב הזה",
                "לא נמצא מתאם Bluetooth"));
            ShowSystemPanel("bluetooth", card, () => OpenBluetoothPanel());
            return;
        }

        if (SystemStatus.BluetoothOn())
        {
            // The state card the reference opens with. It is NOT a switch: see
            // the note below — nothing in Win32 turns a Bluetooth radio on, so a
            // switch here would be a control that lies. It states the state, and
            // pressing it takes you to the one place that can change it.
            sp.Children.Add(Nav(StateCard(GlyphBluetooth, "Bluetooth", "מופעל", true,
                "כיבוי והדלקה של המתאם נעשים ב-Windows",
                () => OpenSystemPanel("ms-settings:bluetooth", "הגדרות Bluetooth"))));
        }
        else
        {
            // 🔴 THE ONE HONEST HAND-OFF IN THIS FILE. Turning a Bluetooth radio
            // ON has no Win32 API — it needs the WinRT Radio class, which would
            // pull a ~20MB projection into a 2MB single-file exe for one switch.
            // So this row says what it is instead of being a toggle that does
            // nothing.
            sp.Children.Add(Nav(RowButton(GlyphBluetooth, "Bluetooth כבוי",
                "הדלקת המתאם נעשית ב-Windows · לחצו לפתיחת ההגדרות",
                () => OpenSystemPanel("ms-settings:bluetooth", "הגדרות Bluetooth"))));
            ShowSystemPanel("bluetooth", card, () => OpenBluetoothPanel());
            return;
        }

        var paired = BluetoothDevices.Paired();
        sp.Children.Add(Text("מכשירים מותאמים", "H3", margin: new Thickness(0, 12, 0, 8)));
        if (paired.Count == 0)
            sp.Children.Add(InfoRow(GlyphInfo, "אין מכשירים מותאמים", ""));
        foreach (var d in paired)
        {
            var dev = d;
            sp.Children.Add(Nav(RowButton(GlyphBluetooth, Ltr(dev.Name),
                (dev.Connected ? "מחובר" : "מותאם · לא מחובר") + " · " + BluetoothDevices.AddressText(dev.Address),
                () => Confirm("להסיר את " + dev.Name + "?",
                    "ההתאמה תימחק ויהיה צריך להתאים מחדש כדי להשתמש בו.",
                    "הסרה", true,
                    () =>
                    {
                        if (BluetoothDevices.Remove(dev.Address))
                            ShowToast(dev.Name + " הוסר");
                        else { Sfx.Play(Sound.Warning); ShowToast("לא ניתן להסיר את המכשיר"); }
                        OpenBluetoothPanel();
                    },
                    back: () => OpenBluetoothPanel()),
                trailing: dev.Connected ? CheckMark() : null)));
        }

        sp.Children.Add(Divider());
        sp.Children.Add(Text("מכשירים בסביבה", "H3", margin: new Thickness(0, 6, 0, 8)));

        if (_btScanning)
            sp.Children.Add(InfoRow(GlyphSync, "מחפש מכשירים...",
                "העבירו את השלט למצב התאמה עכשיו"));
        else
        {
            foreach (var d in _btFound)
            {
                var dev = d;
                sp.Children.Add(Nav(RowButton(GlyphAdd, Ltr(dev.Name),
                    "לחצו כדי להתאים · " + BluetoothDevices.AddressText(dev.Address),
                    () => PairDevice(dev))));
            }
            if (_btFound.Count == 0)
                sp.Children.Add(InfoRow(GlyphInfo, "לא נמצאו מכשירים חדשים",
                    "לחצו על חיפוש כשהמכשיר במצב התאמה"));
        }

        // While a scan is running the button becomes its own OFF switch, the way
        // the reference does it. An inquiry cannot actually be aborted inside the
        // driver, so "stop" stops the SEARCH, not the radio: the panel leaves the
        // scanning state at once and the late result is discarded (see the
        // generation counter in ScanBluetooth) - which is exactly what the user
        // means by stop, and is honest about what the button controls.
        sp.Children.Add(Nav(RowButton(
            _btScanning ? GlyphStop : GlyphSearch,
            _btScanning ? "עצירת החיפוש" : "חיפוש מכשירים",
            _btScanning ? "מחפש מכשירים בסביבה" : "לוקח כמה שניות",
            () => { if (_btScanning) StopBluetoothScan(); else ScanBluetooth(); })));

        ShowSystemPanel("bluetooth", card, () => OpenBluetoothPanel());
    }

    /// <summary>An inquiry BLOCKS for seconds — it must never run on the UI
    /// thread, or the whole console freezes mid-scan.</summary>
    private int _btScanGen;

    private void ScanBluetooth()
    {
        if (_btScanning) return;
        _btScanning = true;
        int gen = ++_btScanGen;
        RefreshSystemPanel();
        Task.Run(() =>
        {
            List<BtDevice> found;
            try { found = BluetoothDevices.Discover(6); }
            catch { found = new List<BtDevice>(); }
            Dispatcher.BeginInvoke(() =>
            {
                // 🔴 A LATE RESULT FROM A CANCELLED SCAN MUST NOT LAND. Stopping
                // bumps the generation, so the inquiry that is still finishing
                // inside the driver comes back to a panel that has moved on and
                // drops its list instead of re-filling a section the user just
                // closed.
                if (gen != _btScanGen) return;
                _btFound = found;
                _btScanning = false;
                if (_sysPanel == "bluetooth") RefreshSystemPanel();
            });
        });
    }

    private void StopBluetoothScan()
    {
        _btScanGen++;
        _btScanning = false;
        RefreshSystemPanel();
    }

    private void PairDevice(BtDevice dev)
    {
        ShowToast("מתאים את " + dev.Name + "...");
        Task.Run(() =>
        {
            bool ok;
            try { ok = BluetoothDevices.Pair(dev.Address); }
            catch { ok = false; }
            Dispatcher.BeginInvoke(() =>
            {
                if (ok)
                {
                    ShowToast(dev.Name + " הותאם");
                    _btFound = _btFound.Where(x => x.Address != dev.Address).ToList();
                    // A freshly paired pad should light the prompts up without
                    // the user having to go and press "re-detect".
                    RedetectPadQuiet();
                }
                else
                {
                    Sfx.Play(Sound.Warning);
                    ShowToast("ההתאמה נכשלה · ודאו שהמכשיר במצב התאמה");
                }
                if (_sysPanel == "bluetooth") RefreshSystemPanel();
            });
        });
    }

    /// <summary>
    /// Re-read which pad is attached WITHOUT announcing it.
    ///
    /// RedetectPad() exists for the settings button and always toasts, which is
    /// right there and wrong here: the pairing flow has already said
    /// "&lt;device&gt; הותאם", and a second toast on top of it is the app talking
    /// over itself.
    /// </summary>
    private void RedetectPadQuiet()
    {
        _padHardware = null;
        var found = PadIdentity.Detect();
        _padHardware = found;
        _padKind = PadOverride ?? found ?? PadKind.Keyboard;
        if (_lastHints is { } h) SetHints(h);
    }
}
