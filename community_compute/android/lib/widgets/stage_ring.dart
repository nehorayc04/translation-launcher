// The live pipeline as a CIRCLE (ring), divided into 4 stages — RTL, the top of
// the ring reads right→left: שליפה → תרגום/ביקורת → בדיקה → שליחה. A light WAVE
// flows continuously AROUND the whole ring (like the website's progress bar),
// passing UNDER each node icon (a dark disc masks it, so it re-emerges). The
// active stage's arc is brighter and its node glows.
//
// Everything — the phase title, the rotating explanation, the big ON/OFF toggle
// and the uptime — lives INSIDE the ring, packed with a FittedBox so nothing can
// ever overlap regardless of text size or wording length.
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../icons.dart';
import '../theme.dart';
import 'big_toggle.dart';

const _nodeU = [0.0, 0.25, 0.5, 0.75];               // travel order, counter-clockwise
const _nodeIcons = ['download', 'activity', 'shield', 'upload'];
const _segHalf = 0.093;

Color _col(int k, Color accent) => [T.cyan, accent, T.purple, T.green][k];

class StageRing extends StatefulWidget {
  final bool on;
  final int stage;          // 0..3 active stage · -1 = idle/off
  final bool running;
  final String title, subtitle;
  final int nKeys;
  final Color accent;
  final ValueChanged<bool> onToggle;
  final VoidCallback goToKeys;
  const StageRing({super.key, required this.on, required this.stage, required this.running,
    required this.title, required this.subtitle, required this.nKeys,
    required this.accent, required this.onToggle, required this.goToKeys});

  @override
  State<StageRing> createState() => _StageRingState();
}

class _StageRingState extends State<StageRing> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 2600))..repeat();

  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final wave = widget.running && Prefs.I.animOn;
    return Center(child: LayoutBuilder(builder: (_, cs) {
      // fill the available width (bigger on phones), but cap it so on a large
      // display (tablet) the ring stays a comfortable STANDARD size, centred.
      final d = math.min(cs.maxWidth, 420.0);
      final r = d / 2 - 22;
      final inset = d * 0.21;
      return SizedBox(width: d, height: d, child: Stack(clipBehavior: Clip.none, children: [
        // the ring + travelling wave
        Positioned.fill(child: RepaintBoundary(child: AnimatedBuilder(
          animation: wave ? _c : const AlwaysStoppedAnimation(0.0),
          builder: (_, __) => CustomPaint(
              painter: _RingPainter(widget.stage, wave ? _c.value : -1, widget.accent)),
        ))),
        // node icons (drawn OVER the ring/wave)
        for (var k = 0; k < 4; k++) _node(k, d / 2, r),
        // centre content — title · toggle · uptime · explanation, never overlapping
        Positioned.fill(child: Padding(
          padding: EdgeInsets.all(inset),
          child: Center(child: FittedBox(
            fit: BoxFit.scaleDown,
            child: SizedBox(width: d - 2 * inset, child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(widget.title, textAlign: TextAlign.center, maxLines: 2, softWrap: true,
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900,
                        color: T.text, height: 1.1)),
                const SizedBox(height: 8),
                BigToggle(value: widget.on, scale: 0.98, onChanged: (v) {
                  if (v && widget.nKeys == 0) { widget.goToKeys(); return; }
                  widget.onToggle(v);
                }),
                const SizedBox(height: 6),
                Text(widget.subtitle, textAlign: TextAlign.center, maxLines: 2, softWrap: true,
                    style: const TextStyle(fontSize: 13, color: T.muted, height: 1.25)),
              ],
            )),
          )),
        )),
      ]));
    }));
  }

  Widget _node(int k, double c, double r) {
    final t = -_nodeU[k] * 2 * math.pi;
    final x = c + r * math.cos(t), y = c + r * math.sin(t);
    final on = widget.stage == k, done = widget.stage >= 0 && k < widget.stage;
    final col = _col(k, widget.accent);
    return Positioned(left: x - 15, top: y - 15, child: SizedBox(width: 30, height: 30,
      child: Center(child: done
          ? CcIcon('check', size: 15, color: col, stroke: 2.6)
          : CcIcon(_nodeIcons[k], size: 15,
              color: on ? Colors.white : T.muted, stroke: on ? 2.4 : 2)),
    ));
  }
}

class _RingPainter extends CustomPainter {
  final int active;   // 0..3 · -1 none
  final double t;     // wave phase 0..1 · -1 = none
  final Color accent;
  _RingPainter(this.active, this.t, this.accent);

  double _circDist(double a, double b) { final d = (a - b).abs(); return math.min(d, 1 - d); }

  // brightness of the travelling wave at position [u] (0..1 around the ring).
  double _wave(double u, double c1, double c2) {
    double b = 0;
    for (final c in [c1, c2]) {
      final d = _circDist(u, c);
      b = math.max(b, math.exp(-(d * d) / 0.0016));
    }
    return b;
  }

  int? _segAt(double u) {
    for (var k = 0; k < 4; k++) { if (_circDist(u, _nodeU[k]) <= _segHalf) return k; }
    return null;
  }

  @override
  void paint(Canvas cv, Size size) {
    final cx = size.width / 2, cy = size.height / 2, r = size.width / 2 - 22;
    final rect = Rect.fromCircle(center: Offset(cx, cy), radius: r);
    final running = t >= 0;
    final c1 = t, c2 = (t + 0.5) % 1.0;   // two bands half a cycle apart
    const n = 108;
    final da = (2 * math.pi / n) * 1.8;   // overlap → one continuous ribbon

    for (var i = 0; i < n; i++) {
      final u = (i + 0.5) / n;
      final k = _segAt(u);
      if (k == null) continue;            // gap between stages
      final a = -u * 2 * math.pi;
      final start = a - da / 2;
      final col = _col(k, accent);
      final on = k == active, done = active >= 0 && k < active;
      cv.drawArc(rect, start, da, false, Paint()
        ..style = PaintingStyle.stroke..strokeWidth = 11..strokeCap = StrokeCap.round
        ..color = col.withOpacity(on ? 0.9 : done ? 0.5 : 0.15));
      if (running) {
        final b = _wave(u, c1, c2);
        if (b > 0.04) {
          final white = Color.lerp(col, Colors.white, 0.75)!;
          cv.drawArc(rect, start, da, false, Paint()      // soft glow
            ..style = PaintingStyle.stroke..strokeWidth = 11 + 8 * b..strokeCap = StrokeCap.round
            ..color = col.withOpacity(0.5 * b)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6));
          cv.drawArc(rect, start, da, false, Paint()      // bright core
            ..style = PaintingStyle.stroke..strokeWidth = 11..strokeCap = StrokeCap.round
            ..color = white.withOpacity((0.35 + 0.6 * b).clamp(0.0, 1.0)));
        }
      }
    }

    // nodes: dark disc masks the wave inside + coloured ring + active glow
    for (var k = 0; k < 4; k++) {
      final a = -_nodeU[k] * 2 * math.pi;
      final p = Offset(cx + r * math.cos(a), cy + r * math.sin(a));
      final on = k == active, done = active >= 0 && k < active;
      final col = _col(k, accent);
      final glow = (on && running) ? _wave(_nodeU[k], c1, c2) : 0.0;
      if (on) {
        cv.drawCircle(p, 19 + 4 * glow, Paint()
          ..color = col.withOpacity(0.28 + 0.34 * glow)
          ..maskFilter = MaskFilter.blur(BlurStyle.normal, 9 + 5 * glow));
      }
      cv.drawCircle(p, 15, Paint()..color = const Color(0xFF0B0B16));
      cv.drawCircle(p, 15, Paint()
        ..style = PaintingStyle.stroke..strokeWidth = on ? 3.0 : 2.2
        ..color = (on || done) ? col : col.withOpacity(0.30));
    }
  }

  @override
  bool shouldRepaint(_RingPainter o) => o.active != active || o.t != t || o.accent != accent;
}
