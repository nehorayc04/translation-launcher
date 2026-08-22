// The live pipeline arc — shows EXACTLY what the worker is doing now, by stage,
// RTL (first stage on the right): משיכה → תרגום/ביקורת → שליחה.
//
// The arc is a clean TOP arch; the three nodes sit ON it (the arc flows THROUGH
// each node — a dark disc masks the line inside so the icon stays clear, and the
// coloured ring reads as a continuation of the arc). The ACTIVE segment carries a
// flowing WAVE of light (not a single dot) that passes through the active node.
// Title + subtitle sit BELOW the arch (never overlapping) and wrap freely.
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../icons.dart';
import '../theme.dart';

const _nodeIcons = ['download', 'activity', 'upload']; // fetch(right) · translate(top) · send(left)
const _nodeDeg   = [330.0, 270.0, 210.0];
const _segStart  = [300.0, 240.0, 180.0]; // each sweeps +60°
const _arcH      = 150.0;

Color _hue(int i, Color accent) => [T.cyan, accent, T.purple][i];
double _cy() => _arcH - 22;
double _rad(double w) => math.min(w / 2 - 22, _arcH - 34);

class StageArc extends StatefulWidget {
  /// 0 = fetch, 1 = translate/review, 2 = send; -1 = idle/off.
  final int segment;
  final String title;
  final String subtitle;
  final bool running;
  final Color accent;
  const StageArc({super.key, required this.segment, required this.title,
    required this.subtitle, required this.running, required this.accent});

  @override
  State<StageArc> createState() => _StageArcState();
}

class _StageArcState extends State<StageArc> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 2200))..repeat();

  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final anim = Prefs.I.animOn;
    return Column(mainAxisSize: MainAxisSize.min, children: [
      SizedBox(height: _arcH, child: LayoutBuilder(builder: (_, cs) {
        final w = cs.maxWidth, cx = w / 2, cy = _cy(), r = _rad(w);
        return Stack(clipBehavior: Clip.none, children: [
          Positioned.fill(child: RepaintBoundary(child: AnimatedBuilder(
            animation: anim ? _c : const AlwaysStoppedAnimation(0.0),
            builder: (_, __) => CustomPaint(
              painter: _ArcPainter(widget.segment,
                  widget.running && anim ? _c.value : -1, widget.accent),
            ),
          ))),
          for (var i = 0; i < 3; i++) _nodeIcon(i, cx, cy, r),
        ]);
      })),
      const SizedBox(height: 10),
      Text(widget.title, textAlign: TextAlign.center, softWrap: true,
          style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: T.text)),
      const SizedBox(height: 4),
      ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 300),
        child: Text(widget.subtitle, textAlign: TextAlign.center, softWrap: true,
            style: const TextStyle(fontSize: 12.5, color: T.muted, height: 1.3)),
      ),
    ]);
  }

  // the bright glyph that sits centered in each node (drawn OVER the disc/ring).
  Widget _nodeIcon(int i, double cx, double cy, double r) {
    final a = _nodeDeg[i] * math.pi / 180;
    final active = widget.segment == i;
    final done   = widget.segment > i && widget.segment >= 0;
    final col    = _hue(i, widget.accent);
    final x = cx + r * math.cos(a), y = cy + r * math.sin(a);
    return Positioned(left: x - 16, top: y - 16, child: SizedBox(width: 32, height: 32,
      child: Center(child: done
          ? CcIcon('check', size: 17, color: col, stroke: 2.6)
          : CcIcon(_nodeIcons[i], size: 17,
              color: active ? Colors.white : T.muted, stroke: active ? 2.4 : 2)),
    ));
  }
}

class _ArcPainter extends CustomPainter {
  final int segment;
  final double t;      // 0..1 wave phase, -1 = none
  final Color accent;
  _ArcPainter(this.segment, this.t, this.accent);

  Offset _pt(double cx, double cy, double r, double deg) {
    final a = deg * math.pi / 180;
    return Offset(cx + r * math.cos(a), cy + r * math.sin(a));
  }

  @override
  void paint(Canvas cv, Size size) {
    final cx = size.width / 2, cy = _cy(), r = _rad(size.width);
    final rect = Rect.fromCircle(center: Offset(cx, cy), radius: r);

    // 1) base arc — three coloured segments (continuous, rounded)
    for (var i = 0; i < 3; i++) {
      final col = _hue(i, accent);
      final active = segment == i, done = segment > i && segment >= 0;
      final a0 = _segStart[i] * math.pi / 180, sweep = 60 * math.pi / 180;
      cv.drawArc(rect, a0, sweep, false, Paint()
        ..style = PaintingStyle.stroke..strokeWidth = 7..strokeCap = StrokeCap.round
        ..color = (active || done) ? col.withOpacity(done ? 0.5 : 0.85) : col.withOpacity(0.14));
    }

    // 2) flowing WAVE of light along the ACTIVE segment (passes through its node)
    if (segment >= 0 && t >= 0) {
      final col = _hue(segment, accent);
      final a0 = _segStart[segment], span = 60.0;
      // two soft pulses sweeping the segment, offset by half a cycle
      final centers = [(t * 1.35) % 1.0, (t * 1.35 + 0.5) % 1.0];
      const samples = 22;
      for (var s = 0; s <= samples; s++) {
        final f = s / samples;
        double bright = 0;
        for (final c in centers) {
          final d = (f - c).abs();
          bright += math.exp(-(d * d) / 0.010);      // gaussian bump
        }
        if (bright < 0.05) continue;
        bright = bright.clamp(0.0, 1.0);
        final p = _pt(cx, cy, r, a0 + span * f);
        cv.drawCircle(p, 3.4 + 2.2 * bright,
            Paint()..color = col.withOpacity(0.5 * bright)
              ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5));
        cv.drawCircle(p, 1.8 + 1.2 * bright,
            Paint()..color = Colors.white.withOpacity(0.85 * bright));
      }
    }

    // 3) nodes OVER the arc: dark disc (masks the line inside) + coloured ring
    for (var i = 0; i < 3; i++) {
      final col = _hue(i, accent);
      final active = segment == i, done = segment > i && segment >= 0;
      final p = _pt(cx, cy, r, _nodeDeg[i]);

      // wave proximity → the active node's ring pulses as the light passes through
      double glow = 0;
      if (active && t >= 0) {
        final nf = (_nodeDeg[i] - _segStart[i]) / 60.0; // node's fraction along its seg (=0.5)
        for (final c in [(t * 1.35) % 1.0, (t * 1.35 + 0.5) % 1.0]) {
          final d = (nf - c).abs();
          glow = math.max(glow, math.exp(-(d * d) / 0.012));
        }
      }

      if (active) {
        cv.drawCircle(p, 20 + 4 * glow, Paint()
          ..color = col.withOpacity(0.30 + 0.35 * glow)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, 10 + 5 * glow));
      }
      // solid dark disc so the arc line + glow never cross the icon (no "bar")
      cv.drawCircle(p, 15, Paint()..color = const Color(0xFF0B0B16));
      // ring = a continuation of the arc, same width, entering/leaving both sides
      cv.drawCircle(p, 15, Paint()
        ..style = PaintingStyle.stroke..strokeWidth = active ? 3.2 : 2.2
        ..color = (active || done) ? col : col.withOpacity(0.30));
    }
  }

  @override
  bool shouldRepaint(_ArcPainter o) => o.segment != segment || o.t != t || o.accent != accent;
}
