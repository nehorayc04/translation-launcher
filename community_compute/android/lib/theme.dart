// The launcher's design system, in Flutter — same canvas/brand/glass, but native
// (real GPU): shifting colorful ambient background, real backdrop blur, springs.
import 'dart:math' as math;
import 'dart:ui' show ImageFilter;
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class T {
  static const canvas = Color(0xFF050510);
  static const ink = Color(0xFF0A0A14);
  static const text = Color(0xFFF0F0FF);
  static const muted = Color(0xFF8B93B0);
  static const yellow = Color(0xFFFFF700);
  static const cyan = Color(0xFF00FFE0);
  static const green = Color(0xFF3FE08A);
  static const amber = Color(0xFFFFB020);
  static const red = Color(0xFFFF5C5C);
  static const purple = Color(0xFFA78BFA);
  static const pink = Color(0xFFF472B6);

  static const glass = Color(0xE00C0C1A);
  static const line = Color(0x14FFFFFF);

  /// Selectable accent swatches (launcher-style personalization).
  static const accents = <String, Color>{
    'green': green, 'cyan': cyan, 'yellow': yellow,
    'purple': purple, 'pink': pink, 'amber': amber,
  };

  static ThemeData build() {
    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: canvas,
      colorScheme: base.colorScheme.copyWith(primary: cyan, secondary: yellow, surface: glass),
      textTheme: base.textTheme.apply(fontFamily: 'Heebo', bodyColor: text, displayColor: text),
      splashFactory: InkSparkle.splashFactory,
    );
  }
}

/// Personalization state (mirrors the launcher's Settings) — persisted + observable.
/// anim: 3=מלאה · 2=רגילה · 1=מופחתת · 0=כבויה. textScale 0.85..1.25.
///
/// TWO independent colour choices:
///   • accentKey  — the BUTTON/accent colour, always a fixed swatch (no cycling).
///   • rainbowBg  — when on, the BACKGROUND (ambient) shifts colours automatically.
class Prefs extends ChangeNotifier {
  static final Prefs I = Prefs._();
  Prefs._();
  late SharedPreferences _p;

  String accentKey = 'green';   // static button colour
  bool rainbowBg = true;        // the background auto-cycles its colours
  int anim = 3;
  double textScale = 0.85;      // default ≈85% (comfortable); range 0.70..1.40
  bool notif = true;

  /// Buttons / highlights — always a fixed colour.
  Color get accent => T.accents[accentKey] ?? T.green;

  /// Does the BACKGROUND shift its hue? (driven inside the Ambient widget itself,
  /// on its own AnimationController — NOT via a global timer, so it never causes
  /// a whole-tree rebuild / the jitter of a stepping timer.)
  bool get bgCycles => rainbowBg && anim > 0;

  bool get animOn => anim > 0;

  /// Motion time-scale: off = instant, reduced = 0.6×, normal/full = 1×.
  Duration dur(int ms) => Duration(milliseconds: (ms * (anim == 0 ? 0.0 : anim == 1 ? 0.6 : 1.0)).round());

  Future<void> init() async {
    _p = await SharedPreferences.getInstance();
    accentKey = _p.getString('accent') ?? 'green';
    if (accentKey == 'rainbow') accentKey = 'green';   // migrate the old cycling accent → static
    rainbowBg = _p.getBool('rainbowBg') ?? true;
    anim = _p.getInt('anim') ?? 3;
    textScale = _p.getDouble('textScale') ?? 0.85;
    notif = _p.getBool('notif') ?? true;
  }

  Future<void> setAccent(String k) async { accentKey = k; await _p.setString('accent', k); notifyListeners(); }
  Future<void> setRainbowBg(bool v) async { rainbowBg = v; await _p.setBool('rainbowBg', v); notifyListeners(); }
  Future<void> setAnim(int v) async { anim = v; await _p.setInt('anim', v); notifyListeners(); }
  Future<void> setTextScale(double v) async { textScale = v; await _p.setDouble('textScale', v); notifyListeners(); }
  Future<void> setNotif(bool v) async { notif = v; await _p.setBool('notif', v); notifyListeners(); }
}

/// A glass panel — a REAL native backdrop blur (always on) with a frosted
/// translucent fill so the shifting colourful background reads THROUGH it (not a
/// flat black surface): a light top-sheen gradient + a bright hairline highlight,
/// the "light catching the material" look.
class GlassPanel extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final double radius;
  final Color? glow;
  final double blur;
  const GlassPanel({super.key, required this.child,
    this.padding = const EdgeInsets.all(16), this.radius = 18, this.glow, this.blur = 16});

  @override
  Widget build(BuildContext context) {
    final r = BorderRadius.circular(radius);
    final body = Container(
      padding: padding,
      decoration: BoxDecoration(
        // frosted glass: a faint white sheen (top→bottom) over a hint of the dark
        // ink, so the blurred colour behind stays visible = clearly glass.
        gradient: const LinearGradient(
          begin: Alignment.topCenter, end: Alignment.bottomCenter,
          colors: [Color(0x2EFFFFFF), Color(0x14FFFFFF), Color(0x120C0C1A)],
          stops: [0, 0.55, 1],
        ),
        borderRadius: r,
        border: Border.all(color: const Color(0x38FFFFFF), width: 1),
        boxShadow: glow == null ? null : [
          BoxShadow(color: glow!.withOpacity(0.22), blurRadius: 40, spreadRadius: -8),
        ],
      ),
      child: child,
    );
    if (blur <= 0) return body;
    return ClipRRect(
      borderRadius: r,
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: body,
      ),
    );
  }
}

/// The launcher's shifting colorful background — several drifting blobs that
/// slowly move + fade. When [cycle] is on, the whole palette rotates its HUE on a
/// SEPARATE, slow controller so the colour loops smoothly and SEAMLESSLY (0°→360°
/// wraps with no jump) — decoupled from the blob motion. Isolated in a
/// RepaintBoundary so it never repaints the rest of the app.
class Ambient extends StatefulWidget {
  final Color accent;
  final bool cycle;
  const Ambient({super.key, this.accent = T.green, this.cycle = false});
  @override
  State<Ambient> createState() => _AmbientState();
}

class _AmbientState extends State<Ambient> with TickerProviderStateMixin {
  late final AnimationController _pos =
      AnimationController(vsync: this, duration: const Duration(seconds: 26))..repeat();
  late final AnimationController _hue =
      AnimationController(vsync: this, duration: const Duration(seconds: 46))..repeat();

  @override
  void dispose() { _pos.dispose(); _hue.dispose(); super.dispose(); }

  Color _shift(Color c, double deg) {
    final h = HSLColor.fromColor(c);
    return h.withHue((h.hue + deg) % 360).toColor();
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(child: IgnorePointer(child: LayoutBuilder(builder: (_, cs) {
      if (!Prefs.I.animOn) {
        final a = widget.accent;
        return _paint(cs, a, _shift(a, 60), 0);
      }
      return AnimatedBuilder(
        animation: Listenable.merge([_pos, _hue]),
        builder: (_, __) {
          final a = widget.cycle
              ? HSLColor.fromAHSL(1, (_hue.value * 360) % 360, 0.72, 0.58).toColor()
              : widget.accent;
          return _paint(cs, a, _shift(a, 60), _pos.value);
        },
      );
    })));
  }

  Widget _paint(BoxConstraints cs, Color a, Color b, double t) => Stack(children: [
        Positioned.fill(child: Container(color: T.canvas)),
        _blob(cs, a, 560, .46, .78 + .18 * math.sin(t * 2 * math.pi), .10 + .12 * math.cos(t * 2 * math.pi)),
        _blob(cs, b, 480, .38, .16 + .16 * math.cos(t * 2 * math.pi * .8), .84 + .10 * math.sin(t * 2 * math.pi * .8)),
        _blob(cs, a, 400, .34, .55 + .30 * math.sin(t * 2 * math.pi * 1.3 + 1), .5 + .30 * math.cos(t * 2 * math.pi * 1.3)),
        _blob(cs, b, 520, .24, .5 + .22 * math.cos(t * 2 * math.pi * .5), .5 + .18 * math.sin(t * 2 * math.pi * .5 + 2)),
      ]);

  Widget _blob(BoxConstraints cs, Color c, double size, double alpha, double fx, double fy) => Positioned(
        left: fx * cs.maxWidth - size / 2,
        top: fy * cs.maxHeight - size / 2,
        child: Container(width: size, height: size, decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(colors: [c.withOpacity(alpha), c.withOpacity(0)], stops: const [0, 1]),
        )),
      );
}
