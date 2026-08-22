// The big central ON/OFF switch — a NARROW glass pill + glowing neon thumb,
// with פעיל/כבוי centered BELOW it. RTL: OFF on the right, slides LEFT to ON.
// Accent-aware (uses the user's chosen accent) + spring motion.
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme.dart';

class BigToggle extends StatefulWidget {
  final bool value;
  final ValueChanged<bool> onChanged;
  final double scale;   // 1.0 = full size; <1 to nest it (e.g. inside the ring)
  const BigToggle({super.key, required this.value, required this.onChanged, this.scale = 1.0});
  @override
  State<BigToggle> createState() => _BigToggleState();
}

class _BigToggleState extends State<BigToggle> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: Prefs.I.dur(440), value: widget.value ? 1 : 0);
  bool _pressed = false;

  @override
  void didUpdateWidget(BigToggle old) {
    super.didUpdateWidget(old);
    if (widget.value != old.value) {
      if (!Prefs.I.animOn) { _c.value = widget.value ? 1 : 0; }
      else { _c.animateTo(widget.value ? 1 : 0, curve: Curves.easeOutBack, duration: Prefs.I.dur(440)); }
    }
  }

  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final acc = Prefs.I.accent;
    final s = widget.scale;
    return Column(mainAxisSize: MainAxisSize.min, children: [
      GestureDetector(
        onTapDown: (_) => setState(() => _pressed = true),
        onTapCancel: () => setState(() => _pressed = false),
        onTapUp: (_) => setState(() => _pressed = false),
        onTap: () => widget.onChanged(!widget.value),
        child: AnimatedScale(
          scale: _pressed ? 0.97 : 1.0, duration: const Duration(milliseconds: 110),
          child: AnimatedBuilder(
            animation: _c,
            builder: (_, __) => CustomPaint(
              size: Size(196 * s, 96 * s),
              painter: _TogglePainter(_c.value, acc),
            ),
          ),
        ),
      ),
      SizedBox(height: 6 * s),
      AnimatedBuilder(
        animation: _c,
        builder: (_, __) {
          final on = _c.value > 0.5;
          return Text(on ? 'פעיל' : 'כבוי',
              style: TextStyle(fontFamily: 'Heebo', fontWeight: FontWeight.w900, fontSize: 22 * s,
                  letterSpacing: 0.5, color: on ? acc : T.muted));
        },
      ),
    ]);
  }
}

class _TogglePainter extends CustomPainter {
  final double pos; // 0=off .. 1=on
  final Color acc;
  _TogglePainter(this.pos, this.acc);

  @override
  void paint(Canvas cv, Size size) {
    final w = size.width, h = size.height;
    final on = pos > 0.5;
    final col = Color.lerp(const Color(0xFF5B6480), acc, pos)!;
    final track = Rect.fromLTWH(4, 20, w - 8, h - 40);
    final r = track.height / 2;

    if (pos > 0.02) {
      for (final g in [[18.0, 10], [10.0, 16], [4.0, 26]]) {
        cv.drawRRect(RRect.fromRectAndRadius(track.inflate(g[0] as double), Radius.circular(r + (g[0] as double))),
            Paint()..color = acc.withOpacity((g[1] as int) * pos / 255));
      }
    }
    final trackRR = RRect.fromRectAndRadius(track, Radius.circular(r));
    cv.drawRRect(trackRR, Paint()..color = const Color(0xDC0C0C1A));
    cv.drawRRect(trackRR, Paint()..color = acc.withOpacity(0.22 * pos));
    cv.drawRRect(trackRR, Paint()
      ..style = PaintingStyle.stroke..strokeWidth = 1..color = Colors.white.withOpacity(0.10));

    final d = track.height - 10;
    final xOff = track.right - d - 5;
    final xOn = track.left + 5;
    final x = xOff + (xOn - xOff) * pos;
    final thumb = Rect.fromLTWH(x, track.top + 5, d, d);
    for (final g in [[9.0, (70 * pos + 10)], [4.0, (90 * pos + 20)]]) {
      cv.drawOval(thumb.inflate(g[0] as double),
          Paint()..color = col.withOpacity(((g[1] as double).clamp(0, 255)) / 255));
    }
    cv.drawOval(thumb, Paint()..shader = LinearGradient(
        begin: Alignment.topCenter, end: Alignment.bottomCenter,
        colors: [Colors.white, col]).createShader(thumb));
    // power glyph
    final c = thumb.center, rr = d * 0.26;
    final gp = Paint()..style = PaintingStyle.stroke..strokeWidth = 3
      ..strokeCap = StrokeCap.round..color = on ? col : const Color(0xFF3A3F57);
    cv.drawArc(Rect.fromCircle(center: c.translate(0, 1), radius: rr),
        math.pi * 0.16, math.pi * 1.34, false, gp);
    cv.drawLine(Offset(c.dx, c.dy - rr - 2), Offset(c.dx, c.dy + 1), gp);
  }

  @override
  bool shouldRepaint(_TogglePainter o) => o.pos != pos || o.acc != acc;
}
