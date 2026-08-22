using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace BigLaunch;

/// <summary>
/// Animated scrolling for the content host.
///
/// Two problems, one helper:
///
/// 🔴🔴 THE VIEW NEVER SCROLLED AT ALL. Every screen was added straight into a
/// Grid, so anything past the fold was simply unreachable — the home screen
/// rendered a third row's HEADER at the bottom edge with its tiles below the
/// window, which reads as an empty section rather than as "there is more here".
/// A console shell has no scrollbar to hint at it and no mouse wheel in the
/// user's hand, so the only route to that content is focus movement.
///
/// 🔴 AND WPF'S OWN BringIntoView IS AN INSTANT JUMP. On a 10ft UI a hard cut
/// between rows destroys the sense of a continuous surface — the eye loses the
/// selection and has to re-find it. The focus move and the scroll have to look
/// like one motion, so the offset is animated on the same easing the rest of
/// the shell uses, and any in-flight scroll is replaced rather than queued
/// (a held direction must never stack up a backlog of animations).
/// </summary>
public static class SmoothScroll
{
    /// <summary>
    /// Pixels of dissolve at a scroll edge — and the reason it is a FIELD and not
    /// two local consts.
    ///
    /// 🔴 THE FADE AND THE SCROLL HAVE TO AGREE, OR THE LAST ROW LOOKS BROKEN.
    /// The bring-into-view below parks a focused row a fixed distance above the
    /// bottom edge; the mask dissolves a fixed distance up from that same edge.
    /// When the parking distance was the SMALLER of the two (24 vs 44), every
    /// row reached by scrolling to the end landed half-inside its own fade — the
    /// settings screen's launcher-handoff button and the library's refresh row
    /// both rendered as a title with its card sliced off underneath, which reads
    /// as a rendering bug rather than as a soft edge. The tailroom is derived
    /// from this number so the two can never drift apart again.
    /// </summary>
    // 🔴 26, NOT 44. The ramp is a hint that content continues, and at 44 it
    // was reading as a band of dead screen: on the home page the last shelf sat
    // under a 44px dissolve on top of a 32px pad on top of the footer's own
    // height, so the bottom eighth of the frame held nothing but fading. A
    // dissolve only has to be wide enough not to look like a cut.
    private const double EdgeRamp = 26;

    /// <summary>
    /// Set BIGLAUNCH_SCROLL_DIAG=1 to trace every bring-into-view to
    /// %LOCALAPPDATA%\BigLaunch\scroll.log. Reasoning about which of three
    /// nested scroll hosts moved the view is guesswork from a screenshot; the
    /// numbers say it in one run.
    /// </summary>
    private static readonly bool Diag =
        Environment.GetEnvironmentVariable("BIGLAUNCH_SCROLL_DIAG") == "1";

    /// <summary>Diagnostic hook for the nav, gated by the same env switch.</summary>
    public static void Trace(string s) { if (Diag) Log(s); }

    private static void Log(string s)
    {
        try
        {
            string dir = System.IO.Path.Combine(Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData), "BigLaunch");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.AppendAllText(System.IO.Path.Combine(dir, "scroll.log"),
                $"[{DateTime.Now:HH:mm:ss.fff}] {s}\n");
        }
        catch { }
    }

    /// <summary>Animatable proxy for ScrollViewer.VerticalOffset, which is read-only.</summary>
    public static readonly DependencyProperty OffsetProperty =
        DependencyProperty.RegisterAttached(
            "Offset", typeof(double), typeof(SmoothScroll),
            new PropertyMetadata(0.0, OnOffsetChanged));

    public static void SetOffset(DependencyObject o, double v) => o.SetValue(OffsetProperty, v);
    public static double GetOffset(DependencyObject o) => (double)o.GetValue(OffsetProperty);

    private static void OnOffsetChanged(DependencyObject o, DependencyPropertyChangedEventArgs e)
    {
        if (o is ScrollViewer sv) sv.ScrollToVerticalOffset((double)e.NewValue);
    }

    /// <summary>
    /// Build the content host. Padding at the bottom is not decoration: without
    /// it the last row sits flush against the footer legend and reads as clipped.
    /// </summary>
    public static ScrollViewer Host(FrameworkElement content, bool animated)
    {
        var sv = new ScrollViewer
        {
            Content = content,
            // No visible scrollbar — a console surface shows its extent by
            // motion, not by chrome. It still scrolls.
            VerticalScrollBarVisibility = ScrollBarVisibility.Hidden,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Focusable = false,
            // Pixel scrolling, not item-at-a-time: rows are 264px tall and a
            // logical-unit scroll would jump most of a screen per step.
            CanContentScroll = false,
            Padding = new Thickness(0, 0, 0, 48),

            // 🔴 A SCROLL EDGE, NOT A GUILLOTINE. Once the view actually
            // scrolled, every row met the header band at a hard horizontal cut
            // straight across the box art - which reads as a torn row, not as
            // "there is more above". Fading the content into the chrome is the
            // same trick as a scroll-edge effect: the boundary stops being a
            // line and becomes a transition. Cheap by design - a 4-stop linear
            // gradient, no blur - because this composites every frame while the
            // surface moves, and this shell has already paid once for putting a
            // blur on an always-on surface.
            //
            // The gradient is VERTICAL, so unlike a horizontal one it is immune
            // to the RTL mirroring of the element's own coordinate space.
        };

        AttachEdgeFade(sv);

        // ⚠️ ATTACH TO THE CONTENT, NOT TO THE ScrollViewer. RequestBringIntoView
        // BUBBLES, so the handler nearest the source wins the right to act
        // first - and the ScrollViewer's own ScrollContentPresenter sits BETWEEN
        // the content and the ScrollViewer. Handling it on the ScrollViewer runs
        // after the presenter has already jumped, so the animation had nothing
        // left to animate and every row change was an instant cut.
        // The content is BELOW the presenter, so handling it there suppresses
        // the built-in jump and leaves the motion to us - while the row's own
        // horizontal ScrollViewer, being lower still, keeps working untouched.
        AttachFollowFocus(sv, content, animated);
        AttachWheel(sv);
        return sv;
    }

    /// <summary>
    /// Make a scroller FOLLOW THE FOCUS, for scrollers that were not built by
    /// Host() — the system panels build their own.
    ///
    /// 🔴 A PANEL THAT DOES NOT FOLLOW ITS FOCUS IS A PANEL WITH A HIDDEN HALF.
    /// The Bluetooth panel scrolls, and its "search / stop searching" row lives
    /// under four paired devices: pressing Down walked focus onto a row nobody
    /// could see, and pressing the search row re-rendered the panel back at the
    /// top, so the scanning state and the stop button were both invisible. The
    /// wheel worked, which is exactly why it looked like a design decision
    /// rather than a missing handler.
    ///
    /// See Host() for why the handler goes on the CONTENT and not on the
    /// ScrollViewer: the event bubbles, and the presenter in between would
    /// otherwise jump before we ever see it.
    /// </summary>
    public static void AttachFollowFocus(ScrollViewer sv, FrameworkElement content, bool animated)
        => content.AddHandler(FrameworkElement.RequestBringIntoViewEvent,
                              new RequestBringIntoViewEventHandler((s, e) => Bring(sv, e, animated)), true);

    /// <summary>Where the wheel is currently steering, so notches accumulate.</summary>
    private static readonly DependencyProperty WheelTargetProperty =
        DependencyProperty.RegisterAttached(
            "WheelTarget", typeof(double), typeof(SmoothScroll), new PropertyMetadata(double.NaN));

    /// <summary>
    /// Mouse-wheel scrolling for a shell that animates its own offset.
    ///
    /// 🔴🔴 THE WHEEL WAS DEAD IN EVERY MENU, and the cause is this class rather
    /// than the ScrollViewer. Once <see cref="Bring"/> runs, the offset is driven
    /// by an animation on <see cref="OffsetProperty"/> with FillBehavior.HoldEnd
    /// — and a held animation OWNS its property. WPF's built-in wheel handler
    /// calls ScrollToVerticalOffset directly, so the view moved for a single
    /// frame and the still-holding animation immediately put it back. From a
    /// couch that is indistinguishable from a wheel that does nothing.
    ///
    /// The fix is not to remove the hold (the comment on <see cref="Bring"/>
    /// explains what that breaks) but to route the wheel through the SAME
    /// property, so both input paths steer one value instead of fighting over it.
    ///
    /// Two behaviours it gains by being ours:
    ///  * ACCUMULATION — a second notch during an in-flight glide adds to the
    ///    target instead of restarting from the current position, so spinning
    ///    fast travels fast. Re-seating from the live offset each time would make
    ///    a quick spin crawl, which is the classic smooth-scroll regression.
    ///  * INTERRUPTIBILITY — the animation always restarts from the REAL current
    ///    offset, so a wheel flick during a focus glide takes over cleanly rather
    ///    than jumping to wherever the previous animation was aiming.
    /// </summary>
    public static void AttachWheel(ScrollViewer sv)
    {
        // PREVIEW, not the bubbling event: whatever is eating it upstream (the
        // presenter, a nested host) never gets the chance.
        sv.PreviewMouseWheel += (_, e) =>
        {
            if (sv.ScrollableHeight <= 0) return;

            // A notch is 120. ~1.6px per unit ≈ 190px — about half a tile row,
            // so one notch reads as a deliberate step and three clear a row.
            double from = double.IsNaN(GetWheelTarget(sv)) ? sv.VerticalOffset : GetWheelTarget(sv);

            // The accumulated target is only trustworthy while it is still ahead
            // of the view in the SAME direction; anything else (a focus glide, a
            // re-render, a page change) has moved the surface underneath it.
            if (Math.Abs(from - sv.VerticalOffset) > sv.ViewportHeight) from = sv.VerticalOffset;

            double to = Math.Max(0, Math.Min(from - e.Delta * 1.6, sv.ScrollableHeight));
            SetWheelTarget(sv, to);
            e.Handled = true;

            if (Math.Abs(to - sv.VerticalOffset) < 0.5) return;

            sv.BeginAnimation(OffsetProperty, null);
            SetOffset(sv, sv.VerticalOffset);
            sv.BeginAnimation(OffsetProperty, new DoubleAnimation
            {
                To = to,
                Duration = TimeSpan.FromMilliseconds(210),
                EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut },
            });
        };
    }

    private static void SetWheelTarget(DependencyObject o, double v) => o.SetValue(WheelTargetProperty, v);
    private static double GetWheelTarget(DependencyObject o) => (double)o.GetValue(WheelTargetProperty);

    /// <summary>
    /// How far a focused row must be parked from the bottom edge so it never
    /// sits inside the dissolve. Derived from <see cref="EdgeRamp"/> for the
    /// reason that field documents — the fade and the scroll have to agree —
    /// and PUBLIC because the spatial nav parks rows on scrollers that are not
    /// <see cref="Host"/>s (the game blade) and would otherwise need its own
    /// hard-coded copy of the same number.
    /// </summary>
    public static double FocusTailroom => EdgeRamp + 16;

    /// <summary>
    /// The scroll-edge dissolve, applied to any vertical <see cref="ScrollViewer"/>.
    ///
    /// 🔴 THIS IS SHARED ON PURPOSE. It began life inline in <see cref="Host"/>,
    /// and when the game blade turned out to guillotine its description mid-glyph
    /// the tempting fix was a second copy next to the blade's own scroller. That
    /// copy was written and it was subtly WRONG in exactly the way the comments
    /// here already warn about: it expressed the ramp as a fraction of the box
    /// and so dissolved the PADDING instead of the content. One implementation,
    /// two call sites — the hard-won corrections then apply to both.
    ///
    /// 🔴 THE STOPS ARE SET IN PIXELS, NOT AS FIXED FRACTIONS. The Padding lives
    /// INSIDE the viewport, so the content stops short of the box while a fixed
    /// percentage ramp starts below that: the ramp dissolves empty space and the
    /// last row is still guillotined. A fraction cannot know about a padding
    /// measured in pixels.
    ///
    /// An edge with nothing behind it stays SQUARE — fading the top while the
    /// view is already at the top just dims the first row for no reason. The
    /// fade means "this continues", so it may only appear when that is true.
    /// </summary>
    public static void AttachEdgeFade(ScrollViewer sv)
    {
        var mask = new LinearGradientBrush
        {
            StartPoint = new Point(0, 0),
            EndPoint = new Point(0, 1),
            GradientStops =
            {
                new GradientStop(Color.FromArgb(0x00, 0, 0, 0), 0.000),
                new GradientStop(Color.FromArgb(0xFF, 0, 0, 0), 0.000),
                new GradientStop(Color.FromArgb(0xFF, 0, 0, 0), 1.000),
                new GradientStop(Color.FromArgb(0x00, 0, 0, 0), 1.000),
            },
        };
        sv.OpacityMask = mask;

        void Edges()
        {
            double h = sv.ActualHeight;
            if (h <= 1) return;
            // Where the CONTENT ends inside the box — above the padding.
            double contentEnd = Math.Max(0, h - sv.Padding.Bottom);
            bool atTop = sv.VerticalOffset <= 1;
            bool atBottom = sv.VerticalOffset >= sv.ScrollableHeight - 1;
            mask.GradientStops[1].Offset = atTop ? 0 : EdgeRamp / h;
            mask.GradientStops[2].Offset = atBottom ? 1 : Math.Max(0, contentEnd - EdgeRamp) / h;
            mask.GradientStops[3].Offset = atBottom ? 1 : contentEnd / h;
        }

        sv.ScrollChanged += (_, _) => Edges();
        sv.SizeChanged += (_, _) => Edges();
        sv.Loaded += (_, _) => Edges();
    }

    private static void Bring(ScrollViewer sv, RequestBringIntoViewEventArgs e, bool animated)
    {
        if (e.TargetObject is not FrameworkElement fe || fe == sv) return;
        if (!fe.IsDescendantOf(sv)) { if (Diag) Log("  not a descendant"); return; }

        // 🔴🔴 A ScrollViewer RE-RAISES BringIntoView FOR ITSELF once it has
        // scrolled its own content, so ancestors can reveal the whole viewer.
        // Measured on the home screen: focusing a tile produced three requests -
        // the tile (246..510, fits, no scroll), its row's viewer (236..520,
        // fits), and then a viewer spanning 183..1256 in a 903px viewport. That
        // last one can never "fit", so the handler dutifully scrolled to its
        // BOTTOM and the view slammed past two rows on a single D-pad press.
        // Only the focused leaf is a meaningful target here, and an element
        // taller than the viewport has no correct answer at all.
        if (fe is ScrollViewer) return;

        Rect r;
        try { r = fe.TransformToAncestor(sv).TransformBounds(new Rect(fe.RenderSize)); }
        catch { return; }   // not laid out yet — the next focus will retry

        if (r.Height > sv.ViewportHeight) return;

        if (Diag)
            Log($"bring src={fe.GetType().Name} rect={r.Top:0}..{r.Bottom:0} " +
                $"vp={sv.ViewportHeight:0} off={sv.VerticalOffset:0} scrollable={sv.ScrollableHeight:0}");

        // Keep the section header above the focused row in frame. Landing a row
        // flush against the top edge hides what it belongs to.
        //
        // The tail clears the dissolve ramp with room to spare — a row parked
        // exactly ON the ramp's edge would still be touched by its first, almost
        // invisible stop, and "almost invisible" on box art is a grey haze.
        const double headroom = 96;
        double tailroom = FocusTailroom;
        double off = sv.VerticalOffset;
        if (r.Bottom + tailroom > sv.ViewportHeight) off += r.Bottom + tailroom - sv.ViewportHeight;
        else if (r.Top - headroom < 0) off += r.Top - headroom;

        off = Math.Max(0, Math.Min(off, sv.ScrollableHeight));
        if (Math.Abs(off - sv.VerticalOffset) < 0.5) { e.Handled = true; return; }

        e.Handled = true;   // we own the scroll; suppress WPF's instant jump

        // Focus has taken the surface somewhere the wheel did not ask for, so
        // its accumulated target is now stale — a notch after a focus glide must
        // start from where the view actually IS, not from where the wheel was
        // last aiming before the pad moved.
        SetWheelTarget(sv, double.NaN);

        if (!animated) { sv.ScrollToVerticalOffset(off); return; }

        // Replace any in-flight animation, re-seating the base value from the
        // REAL current offset so a held direction glides continuously instead
        // of restarting from wherever the last animation was aiming.
        //
        // ⚠️ The fill behaviour must HOLD. With FillBehavior.Stop the attached
        // property snaps back to its base the moment the animation ends, and the
        // callback dutifully scrolls back with it — the view would slide to the
        // row and then jump away from it.
        sv.BeginAnimation(OffsetProperty, null);
        SetOffset(sv, sv.VerticalOffset);
        sv.BeginAnimation(OffsetProperty, new DoubleAnimation
        {
            To = off,
            Duration = TimeSpan.FromMilliseconds(260),
            EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut },
        });
    }
}
