using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Effects;
using BigLaunch.Services;

namespace BigLaunch;

/// <summary>
/// The glass material: what makes a floating surface read as glass rather than
/// as a dark card, and the one slider shape every value in the shell uses.
///
/// 🔴🔴 GLASS IS NOT A FILL, IT IS A RELATIONSHIP. A translucent panel over a
/// sharp screen is just a dirty window - you read the covers through it and the
/// text fights the artwork. What makes the reference look the way it does is
/// that the SHELL BEHIND the panel is blurred and pushed back while the panel is
/// up, so the panel is the only sharp thing on screen. That is Frost(), below,
/// and it is why the panel fills in Tokens.xaml can stay genuinely translucent
/// instead of creeping up to 98% opaque every time something is hard to read.
/// </summary>
public partial class MainWindow
{
    // ------------------------------------------------------------------ frost

    private const double FrostRadius = 16;
    private const double FrostScale = 0.986;

    /// <summary>
    /// Blur and push back everything behind the overlay layers.
    ///
    /// Only Chrome and Blade are touched: the hero art underneath is ALREADY
    /// blurred at radius 58, and stacking a second full-screen blur on top of it
    /// would double the most expensive thing the shell draws for a difference
    /// nobody can see.
    ///
    /// 🔴 THE EFFECT IS REMOVED, NOT LEFT AT RADIUS 0. A BlurEffect with radius
    /// zero still forces the whole layer through the effect pipeline every
    /// frame, so leaving one attached would tax the shell forever for the sake
    /// of the few seconds a panel is open. It is attached on the way in and
    /// detached the moment the fade-out lands.
    /// </summary>
    /// <summary>
    /// Re-derive the frost from WHAT IS ON SCREEN, rather than being told.
    ///
    /// 🔴 THE LAYERS STACK, SO A BOOLEAN IS NOT ENOUGH. A confirmation can open
    /// over the game blade, which is itself over the shell: the blade must blur
    /// when the dialog arrives and un-blur when it leaves, while the shell stays
    /// blurred underneath both. Every overlay just calls this and the answer is
    /// computed once from the visibilities — the alternative (each caller
    /// passing on/off) gets the two-deep case wrong in one direction or the
    /// other every time.
    /// </summary>
    private void UpdateFrost()
    {
        bool modal = DialogHost.Visibility == Visibility.Visible
                  || QuickMenu.Visibility == Visibility.Visible
                  || SearchHost.Visibility == Visibility.Visible;
        bool blade = Blade.Visibility == Visibility.Visible;

        // The shell blurs under anything at all; the blade blurs only under
        // something that is over IT.
        FrostOne(Chrome, modal || blade);
        if (blade) FrostOne(Blade, modal);
        else Blade.Effect = null;
    }

    private void FrostOne(FrameworkElement el, bool on)
    {
        if (!_settings.AnimationsEnabled)
        {
            el.Effect = on ? new BlurEffect { Radius = FrostRadius, KernelType = KernelType.Gaussian, RenderingBias = RenderingBias.Performance } : null;
            el.RenderTransform = Transform.Identity;
            return;
        }

        var d = new Duration(TimeSpan.FromMilliseconds(on ? 220 : 170));
        var ease = HouseEase(on);

        if (on)
        {
            var blur = el.Effect as BlurEffect;
            if (blur is null)
            {
                blur = new BlurEffect { Radius = 0, KernelType = KernelType.Gaussian, RenderingBias = RenderingBias.Performance };
                el.Effect = blur;
            }
            blur.BeginAnimation(BlurEffect.RadiusProperty,
                new DoubleAnimation(FrostRadius, d) { EasingFunction = ease });

            // Pushing the shell back a hair is what turns "a panel appeared" into
            // "the panel is in front" — depth the eye reads before it reads the
            // blur. RenderTransform, never LayoutTransform: ApplyUiScale owns the
            // layout transform, and re-laying the whole shell out for a modal
            // would re-wrap every row behind it.
            var st = el.RenderTransform as ScaleTransform;
            if (st is null || el.RenderTransform.IsFrozen)
            {
                st = new ScaleTransform(1, 1);
                el.RenderTransformOrigin = new Point(0.5, 0.5);
                el.RenderTransform = st;
            }
            st.BeginAnimation(ScaleTransform.ScaleXProperty, new DoubleAnimation(FrostScale, d) { EasingFunction = ease });
            st.BeginAnimation(ScaleTransform.ScaleYProperty, new DoubleAnimation(FrostScale, d) { EasingFunction = ease });
            return;
        }

        if (el.Effect is BlurEffect b)
        {
            var back = new DoubleAnimation(0, d) { EasingFunction = ease };
            back.Completed += (_, _) =>
            {
                // Only drop the effect if nothing re-frosted it in the meantime -
                // closing a picker that returns to the panel underneath fires this
                // completion AFTER the panel has already asked for frost again.
                if (el.Effect is BlurEffect cur && cur.Radius < 0.5) el.Effect = null;
            };
            b.BeginAnimation(BlurEffect.RadiusProperty, back);
        }
        if (el.RenderTransform is ScaleTransform s2)
        {
            s2.BeginAnimation(ScaleTransform.ScaleXProperty, new DoubleAnimation(1, d) { EasingFunction = ease });
            s2.BeginAnimation(ScaleTransform.ScaleYProperty, new DoubleAnimation(1, d) { EasingFunction = ease });
        }
    }

    /// <summary>
    /// The house curve, as a spline rather than a CubicEase.
    ///
    /// CubicEase is a fixed t³ - it decelerates evenly and reads as "correct but
    /// mechanical". The measured house curve (Tokens.xaml, EaseDecel) leaves
    /// fast and settles late, which is what a real object moved by a hand does
    /// and what every transition here now shares so they feel like one system.
    /// Arriving and leaving get different curves on purpose: things should
    /// arrive softly and leave briskly, never the other way round.
    /// </summary>
    private IEasingFunction HouseEase(bool arriving) =>
        new KeySplineEase((KeySpline)FindResource(arriving ? "EaseDecel" : "EaseStandard"));

    /// <summary>A KeySpline as an easing function, so the measured curves in
    /// Tokens.xaml can drive code-behind animations and not only storyboards.</summary>
    private sealed class KeySplineEase : IEasingFunction
    {
        private readonly KeySpline _s;
        public KeySplineEase(KeySpline s) { _s = s; }

        public double Ease(double t)
        {
            // Newton on the x-component of the cubic Bezier (P0=0, P3=1), then
            // read y at that parameter. Six iterations is well past visual
            // convergence for the curves we ship.
            double x1 = _s.ControlPoint1.X, y1 = _s.ControlPoint1.Y;
            double x2 = _s.ControlPoint2.X, y2 = _s.ControlPoint2.Y;
            double u = t;
            for (int i = 0; i < 6; i++)
            {
                double x = Bez(u, x1, x2) - t;
                double dx = DBez(u, x1, x2);
                if (Math.Abs(dx) < 1e-6) break;
                u -= x / dx;
                u = Math.Clamp(u, 0, 1);
            }
            return Bez(u, y1, y2);
        }

        private static double Bez(double t, double a, double b)
        {
            double m = 1 - t;
            return 3 * m * m * t * a + 3 * m * t * t * b + t * t * t;
        }

        private static double DBez(double t, double a, double b)
        {
            double m = 1 - t;
            return 3 * m * m * a + 6 * m * t * (b - a) + 3 * t * t * (1 - b);
        }
    }

    // ----------------------------------------------------------------- slider

    /// <summary>
    /// One slider shape for the whole shell: a rounded track, a filled portion,
    /// a round knob at the boundary and a value bubble over it.
    ///
    /// 🔴 THE GEOMETRY IS STAR COLUMNS, NOT A MEASURED WIDTH. A fill whose Width
    /// is computed from ActualWidth is a layout pass behind on every change and
    /// lands wrong on the very first draw - the bug this replaced. Two star
    /// columns are exact at the first pass and re-flow for free at any size, and
    /// the knob simply straddles the boundary between them.
    /// </summary>
    /// <summary>
    /// The slider's filled fraction, as an ANIMATABLE property.
    ///
    /// 🔴 A GridLength CANNOT BE ANIMATED, WHICH IS WHY THIS EXISTS. The geometry
    /// is two star columns (exact at the first layout pass, unlike a width
    /// measured from ActualWidth), but star widths can only be SET - so a value
    /// change jumped. This attached double is animated instead, and its callback
    /// writes the two column widths: the layout stays exact and the motion
    /// becomes something a spring can drive.
    /// </summary>
    private static readonly DependencyProperty FracProperty =
        DependencyProperty.RegisterAttached("Frac", typeof(double), typeof(MainWindow),
            new PropertyMetadata(0.0, OnFracChanged));

    private static void OnFracChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not Grid g || g.ColumnDefinitions.Count < 2) return;
        double f = Math.Clamp((double)e.NewValue, 0, 1);
        // Two columns for a plain ratio (the value bubble), three when there is a
        // knob between them - the middle column IS the knob, so it always has a
        // cell of its own to sit in. See BuildSlider.
        int last = g.ColumnDefinitions.Count - 1;
        g.ColumnDefinitions[0].Width = new GridLength(f, GridUnitType.Star);
        g.ColumnDefinitions[last].Width = new GridLength(1 - f, GridUnitType.Star);
    }

    private sealed class GlassSlider
    {
        public required FrameworkElement Root { get; init; }
        /// <summary>frac is 0..1; text is what the bubble shows.</summary>
        public required Action<double, string> Set { get; init; }
        /// <summary>Thicken the track and lift the knob while the row is in use -
        /// a control you have hold of should not look like one you do not.</summary>
        public Action<bool>? Grab { get; init; }
        /// <summary>The value bubble, held directly rather than dug back out of
        /// the visual tree — callers add their own marks to the track, and a
        /// lookup by child index breaks the moment one of them does.</summary>
        public FrameworkElement? Bubble { get; init; }
    }

    /// <param name="scrub">Called with 0..1 while the mouse drags the track.
    /// Null means the slider is display-only and swallows no mouse.</param>
    private GlassSlider BuildSlider(bool bubble = true, Action<double>? scrub = null)
    {
        const double Knob = 20, Height = 10;

        // 🔴 THE INSET IS HALF A KNOB. The knob straddles the boundary between the
        // two columns, so at 0% and at 100% half of it hangs outside the track -
        // and the row clipped it into a half-circle at exactly the two values a
        // user sits at most often. Inset by half its width and it stays whole
        // from end to end; the extra height leaves room for it to grow on grab.
        var track = new Grid
        {
            // 🔴 A FULL KNOB OF INSET, NOT HALF. Half its width is what the knob
            // OVERHANGS at each end, so a half-knob inset leaves it exactly flush
            // with the content edge - and "exactly flush" is where a row's own
            // padding, a scroller's clip or a rounded border shaves a sliver off.
            // At 0% (a muted app, the smallest display size) that sliver is half
            // the circle, which is the state people actually sit at.
            ClipToBounds = false,
            Height = Math.Max(Knob, Height) + 8,
            // The top inset is the BUBBLE'S room. It floats 26px above the track,
            // and with the old 8px it was drawn outside the row and sliced by
            // the focus ring - a read-out you cannot read.
            Margin = new Thickness(0, 32, 0, 4),
        };
        // 🔴🔴 THE KNOB GETS ITS OWN COLUMN, IT DOES NOT STRADDLE A BOUNDARY.
        //
        // It used to hang half its width past the edge between the filled and
        // empty columns, which is fine in the middle of the track and wrong at
        // both ends: at 0% (and 100%) the boundary IS the track's own edge, so
        // half the circle was arranged outside the cell and came out sliced -
        // exactly at the two values people leave a slider sitting at. Widening
        // the inset did not help, because the overhang is measured from the
        // CELL, not from the track. A fixed middle column removes the overhang
        // entirely: the knob is never outside anything, at any value.
        var left = new ColumnDefinition { Width = new GridLength(0, GridUnitType.Star) };
        var mid = new ColumnDefinition { Width = new GridLength(Knob) };
        var right = new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) };
        track.ColumnDefinitions.Add(left);
        track.ColumnDefinitions.Add(mid);
        track.ColumnDefinitions.Add(right);

        var bg = new Border
        {
            Height = Height,
            CornerRadius = new CornerRadius(Height / 2),
            Background = (Brush)FindResource("TrackBrush"),
            VerticalAlignment = VerticalAlignment.Center,
        };
        Grid.SetColumn(bg, 0);
        Grid.SetColumnSpan(bg, 3);
        track.Children.Add(bg);

        var fill = new Border
        {
            Height = Height,
            CornerRadius = new CornerRadius(Height / 2),
            Background = (Brush)FindResource("Accent"),
            VerticalAlignment = VerticalAlignment.Center,
        };
        // The fill runs up to and UNDER the knob, so there is never a gap between
        // the coloured part and the handle that marks its end.
        Grid.SetColumn(fill, 0);
        Grid.SetColumnSpan(fill, 2);
        track.Children.Add(fill);

        // The knob fills its own column exactly - no alignment, no negative
        // margin, nothing to overflow.
        var knob = new Border
        {
            Width = Knob,
            Height = Knob,
            CornerRadius = new CornerRadius(Knob / 2),
            Background = new SolidColorBrush(Colors.White),
            VerticalAlignment = VerticalAlignment.Center,
            Effect = new DropShadowEffect
            {
                BlurRadius = 10,
                ShadowDepth = 2,
                Direction = 270,
                Opacity = 0.45,
                Color = Colors.Black,
            },
        };
        Grid.SetColumn(knob, 1);
        track.Children.Add(knob);

        Border? tip = null;
        TextBlock? tipText = null;
        // 🔴🔴 THE TRACK RUNS RIGHT-TO-LEFT, WITH THE REST OF THE SHELL.
        //
        // It was briefly pinned LTR to cure an "inverted arrows" complaint, and
        // that was the wrong half of the problem: in a Hebrew UI the bar starts
        // where the reading starts, and a slider that fills from the left is the
        // one element on screen running against everything around it. The fill
        // grows from the RIGHT; what had to change instead is the ARROWS, which
        // now move the handle the way they point (see Move(): under a mirrored
        // track, "right" is toward the low end). Nothing here pins direction -
        // it simply inherits the window's.
        var host = new Grid();
        host.Children.Add(track);

        if (bubble)
        {
            tipText = new TextBlock
            {
                Style = (Style)FindResource("Caption"),
                Foreground = (Brush)FindResource("FgPrimary"),
                FlowDirection = FlowDirection.LeftToRight,
                HorizontalAlignment = HorizontalAlignment.Center,
            };
            tip = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(0xF0, 0x23, 0x2B, 0x38)),
                BorderBrush = (Brush)FindResource("GlassEdge"),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(8, 1, 8, 2),
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Top,
                Opacity = 0,
                Child = tipText,
            };
            // Same straddle as the knob, and it sits in the gap the track's own
            // top inset leaves for it.
            //
            // 🔴 A NEGATIVE MARGIN PUT IT OUTSIDE THE ROW. It used to be lifted
            // -26 from the top of the host, which is above the row itself - so
            // the focus ring sliced the read-out in half at every value. The
            // room is made INSIDE the row (the track's 32px top inset) and the
            // bubble is placed in it, rather than hung over the edge.
            // 🔴 A CANVAS, BECAUSE A CELL MEASURES ITS CHILD. The bubble sits in
            // the knob's own 20px column so it tracks the value - but a child of
            // a 20px cell is MEASURED against 20px, so the read-out came out
            // squeezed to a sliver with its text clipped away. A Canvas measures
            // its children against infinity, and re-centring it on its own width
            // is a one-line SizeChanged that only fires when the text changes.
            var tipAnchor = new Canvas { Width = Knob, Height = 0, ClipToBounds = false };
            tipAnchor.Children.Add(tip);
            tip.SizeChanged += (_, _) => Canvas.SetLeft(tip, (Knob - tip.ActualWidth) / 2);
            Grid.SetColumn(tipAnchor, 1);
            var tipRow = new Grid
            {
                Margin = new Thickness(0, 2, 0, 0),
                VerticalAlignment = VerticalAlignment.Top,
                IsHitTestVisible = false,
            };
            tipRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            tipRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(Knob) });
            tipRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            tipRow.Children.Add(tipAnchor);
            host.Children.Add(tipRow);

            // The bubble is a read-out for a value you are CHANGING, so it only
            // shows while the row that owns it has focus (see BindBubble). A
            // permanently visible bubble is noise on a screen full of rows.
        }

        // The whole track can be stretched from either end - this is what makes a
        // press that CANNOT move the value still answer the user.
        var rubber = new ScaleTransform(1, 1);
        host.RenderTransform = rubber;

        var grow = new ScaleTransform(1, 1);
        knob.RenderTransformOrigin = new Point(0.5, 0.5);
        knob.RenderTransform = grow;

        // 🔴 PRESS AND DRAG, NOT JUST CLICK. A single click that jumps the value
        // is fine for a mouse that knows where it is going; setting a level by
        // ear is a continuous act, and a slider you cannot HOLD is the one thing
        // every other volume control on the machine lets you do.
        if (scrub is not null)
        {
            double FracAt(Point p) => Math.Clamp(p.X / Math.Max(1.0, track.ActualWidth), 0, 1);

            host.PreviewMouseLeftButtonDown += (_, e) =>
            {
                host.CaptureMouse();
                scrub(FracAt(e.GetPosition(track)));
                // Handled, so the press never reaches the row behind - which
                // would otherwise treat a scrub as a click on the row itself.
                e.Handled = true;
            };
            host.PreviewMouseMove += (_, e) =>
            {
                if (host.IsMouseCaptured && e.LeftButton == MouseButtonState.Pressed)
                    scrub(FracAt(e.GetPosition(track)));
            };
            host.PreviewMouseLeftButtonUp += (_, e) =>
            {
                if (!host.IsMouseCaptured) return;
                host.ReleaseMouseCapture();
                e.Handled = true;
            };
        }

        double last = double.NaN;
        bool first = true;

        void Set(double frac, string text)
        {
            frac = Math.Clamp(frac, 0, 1);

            if (tip is not null && tipText is not null)
            {
                tipText.Text = text;
                // The bubble rides the same value: its row has the identical
                // column shape, so one property drives both.
                if (tip.Parent is Canvas c && c.Parent is Grid tg)
                    tg.SetValue(FracProperty, frac);
            }

            // The first draw is a STATE, not a change: animating from zero on
            // load would make every panel open with its sliders sweeping.
            if (first || !_settings.AnimationsEnabled || double.IsNaN(last))
            {
                first = false;
                track.BeginAnimation(FracProperty, null);
                track.SetValue(FracProperty, frac);
                last = frac;
                return;
            }

            // 🔴 A PRESS THAT CHANGES NOTHING MUST STILL ANSWER. Pushing right at
            // 100% did literally nothing on screen, which reads as a dropped
            // input rather than as "this is the end". The track now stretches a
            // few percent from the opposite end and springs back - the same
            // rubber-band an over-scrolled list gives you, and it is legible for
            // the same reason: it is a physical answer to a physical push.
            if (Math.Abs(frac - last) < 0.0005)
            {
                if (frac >= 0.999 || frac <= 0.001) Rubber(frac >= 0.5);
                return;
            }

            var move = new DoubleAnimation(frac, new Duration(TimeSpan.FromMilliseconds(260)))
            {
                // Overshoot, lightly: the value settles past its mark and comes
                // back, which is what makes a step feel elastic instead of typed.
                EasingFunction = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 0.34 },
            };
            track.BeginAnimation(FracProperty, move);
            last = frac;
        }

        void Rubber(bool atFillEnd)
        {
            if (!_settings.AnimationsEnabled) return;
            // Anchor the stretch at the end you are NOT pushing against, so the
            // track visibly leans toward the press.
            host.RenderTransformOrigin = new Point(atFillEnd ? 0 : 1, 0.5);
            var a = new DoubleAnimation(1.035, new Duration(TimeSpan.FromMilliseconds(110)))
            {
                AutoReverse = true,
                EasingFunction = new SineEase { EasingMode = EasingMode.EaseOut },
            };
            rubber.BeginAnimation(ScaleTransform.ScaleXProperty, a);
        }

        void Grab(bool on)
        {
            if (!_settings.AnimationsEnabled)
            {
                bg.Height = fill.Height = on ? Height + 4 : Height;
                return;
            }
            var d = new Duration(TimeSpan.FromMilliseconds(160));
            var ease = new BackEase { EasingMode = EasingMode.EaseOut, Amplitude = 0.5 };
            // The bar thickens under the hand and the knob comes up to meet it.
            var h = new DoubleAnimation(on ? Height + 4 : Height, d) { EasingFunction = ease };
            bg.BeginAnimation(FrameworkElement.HeightProperty, h);
            fill.BeginAnimation(FrameworkElement.HeightProperty, h.Clone());
            var k = new DoubleAnimation(on ? 1.18 : 1.0, d) { EasingFunction = ease };
            grow.BeginAnimation(ScaleTransform.ScaleXProperty, k);
            grow.BeginAnimation(ScaleTransform.ScaleYProperty, k.Clone());
        }

        return new GlassSlider { Root = host, Set = Set, Bubble = tip, Grab = Grab };
    }

    // -------------------------------------------------------------- state card

    /// <summary>
    /// The hero row a status panel opens with: what this thing is, and whether it
    /// is on.
    ///
    /// 🔴 IT LOOKS LIKE A SWITCH ONLY WHERE IT IS ONE. This shape exists because
    /// the reference opens its Bluetooth panel with a big on/off card - but
    /// nothing in Win32 turns a Bluetooth radio on, so ours states the state and
    /// hands off to the one place that can change it. A pill that reads "מופעל"
    /// is a fact; a switch that springs back is a lie, and a shell that lies once
    /// about a control is not trusted about any of them.
    /// </summary>
    private Button StateCard(string glyph, string title, string state, bool on,
                             string detail, Action click)
    {
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var mark = new TextBlock
        {
            Text = glyph,
            FontFamily = new FontFamily("Segoe Fluent Icons, Segoe MDL2 Assets"),
            FontSize = 22,
            Foreground = (Brush)FindResource(on ? "Accent" : "FgDim"),
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 14, 0),
        };
        Grid.SetColumn(mark, 0);
        grid.Children.Add(mark);

        var col = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
        col.Children.Add(new TextBlock
        {
            Text = title,
            Style = (Style)FindResource("Body"),
            FontWeight = FontWeights.SemiBold,
        });
        col.Children.Add(new TextBlock
        {
            Text = detail,
            Style = (Style)FindResource("Caption"),
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 3, 0, 0),
        });
        Grid.SetColumn(col, 1);
        grid.Children.Add(col);

        var pill = new Border
        {
            CornerRadius = new CornerRadius(13),
            Padding = new Thickness(14, 5, 14, 6),
            Margin = new Thickness(14, 0, 0, 0),
            VerticalAlignment = VerticalAlignment.Center,
            Background = on ? (Brush)FindResource("Accent") : (Brush)FindResource("GlassRowHi"),
            Child = new TextBlock
            {
                Text = state,
                Style = (Style)FindResource("Caption"),
                FontWeight = FontWeights.SemiBold,
                Foreground = on ? new SolidColorBrush(Color.FromRgb(0x0E, 0x14, 0x1B))
                                : (Brush)FindResource("FgSecondary"),
            },
        };
        Grid.SetColumn(pill, 2);
        grid.Children.Add(pill);

        var btn = new Button { Style = (Style)FindResource("ListRow"), Content = grid };
        btn.Click += (_, _) => { Sfx.Play(Sound.Select); click(); };
        return btn;
    }

    /// <summary>Fade the value bubble in/out with the focus of the row that owns
    /// it, so the number appears exactly while it can be changed.</summary>
    private void BindBubble(GlassSlider slider, FrameworkElement owner)
    {
        if (slider.Bubble is not { } tip) return;

        void Show(bool on)
        {
            if (!_settings.AnimationsEnabled) { tip.Opacity = on ? 1 : 0; return; }
            tip.BeginAnimation(UIElement.OpacityProperty,
                new DoubleAnimation(on ? 1 : 0, new Duration(TimeSpan.FromMilliseconds(140)))
                { EasingFunction = HouseEase(on) });
        }

        void State(bool on) { Show(on); slider.Grab?.Invoke(on); }

        owner.GotKeyboardFocus += (_, _) => State(true);
        owner.LostKeyboardFocus += (_, _) => State(false);
        owner.MouseEnter += (_, _) => State(true);
        owner.MouseLeave += (_, _) => { if (!owner.IsKeyboardFocusWithin) State(false); };
        if (owner.IsKeyboardFocusWithin) { tip.Opacity = 1; slider.Grab?.Invoke(true); }
    }
}
