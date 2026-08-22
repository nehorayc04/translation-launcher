using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using BigLaunch.Services;

namespace BigLaunch;

public partial class MainWindow
{
    /// <summary>
    /// Rows on an ordinary PAGE that own left/right, the way the volume row owns
    /// it inside a system panel. Cleared with the rest of the navigation map on
    /// every render, because the elements in it die with the page they were
    /// built for and a stale entry would answer for a row that no longer exists.
    /// </summary>
    private readonly Dictionary<FrameworkElement, Action<int>> _pageSteps = new();

    private static readonly (string Key, string Name, string What)[] SizeGroups =
    {
        ("tiles",  "כרטיסיות המשחקים", "העטיפות עצמן - כמה מהן נכנסות לשורה"),
        ("chrome", "השורה העליונה",    "נתוני המערכת, השעון והאייקונים שבצד"),
        ("text",   "הטקסט",            "כותרות, שמות ותיאורים בכל המסכים"),
        ("hints",  "רמזי הכפתורים",    "השורה התחתונה - בחירה, חזרה וסמלי המקשים"),
    };

    /// <summary>
    /// What each group is drawn at when its slider reads 100%.
    ///
    /// 🔴🔴 "100%" IS A DEFAULT, NOT A CONSTANT OF NATURE. These four numbers are
    /// the sizes this shell was actually tuned to on a real television, arrived
    /// at by sitting in front of it and moving the sliders - so they are what
    /// "רגיל" has to mean. Leaving them as a user override instead would have
    /// left every fresh install opening at a size nobody wants, with the right
    /// one reachable only by re-discovering these same four numbers by hand.
    ///
    /// The sliders keep their own 0.60..1.60 range on TOP of this, so 100% is
    /// the tuned size and 120% is a fifth larger than the tuned size - which is
    /// what a percentage on a settings screen is supposed to mean.
    ///
    /// Existing installs are rebased once (AppSettings.SizeBaseline): the four
    /// stored multipliers that produced this look are reset to 1.0, so the
    /// screen does not change under anyone the day this shipped.
    /// </summary>
    private static double GroupBase(string key) => key switch
    {
        "tiles" => 1.20,
        "chrome" => 1.30,
        "text" => 1.20,
        _ => 1.25,
    };

    /// <summary>The multiplier the renderer should actually use.</summary>
    private double GroupEffective(string key) => GroupBase(key) * GroupScale(key);

    private double GroupScale(string key) => key switch
    {
        "tiles" => _settings.ScaleTiles,
        "chrome" => _settings.ScaleChrome,
        "text" => _settings.ScaleText,
        _ => _settings.ScaleHints,
    };

    private void SetGroupScale(string key, double v)
    {
        // 🔴 CLAMPED, AND THE FLOOR IS NOT ZERO. A slider that can reach a size
        // nothing is readable at is a slider that can lock somebody out of the
        // screen they would have to use to undo it — and this shell is driven
        // from a sofa with a pad, where "just use the mouse" is not an answer.
        v = Math.Clamp(v, 0.60, 1.60);
        switch (key)
        {
            case "tiles": _settings.ScaleTiles = v; break;
            case "chrome": _settings.ScaleChrome = v; break;
            case "text": _settings.ScaleText = v; break;
            default: _settings.ScaleHints = v; break;
        }
    }

    /// <summary>
    /// The per-group size screen: one track per group, 100% in the middle.
    ///
    /// It is a PAGE, not a dialog, and that is deliberate — you are judging the
    /// effect on the shell itself, so the shell has to stay visible and has to
    /// re-draw at the new size as you move. A modal card over a dimmed screen
    /// would hide the only thing you are looking at.
    /// </summary>
    private void PickPerGroupSizes()
    {
        _settings.UiScale = 0.85;      // "רגיל" is what 100% on every track means
        _settings.Save();
        ApplyUiScale();
        _setCat = "גודל ותצוגה";
        _sizesOpen = true;
        Sfx.Play(Sound.Select);
        RenderTab();
    }

    private bool _sizesOpen;

    private void BuildSizeSliders(StackPanel sp)
    {
        sp.Children.Add(Text("התאמה אישית של הגדלים", "H3", margin: new Thickness(0, 4, 0, 6)));
        sp.Children.Add(Text(
            "כל פס שולט על קבוצה אחת בנפרד. 100% באמצע הוא הגודל של \"רגיל\" - " +
            "ימינה גדול יותר, שמאלה קטן יותר. חץ ימין/שמאל או הסטיק מזיזים; " +
            "בחירה מחזירה את הפס ל-100%.",
            "Caption", margin: new Thickness(0, 0, 0, 14)));

        foreach (var (key, name, what) in SizeGroups)
            sp.Children.Add(SliderRow(key, name, what));

        sp.Children.Add(Nav(RowButton(GlyphRefresh, "החזרת כל הפסים ל-100%",
            "מחזיר את כל ארבע הקבוצות לגודל של \"רגיל\"",
            () =>
            {
                _settings.ScaleTiles = _settings.ScaleChrome =
                    _settings.ScaleText = _settings.ScaleHints = 1.0;
                _settings.Save();
                ApplyUiScale();
                Sfx.Play(Sound.Select);
                RenderTab();
                ShowToast("כל הגדלים חזרו ל-100%");
            })));

        sp.Children.Add(Nav(RowButton(GlyphBack, "חזרה לגדלים המוכנים",
            "קטן · רגיל · גדול · ענק",
            () =>
            {
                // 🔴 A THROTTLED SAVE CAN LOSE THE LAST NOTCH. Dragging writes
                // through SaveThrottled so a held direction does not hammer the
                // disk, which means the final press may still be sitting in the
                // 2-second coalescing window when you walk away. Leaving the
                // screen is the moment the value becomes final, so it is written
                // for real here - otherwise the number you settled on and the
                // number you get back are quietly different.
                _settings.Save();
                _sizesOpen = false;
                Sfx.Play(Sound.Back);
                RenderTab();
            })));
    }

    /// <summary>One track. It updates ITSELF as the value moves — a full page
    /// re-render per step would throw the focus and the scroll away on every
    /// single press, which is exactly what a slider must not do.</summary>
    private UIElement SliderRow(string key, string name, string what)
    {
        Action? RedrawRef = null;

        var pct = new TextBlock
        {
            Style = (Style)FindResource("H3"),
            // 🔴 A PERCENTAGE IS AN LTR RUN INSIDE AN RTL PARAGRAPH. Left to the
            // window's direction the sign leads the digits and it renders "%100",
            // which reads as a different number for a moment every time. The
            // value bubble already isolates itself; this is the same fix for the
            // label beside it.
            FlowDirection = FlowDirection.LeftToRight,
            VerticalAlignment = VerticalAlignment.Center,
            MinWidth = 86,
            Margin = new Thickness(16, 0, 0, 0),
            TextAlignment = TextAlignment.Right,
        };

        // 🔴 THE SAME SLIDER AS THE VOLUME PANEL, NOT A LOOKALIKE. This used to be
        // its own track drawn from ActualWidth - which is a layout pass behind on
        // every change, needs a SizeChanged hook to catch up, and drifted from
        // the volume slider's look the moment either one was touched. BuildSlider
        // (MainWindow.Glass.cs) is star-column geometry: exact on the first pass,
        // free to re-flow, and identical everywhere a value is set in this shell.
        // Dragging maps the track straight onto the 0.60..1.60 range. Rounded to
        // the same 5% notch the arrows use, so a drag and a press cannot leave
        // the value on numbers the keyboard could never reach.
        var slider = BuildSlider(scrub: frac =>
        {
            double v = 0.60 + Math.Round(frac * 100 / 5.0) * 0.05;
            if (Math.Abs(v - GroupScale(key)) < 0.001) return;
            SetGroupScale(key, v);
            _settings.SaveThrottled();
            ApplyUiScale();
            RedrawRef?.Invoke();
        });
        var trackHost = slider.Root;

        // The 100% mark, drawn on the track so "the middle" is a place you can
        // see rather than a number you have to read. 0.60..1.60 across the track
        // puts 1.00 at 40% of the way, and two star columns place it there
        // without measuring anything.
        var markRow = new Grid { IsHitTestVisible = false, Margin = new Thickness(0, 32, 0, 4) };
        markRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(0.40, GridUnitType.Star) });
        markRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(20) });
        markRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(0.60, GridUnitType.Star) });
        var mark = new Border
        {
            Width = 2, Height = 16,
            Background = new SolidColorBrush(Color.FromArgb(0x77, 0xFF, 0xFF, 0xFF)),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        Grid.SetColumn(mark, 1);
        markRow.Children.Add(mark);
        ((Grid)trackHost).Children.Insert(1, markRow);

        void Redraw()
        {
            double v = GroupScale(key);
            pct.Text = $"{v * 100:0}%";
            slider.Set((v - 0.60) / 1.00, $"{v * 100:0}%");
        }
        RedrawRef = Redraw;

        // 🔴 A GRID, NOT A HORIZONTAL StackPanel. The reading is an LTR island in
        // an RTL row, and inside a StackPanel that mixture decided its own
        // position: the percentage floated somewhere in the middle of the row,
        // detached from both the name and the track it belongs to. Two columns
        // put the name at the reading start and the value at the far end, which
        // is where the same number sits in the volume panel.
        var head = new Grid();
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        head.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var labels = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
        labels.Children.Add(new TextBlock { Text = name, Style = (Style)FindResource("H3") });
        labels.Children.Add(new TextBlock
        {
            Text = what,
            Style = (Style)FindResource("Caption"),
            Margin = new Thickness(0, 2, 0, 0),
        });
        Grid.SetColumn(labels, 0);
        head.Children.Add(labels);
        Grid.SetColumn(pct, 1);
        head.Children.Add(pct);

        var body = new StackPanel { Margin = new Thickness(18, 12, 18, 12) };
        body.Children.Add(head);
        body.Children.Add(trackHost);

        var btn = new Button
        {
            Style = (Style)FindResource("ListRow"),
            Content = body,
            // Select resets this one track. There is nothing else "pressing" a
            // slider could sensibly mean, and it gives the pad a way back to the
            // default without hunting for the exact middle.
        };
        btn.Click += (_, _) =>
        {
            SetGroupScale(key, 1.0);
            _settings.Save();
            ApplyUiScale();
            Redraw();
            Sfx.Play(Sound.Select);
        };

        // No SizeChanged hook any more: star columns re-flow on their own, so the
        // only thing that has to re-draw is a VALUE change.
        BindBubble(slider, btn);
        btn.Loaded += (_, _) => Redraw();

        _pageSteps[btn] = delta =>
        {
            // delta arrives as ±5 from the shared claim; one notch is 5%.
            SetGroupScale(key, GroupScale(key) + (delta > 0 ? 0.05 : -0.05));
            _settings.SaveThrottled();
            ApplyUiScale();
            Redraw();
            Sfx.Play(Sound.Navigate);
        };

        return Nav(btn);
    }
}
