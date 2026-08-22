using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using BigLaunch.Interop;
using BigLaunch.Services;

namespace BigLaunch;

/// <summary>
/// Every command this shell has, named once.
///
/// 🔴 THE ACTIONS ARE THE FIXED POINT, NOT THE BUTTONS. The input handlers used
/// to switch on the hardware — `case Pad.Y: OpenSearch()` — which means the pad
/// layout WAS the source code and there was nothing a user could rebind. Naming
/// the actions turns the mapping into data: the handlers now ask "what does this
/// button mean" and get an answer that a person can change.
///
/// The four directions are deliberately NOT in here. They are not commands, they
/// are movement, and a shell whose user can unbind "down" is a shell that can be
/// made impossible to leave with the device you rebound it from.
/// </summary>
public enum ShellAction
{
    Select, Back, Search, QuickMenu, PrevTab, NextTab, Settings, FilterPrev, FilterNext,
}

public partial class MainWindow
{
    // ---------------------------------------------------------------- defaults

    private static readonly (ShellAction Act, string Name, string What)[] Actions =
    {
        (ShellAction.Select,     "בחירה",        "מפעיל את מה שמסומן"),
        (ShellAction.Back,       "חזרה",         "סוגר חלון או חוזר מסך אחורה"),
        (ShellAction.Search,     "חיפוש",        "פותח את תיבת החיפוש"),
        (ShellAction.QuickMenu,  "תפריט מהיר",   "פותח את התפריט הצף"),
        // 🔴 THE NAMES SAY WHICH WAY THE EYE MOVES, NOT WHICH WAY THE INDEX DOES.
        // "Prev" walks the Tabs array backwards, and because the strip is laid
        // out right-to-left that is a step to the RIGHT on screen. Naming these
        // after the array is how a prompt ends up promising the opposite of what
        // the key does.
        (ShellAction.PrevTab,    "מסך ימינה",     "עובר למסך שמימין בשורה"),
        (ShellAction.NextTab,    "מסך שמאלה",    "עובר למסך שמשמאל בשורה"),
        (ShellAction.Settings,   "הגדרות",       "קופץ ישר למסך ההגדרות"),
        (ShellAction.FilterPrev, "סינון קודם",   "בספרייה - מחליף את הסינון אחורה"),
        (ShellAction.FilterNext, "סינון הבא",    "בספרייה - מחליף את הסינון קדימה"),
    };

    private static readonly Dictionary<ShellAction, Pad> PadDefaults = new()
    {
        [ShellAction.Select] = Pad.A,
        [ShellAction.Back] = Pad.B,
        [ShellAction.Search] = Pad.Y,
        [ShellAction.QuickMenu] = Pad.X,
        [ShellAction.PrevTab] = Pad.LB,
        [ShellAction.NextTab] = Pad.RB,
        [ShellAction.Settings] = Pad.Start,
        [ShellAction.FilterPrev] = Pad.LT,
        [ShellAction.FilterNext] = Pad.RT,
    };

    private static readonly Dictionary<ShellAction, Key> KeyDefaults = new()
    {
        [ShellAction.Select] = Key.Enter,
        [ShellAction.Back] = Key.Escape,
        [ShellAction.Search] = Key.Y,
        [ShellAction.QuickMenu] = Key.X,
        [ShellAction.PrevTab] = Key.E,      // E moves right along the strip
        [ShellAction.NextTab] = Key.Q,      // Q moves left
        [ShellAction.Settings] = Key.F1,
        [ShellAction.FilterPrev] = Key.OemComma,
        [ShellAction.FilterNext] = Key.OemPeriod,
    };

    // ------------------------------------------------------------- resolution

    private Pad PadFor(ShellAction a) =>
        _settings.PadMap.TryGetValue(a.ToString(), out var s) && Enum.TryParse<Pad>(s, out var p)
            ? p : PadDefaults[a];

    private Key KeyFor(ShellAction a) =>
        _settings.KeyMap.TryGetValue(a.ToString(), out var s) && Enum.TryParse<Key>(s, out var k)
            ? k : KeyDefaults[a];

    /// <summary>
    /// The action a FOOTER TOKEN stands for.
    ///
    /// THE LEGEND WAS PRINTING THE FACTORY LAYOUT, NOT THE USER'S. Every
    /// SetHints call names a literal button - ("A", "בחירה") - which was true
    /// only until the mapping screen let someone move "בחירה" onto Y. From then
    /// on the whole shell kept promising A while A did nothing, and the one
    /// screen built to let a user fix their controller was the screen that made
    /// every other screen lie. The tokens are read as the DEFAULT binding they
    /// were written against, resolved back to an action, and re-drawn as
    /// whatever button currently carries it.
    /// </summary>
    private static ShellAction? ActionForToken(string token) => token switch
    {
        "A" => ShellAction.Select,
        "B" => ShellAction.Back,
        "X" => ShellAction.QuickMenu,
        "Y" => ShellAction.Search,
        "LB" => ShellAction.PrevTab,
        "RB" => ShellAction.NextTab,
        "LT" => ShellAction.FilterPrev,
        "RT" => ShellAction.FilterNext,
        "Start" => ShellAction.Settings,
        _ => null,
    };

    /// <summary>The token to actually draw for a legend entry on THIS install.</summary>
    private string LiveToken(string token)
    {
        // A pair is two prompts sharing one label ("החלפת מסך"); each half
        // follows its own binding, so an asymmetric remap still reads right.
        if (token.Contains('/') && token.Split('/') is { Length: 2 } halves
            && ActionForToken(halves[0]) is not null)
            return LiveToken(halves[0]) + "/" + LiveToken(halves[1]);

        if (ActionForToken(token) is not { } act) return token;

        // The keyboard keeps its own token space (GlyphFor turns "A" into
        // "Enter"), so an unbound-on-pad action still has a printable prompt.
        if (_padKind is PadKind.Keyboard) return token;

        var p = PadFor(act);
        return p switch
        {
            Pad.A => "A", Pad.B => "B", Pad.X => "X", Pad.Y => "Y",
            Pad.LB => "LB", Pad.RB => "RB", Pad.LT => "LT", Pad.RT => "RT",
            Pad.Start => "Start", Pad.Back => "Back",
            // Unassigned: say so rather than name a button that does nothing.
            _ => "—",
        };
    }

    /// <summary>What this pad button means, or null if it means nothing.</summary>
    private ShellAction? ActionForPad(Pad p)
    {
        if (p is Pad.None) return null;
        foreach (var (act, _, _) in Actions)
            if (PadFor(act) == p) return act;
        // Two hardware keys that are aliases rather than bindings: the Guide
        // button is the console-shell key and Back is the console-shell "out",
        // and neither is worth a row in a mapping table nobody would look for
        // them in. They only apply if the user has not bound them to something.
        return p switch
        {
            Pad.Guide => ShellAction.QuickMenu,
            Pad.Back => ShellAction.Back,
            _ => null,
        };
    }

    private ShellAction? ActionForKey(Key k)
    {
        foreach (var (act, _, _) in Actions)
            if (KeyFor(act) == k) return act;
        return null;
    }

    /// <summary>
    /// Run one command. Every guard that used to live inside the input switch
    /// lives here instead, so the keyboard and the pad cannot drift apart — they
    /// were already subtly different before this (the pad could reach the
    /// library filters, the keyboard could not).
    /// </summary>
    private void InvokeAction(ShellAction a)
    {
        switch (a)
        {
            case ShellAction.Select:
                if (_layer == "search") ActivateFirstResult();
                else if (IsTextEntry()) ActivateLast();
                else ActivateFocused();
                break;
            case ShellAction.Back:
                Back(); break;
            case ShellAction.Search:
                if (_layer == "view") OpenSearch(); break;
            case ShellAction.QuickMenu:
                if (_layer == "view") OpenQuickMenu(); break;
            case ShellAction.PrevTab:
                if (_layer == "view") CycleTab(-1); break;
            case ShellAction.NextTab:
                if (_layer == "view") CycleTab(+1); break;
            case ShellAction.Settings:
                if (_layer == "view") SetTab("settings"); break;
            case ShellAction.FilterPrev:
                if (_layer == "view" && _tab == "library") CycleFilter(-1); break;
            case ShellAction.FilterNext:
                if (_layer == "view" && _tab == "library") CycleFilter(+1); break;
        }
    }

    // ------------------------------------------------------------------ labels

    private static string PadLabel(Pad p) => p switch
    {
        Pad.A => "A", Pad.B => "B", Pad.X => "X", Pad.Y => "Y",
        Pad.LB => "LB", Pad.RB => "RB", Pad.LT => "LT", Pad.RT => "RT",
        Pad.Start => "Start", Pad.Back => "Back", Pad.Guide => "Guide",
        Pad.Up => "למעלה", Pad.Down => "למטה", Pad.Left => "שמאלה", Pad.Right => "ימינה",
        _ => "-",
    };

    private static string KeyLabel(Key k) => k switch
    {
        Key.Enter => "Enter", Key.Escape => "Esc", Key.Tab => "Tab", Key.Space => "Space",
        Key.Back => "Backspace",
        Key.OemOpenBrackets => "[", Key.OemCloseBrackets => "]",
        Key.OemComma => ",", Key.OemPeriod => ".",
        Key.OemMinus => "-", Key.OemPlus => "=",
        _ => k.ToString(),
    };

    /// <summary>
    /// The pad label as the person holding the pad sees it. A DualSense owner who
    /// binds a button to ✕ and is then shown "A" has been told the wrong thing by
    /// the one screen whose entire job is to tell them what they bound.
    /// </summary>
    private string PadLabelForUser(Pad p)
    {
        if (_padKind is not (PadKind.Ps4 or PadKind.Ps5)) return PadLabel(p);
        return p switch
        {
            Pad.A => "✕", Pad.B => "○", Pad.X => "□", Pad.Y => "△",
            Pad.LB => "L1", Pad.RB => "R1", Pad.LT => "L2", Pad.RT => "R2",
            Pad.Start => "Options", Pad.Back => "Create", Pad.Guide => "PS",
            _ => PadLabel(p),
        };
    }

    // ------------------------------------------------------------ the capture

    /// <summary>Non-null while the shell is waiting for a button to be pressed.</summary>
    private (ShellAction Act, bool ForPad)? _capture;

    /// <summary>
    /// True when the press was swallowed by an open capture. Both input handlers
    /// call this FIRST, which is what makes rebinding work with the very buttons
    /// that would otherwise close the screen you are rebinding them on.
    /// </summary>
    private bool CapturePad(Pad p)
    {
        if (_capture is not { } c || !c.ForPad) return false;
        if (p is Pad.None) return true;

        // 🔴 THE ESCAPE HATCH CANNOT ITSELF BE BINDABLE HERE. If every button is
        // captured, a person who opens this with a pad and changes their mind has
        // no way out except the keyboard - on a device that may not have one. The
        // Guide button is reserved as "cancel" for exactly the length of this
        // screen, and the card says so.
        if (p is Pad.Guide) { EndCapture(null); return true; }

        SetBinding(c.Act, pad: p);
        EndCapture($"{ActionName(c.Act)} · שלט: {PadLabelForUser(p)}");
        return true;
    }

    private bool CaptureKey(Key k)
    {
        if (_capture is not { } c || c.ForPad) return false;
        if (k is Key.System or Key.LeftCtrl or Key.RightCtrl or Key.LeftShift
              or Key.RightShift or Key.LeftAlt or Key.RightAlt or Key.LWin or Key.RWin)
            return true;                                   // a modifier alone is not a binding
        if (k is Key.Escape) { EndCapture(null); return true; }

        SetBinding(c.Act, key: k);
        EndCapture($"{ActionName(c.Act)} · מקלדת: {KeyLabel(k)}");
        return true;
    }

    private static string ActionName(ShellAction a) =>
        Actions.First(x => x.Act == a).Name;

    /// <summary>
    /// Store one binding, and take it off whatever else was holding it.
    ///
    /// 🔴 TWO ACTIONS ON ONE BUTTON IS A SHELL THAT DOES THE WRONG THING AT
    /// RANDOM. ActionForPad returns the FIRST match, so a duplicate would leave
    /// the loser silently dead with nothing on screen saying so. Whoever binds it
    /// last wins, and the previous owner is explicitly cleared to "-" so the
    /// mapping screen shows the hole instead of hiding it.
    /// </summary>
    private void SetBinding(ShellAction a, Pad? pad = null, Key? key = null)
    {
        if (pad is { } p)
        {
            foreach (var (other, _, _) in Actions)
                if (other != a && PadFor(other) == p)
                    _settings.PadMap[other.ToString()] = Pad.None.ToString();
            _settings.PadMap[a.ToString()] = p.ToString();
        }
        if (key is { } k)
        {
            foreach (var (other, _, _) in Actions)
                if (other != a && KeyFor(other) == k)
                    _settings.KeyMap[other.ToString()] = Key.None.ToString();
            _settings.KeyMap[a.ToString()] = k.ToString();
        }
        _settings.Save();
    }

    private void EndCapture(string? toast)
    {
        _capture = null;
        DismissDialog();
        _layer = "view";
        RenderTab();
        if (toast is not null) { Sfx.Play(Sound.Select); ShowToast(toast); }
    }

    private void AskForBinding(ShellAction a, bool forPad)
    {
        Sfx.Play(Sound.Select);
        _layer = "dialog";
        _capture = (a, forPad);
        _dialogBack = () => EndCapture(null);

        ResetNav();
        _navViewStart = 0;
        DialogHost.Children.Clear();
        DialogHost.Visibility = Visibility.Visible;

        var sp = new StackPanel();
        sp.Children.Add(new TextBlock
        {
            Text = forPad ? "לחצו על כפתור בשלט" : "לחצו על מקש במקלדת",
            Style = (Style)FindResource("H2"),
            TextWrapping = TextWrapping.Wrap,
        });
        sp.Children.Add(new TextBlock
        {
            Text = $"הכפתור שתלחצו עליו יבצע מעכשיו \"{ActionName(a)}\".",
            Style = (Style)FindResource("Caption"),
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 8, 0, 4),
        });
        sp.Children.Add(new TextBlock
        {
            Text = forPad
                ? "אם הכפתור כבר משמש לפעולה אחרת - הוא יעבור לכאן, והפעולה הישנה תישאר בלי כפתור."
                  + "\nלביטול: כפתור ה-Guide (PS/Xbox) באמצע השלט."
                : "אם המקש כבר משמש לפעולה אחרת - הוא יעבור לכאן."
                  + "\nלביטול: Esc.",
            Style = (Style)FindResource("Caption"),
            TextWrapping = TextWrapping.Wrap,
            Opacity = 0.75,
            Margin = new Thickness(0, 10, 0, 0),
        });

        DialogHost.Children.Add(new Border
        {
            Style = (Style)FindResource("GlassPanelCard"),
            BorderBrush = (Brush)FindResource("HairlineBrush"),
            Width = CardWidth(620),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = (Effect)FindResource("ShadowPanel"),
            Child = sp,
        });
    }

    // ------------------------------------------------------------- the screen

    private void BuildMappingSection(StackPanel sp)
    {
        sp.Children.Add(Text(
            "כל פעולה וכפתור. בחרו שורה כדי להקצות לה כפתור אחר - בשלט או במקלדת.",
            "Caption", margin: new Thickness(0, 0, 0, 12)));

        foreach (var (act, name, what) in Actions)
        {
            Pad p = PadFor(act);
            Key k = KeyFor(act);
            string padTxt = p is Pad.None ? "לא מוקצה" : PadLabelForUser(p);
            string keyTxt = k is Key.None ? "לא מוקצה" : KeyLabel(k);

            var a = act;
            sp.Children.Add(Nav(RowButton(GlyphGame, $"{name} · שלט: {padTxt}", what,
                () => AskForBinding(a, forPad: true))));
            sp.Children.Add(Nav(RowButton(GlyphChip, $"{name} · מקלדת: {keyTxt}", null,
                () => AskForBinding(a, forPad: false))));
        }

        sp.Children.Add(Nav(RowButton(GlyphRefresh, "איפוס לברירת המחדל",
            "מחזיר את כל הכפתורים והמקשים למה שהיו",
            () =>
            {
                _settings.PadMap.Clear();
                _settings.KeyMap.Clear();
                _settings.Save();
                Sfx.Play(Sound.Select);
                RenderTab();
                ShowToast("המיפוי אופס");
            })));
    }
}
