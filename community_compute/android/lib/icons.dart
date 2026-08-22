// Launcher-style line icons — Lucide-ish 24×24 stroke glyphs drawn with a
// CustomPainter. No emoji, no external dependency; `currentColor` via [color].
import 'dart:math' as math;
import 'package:flutter/material.dart';

class CcIcon extends StatelessWidget {
  final String name;
  final double size;
  final Color color;
  final double stroke;
  const CcIcon(this.name, {super.key, this.size = 22, this.color = Colors.white, this.stroke = 2});

  @override
  Widget build(BuildContext context) =>
      SizedBox(width: size, height: size, child: CustomPaint(painter: _IconPainter(name, color, stroke)));
}

class _IconPainter extends CustomPainter {
  final String name;
  final Color color;
  final double stroke;
  _IconPainter(this.name, this.color, this.stroke);

  @override
  void paint(Canvas cv, Size size) {
    final s = size.width / 24.0;
    final p = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    Offset o(double x, double y) => Offset(x * s, y * s);
    void line(double x1, double y1, double x2, double y2) => cv.drawLine(o(x1, y1), o(x2, y2), p);
    void circle(double x, double y, double r) => cv.drawCircle(o(x, y), r * s, p);
    void arc(double x, double y, double r, double a0, double sweep) =>
        cv.drawArc(Rect.fromCircle(center: o(x, y), radius: r * s), a0, sweep, false, p);
    void rrect(double x, double y, double w, double h, double r) => cv.drawRRect(
        RRect.fromRectAndRadius(Rect.fromLTWH(x * s, y * s, w * s, h * s), Radius.circular(r * s)), p);
    void poly(List<double> pts) {
      final path = Path()..moveTo(pts[0] * s, pts[1] * s);
      for (var i = 2; i < pts.length; i += 2) { path.lineTo(pts[i] * s, pts[i + 1] * s); }
      cv.drawPath(path, p);
    }

    switch (name) {
      case 'power':
        arc(12, 12.5, 6.5, math.pi * 0.62, math.pi * 1.76);
        line(12, 3.5, 12, 12);
      case 'key':
        circle(8, 15, 4);
        line(10.8, 12.2, 20, 3);
        line(17, 6, 19, 8);
        line(14.5, 8.5, 16.5, 10.5);
      case 'gear':
        circle(12, 12, 3);
        for (var i = 0; i < 8; i++) {
          final a = i * math.pi / 4;
          line(12 + 5 * math.cos(a), 12 + 5 * math.sin(a), 12 + 8 * math.cos(a), 12 + 8 * math.sin(a));
        }
      case 'info':
        circle(12, 12, 9);
        line(12, 11, 12, 16);
        cv.drawCircle(o(12, 8), stroke * 0.75, Paint()..color = color..style = PaintingStyle.fill);
      case 'activity': // live pulse / rate
        poly([3, 12, 8, 12, 10.5, 5, 13.5, 19, 16, 12, 21, 12]);
      case 'download': // fetch lines
        line(12, 3, 12, 15);
        poly([7.5, 10.5, 12, 15, 16.5, 10.5]);
        poly([4, 20, 20, 20]);
      case 'upload': // send lines back
        line(12, 21, 12, 9);
        poly([7.5, 13.5, 12, 9, 16.5, 13.5]);
        poly([4, 4, 20, 4]);
      case 'globe': // IP
        circle(12, 12, 9);
        line(3, 12, 21, 12);
        cv.drawOval(Rect.fromCenter(center: o(12, 12), width: 10 * s, height: 18 * s), p);
      case 'shield': // key status
        poly([12, 3, 20, 6, 20, 12, 12, 21, 4, 12, 4, 6, 12, 3]);
        poly([9, 12, 11.2, 14.5, 15.5, 9.5]);
      case 'check':
        poly([5, 12.5, 10, 17.5, 19.5, 7]);
      case 'copy':
        rrect(9, 9, 11, 11, 2.5);
        poly([5.5, 15, 4.5, 15, 4, 14.5, 4, 4.5, 4.5, 4, 14.5, 4, 15, 4.5, 15, 5.5]);
      case 'external':
        poly([14, 4, 20, 4, 20, 10]);
        line(20, 4, 12.5, 11.5);
        poly([18, 13, 18, 19, 5, 19, 5, 6, 11, 6]);
      case 'chevron-down':
        poly([6, 9.5, 12, 15.5, 18, 9.5]);
      case 'chevron-up':
        poly([6, 14.5, 12, 8.5, 18, 14.5]);
      case 'close':
        line(6, 6, 18, 18); line(18, 6, 6, 18);
      case 'minus':
        line(5, 12, 19, 12);
      case 'plus':
        line(12, 5, 12, 19); line(5, 12, 19, 12);
      case 'battery': // battery-unrestricted prompt
        rrect(3, 8, 16, 8, 2.5);
        line(20.5, 11, 20.5, 13);
        poly([11, 9.5, 8.5, 12.5, 11.5, 12.5, 9, 15.5]);
      case 'dot':
        cv.drawCircle(o(12, 12), 4 * s, Paint()..color = color..style = PaintingStyle.fill);
      case 'eye':
        cv.drawPath(Path()
          ..moveTo(2 * s, 12 * s)
          ..cubicTo(5 * s, 6 * s, 19 * s, 6 * s, 22 * s, 12 * s)
          ..cubicTo(19 * s, 18 * s, 5 * s, 18 * s, 2 * s, 12 * s), p);
        circle(12, 12, 3.2);
      case 'eye-off':
        cv.drawPath(Path()
          ..moveTo(3 * s, 12.5 * s)
          ..cubicTo(6 * s, 7.5 * s, 12 * s, 6 * s, 15 * s, 6.8 * s), p);
        cv.drawPath(Path()
          ..moveTo(21 * s, 12.5 * s)
          ..cubicTo(19.5 * s, 15 * s, 17 * s, 16.6 * s, 14 * s, 17.2 * s), p);
        arc(12, 12, 3.2, math.pi * 1.15, math.pi * 1.1);
        line(4, 4, 20, 20);
      case 'chevron-left':
        poly([14.5, 6, 8.5, 12, 14.5, 18]);
      case 'chevron-right':
        poly([9.5, 6, 15.5, 12, 9.5, 18]);
      case 'refresh': // circular-arrow: ~11/12 circle + a solid arrowhead at 2 o'clock
        {
          arc(12, 12, 7, math.pi * 5 / 3, math.pi * 11 / 6);
          final rt = o(17.75, 7.24), rb = o(16.7, 3.86), rc = o(14.3, 8.02);
          cv.drawPath(
              Path()..moveTo(rt.dx, rt.dy)..lineTo(rb.dx, rb.dy)..lineTo(rc.dx, rc.dy)..close(),
              Paint()..color = color..style = PaintingStyle.fill);
        }
      case 'home':
        poly([4, 11, 12, 4, 20, 11]);
        poly([6, 10, 6, 20, 18, 20, 18, 10]);
      default:
        circle(12, 12, 8);
    }
  }

  @override
  bool shouldRepaint(_IconPainter o) => o.name != name || o.color != color || o.stroke != stroke;
}
