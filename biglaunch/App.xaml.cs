using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows;
using System.Windows.Media;
using BigLaunch.Interop;
using BigLaunch.Services;

namespace BigLaunch;

public partial class App : Application
{
    // Steam and Big Picture are one product with two shells; so are we. A
    // second launch must FOCUS the running console, never open a second one.
    private static Mutex? _single;

    [DllImport("shell32.dll")]
    private static extern int SetCurrentProcessExplicitAppUserModelID(
        [MarshalAs(UnmanagedType.LPWStr)] string id);

    /// <summary>
    /// Write a design token so every DynamicResource consumer actually follows it.
    ///
    /// 🔴🔴 Application.Current.Resources[key] = x IS A SILENT NO-OP when a merged
    /// dictionary also defines that key. A DynamicResource resolves against the
    /// dictionary that CONTAINS the reference first, so Tokens.xaml's own
    /// AccentColor always beat the app-level one — which meant the "bind the OS
    /// accent" code below reported success and changed nothing, for every build
    /// since it was written. Nobody noticed because the hardcoded token and this
    /// machine's Windows accent are both blue.
    ///
    /// So: find the dictionary that OWNS the key and write THERE.
    /// </summary>
    public static void SetToken(string key, object value)
    {
        var owner = Owner(Current.Resources);
        if (owner is not null) owner[key] = value;
        else Current.Resources[key] = value;

        SmoothScroll.Trace($"token {key}={value} owner={(owner?.Source?.ToString() ?? (owner is null ? "APP" : "inline"))} " +
                           $"readback={Current.TryFindResource(key)}");

        ResourceDictionary? Owner(ResourceDictionary d)
        {
            foreach (var m in d.MergedDictionaries)
                if (Owner(m) is { } hit) return hit;
            return d.Contains(key) ? d : null;
        }
    }

    /// <summary>
    /// Repaint the whole shell in <paramref name="c"/>.
    ///
    /// 🔴🔴 SETTING THE *COLOUR* TOKEN ALONE IS NOT ENOUGH AT RUNTIME. Tokens.xaml
    /// holds <c>Accent</c> as a SolidColorBrush whose Color is a DynamicResource on
    /// AccentColor — and WPF realizes that brush ONCE. A later change to AccentColor
    /// does not re-evaluate the already-built brush, so every consumer keeps the
    /// colour the app started with. It looked like a picker running one choice
    /// behind; it was actually a picker that only ever worked at startup.
    ///
    /// So replace the BRUSH resource too: `{DynamicResource Accent}` on an element
    /// property DOES re-evaluate, so swapping the object repaints everything.
    /// </summary>
    public static void ApplyAccent(Color c)
    {
        SetToken("AccentColor", c);
        SetToken("AccentGlowColor", Color.FromArgb(0x99, c.R, c.G, c.B));
        SetToken("Accent", new SolidColorBrush(c));
    }

    protected override void OnStartup(StartupEventArgs e)
    {
        // MUST equal the AppUserModelID on our Start-menu/desktop shortcut
        // (installer.iss). Windows pairs the two to give the console its OWN
        // taskbar button instead of merging it into the launcher's — the
        // visible difference between "two programs" and "one program twice".
        try { SetCurrentProcessExplicitAppUserModelID("HebrewTranslationHub.BigLaunch"); }
        catch { /* cosmetic only — never block startup on it */ }

        // 🔴 ACCESS_DENIED IS ALSO "ALREADY RUNNING". A mutex owned by a
        // HIGHER-INTEGRITY process can refuse a medium-IL open, and CreateMutex
        // then reports ACCESS_DENIED rather than ALREADY_EXISTS - which .NET
        // surfaces as a THROW, not as fresh=false. Unhandled, that kills the new
        // copy on the spot: the shortcut does nothing, no window, no error, and
        // the console on screen stays the old build. The desktop launcher hit
        // exactly this and had to be taught the same rule.
        //
        // ⚠ Measured on this machine the elevated instance still answers 183
        // (ALREADY_EXISTS), so the ordinary path below is what runs and this
        // catch is defence, not the explanation for any bug seen here. It costs
        // nothing and closes a failure mode whose symptom is indistinguishable
        // from "my change did nothing".
        bool fresh;
        try
        {
            _single = new Mutex(true, @"Local\HebrewTranslationHub.BigLaunch", out fresh);
        }
        catch (UnauthorizedAccessException)
        {
            fresh = false;
        }
        if (!fresh)
        {
            // Another console is already up — bring it forward and exit quietly.
            Focus.RaiseExisting();
            Shutdown();
            return;
        }

        base.OnStartup(e);

        // Bind the OS accent so the shell takes on the user's Windows
        // personality, exactly as Winhanced binds SystemAccentColor.
        // A saved choice wins; empty means "follow Windows", which is the default
        // and what a shell should do until the user says otherwise.
        Color accent = Backdrop.AccentColor();
        try
        {
            string hex = AppSettings.Load().AccentHex;
            if (!string.IsNullOrWhiteSpace(hex))
                accent = (Color)ColorConverter.ConvertFromString(hex);
        }
        catch { }
        ApplyAccent(accent);

        DispatcherUnhandledException += (_, args) =>
        {
            // A console shell must never die on a background failure — a
            // missing cover or an unreadable cache is not a crash.
            //
            // 🔴🔴 BUT SWALLOWING SILENTLY IS ITS OWN BUG. A throw partway
            // through a render leaves a screen that LOOKS finished and is
            // missing whatever came after the throw — so the failure presents
            // as a design flaw, not as an error. One live example: a typo'd
            // resource key (DurMed, never defined) threw inside RenderTab AFTER
            // the view was added, so every screen shipped with no footer legend
            // and no initial focus, and nothing anywhere said why.
            // Handled, but never unrecorded.
            string line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {args.Exception}\n\n";
            Debug.WriteLine("BigLaunch unhandled: " + args.Exception);
            try
            {
                string dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BigLaunch");
                Directory.CreateDirectory(dir);
                File.AppendAllText(Path.Combine(dir, "errors.log"), line);
            }
            catch { }
            args.Handled = true;
        };
    }
}
