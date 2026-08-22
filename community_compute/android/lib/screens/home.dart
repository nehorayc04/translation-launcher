import 'package:flutter/material.dart';
import '../config.dart';
import '../engine.dart';
import '../icons.dart';
import '../theme.dart';
import '../widgets/stage_ring.dart';

class HomeScreen extends StatelessWidget {
  final Engine engine;
  final ValueChanged<bool> onToggle;
  final VoidCallback goToKeys;
  const HomeScreen({super.key, required this.engine, required this.onToggle, required this.goToKeys});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: engine,
      builder: (_, __) {
        final acc = Prefs.I.accent;
        final e = engine;
        final pending = e.st.outbox.length;                       // translated, not yet sent
        final offline = e.st.inbox.length + e.st.outbox.length;   // the offline safety buffer

        final (connLabel, connColor) = !e.on
            ? ('כבוי', T.muted)
            : e.online ? ('מחובר', T.green) : ('נאגר', T.amber);

        final (workLabel, workColor) = switch (true) {
          _ when !e.on => ('כבוי', T.muted),
          _ when e.phase == 'nokeys' => ('צריך מפתח', T.amber),
          _ when e.phase == 'provfail' => ('תקלת ספק', T.red),
          _ when e.phase == 'buffer' || !e.online => ('אוגר מקומית · אין קשר', T.amber),
          _ when e.arcRunning => ('פעיל · מעבד עבודה', acc),
          _ when e.queueEmpty => ('אין שורות בתור כרגע', T.muted),
          _ => ('בהמתנה · מתחבר לתור', T.muted),
        };

        return ListView(
          padding: const EdgeInsets.fromLTRB(14, 16, 14, 88),
          children: [
            Center(child: Text(Config.appName,
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: T.text))),
            const SizedBox(height: 2),
            const Center(child: Text('תרמו כוח-תרגום לקהילה · במכשיר שלכם, עם המפתחות שלכם',
                textAlign: TextAlign.center, style: TextStyle(color: T.muted, fontSize: 12.5))),
            const SizedBox(height: 8),

            // the live pipeline RING — status title, the ON/OFF toggle, the uptime
            // and the rotating explanation all live INSIDE the circle.
            StageRing(
              on: e.on, stage: e.ringStage, running: e.arcRunning,
              title: e.stageTitle, subtitle: e.stageSub,
              nKeys: e.nKeys, accent: acc, onToggle: onToggle, goToKeys: goToKeys,
            ),
            // uptime BELOW the ring (out of the centre) so the toggle can be big
            if (e.on && e.st.uptimeText().isNotEmpty) ...[
              const SizedBox(height: 8),
              Center(child: Text('פועל כבר ${e.st.uptimeText()}',
                  style: const TextStyle(color: T.muted, fontSize: 13))),
            ],
            const SizedBox(height: 18),

            // three headline stats
            Row(children: [
              Expanded(child: _statLive('שורות שתרמת', e.st.linesDone, 'check', acc)),
              const SizedBox(width: 10),
              // translated locally but not yet returned — climbs per line, resets
              // to 0 once the batch syncs (then those lines join "שורות שתרמת").
              Expanded(child: _statLive('ממתין לשליחה', pending, 'upload', T.cyan)),
              const SizedBox(width: 10),
              Expanded(child: _stat('קצב/דקה', e.st.ratePerMin().toStringAsFixed(1), 'activity', T.yellow)),
            ]),
            const SizedBox(height: 12),

            // full status details
            GlassPanel(radius: 18, glow: acc, child: Column(children: [
              _row('activity', 'מצב עבודה', workLabel, workColor),
              _div(),
              _row('globe', 'חיבור לשרת', connLabel, connColor),
              _div(),
              _row('shield', 'מפתחות פעילים', '${e.nKeys}/3', e.nKeys > 0 ? T.green : T.amber),
              _div(),
              _row('globe', 'כתובת ה-IP שלכם', e.st.ip.isEmpty ? '…' : e.st.ip, T.text,
                  hint: 'מוצגת רק לכם - לא נשלחת לשרת'),
              _div(),
              _row('upload', 'תורגמו בשעה האחרונה', '${e.st.linesLastHour()}', T.text),
              _div(),
              _row('download', 'מאגר לא-מקוון', '$offline',
                  offline > 0 ? T.cyan : T.muted,
                  hint: 'שורות שממתינות במכשיר · 0 = הכול מסונכרן'),
            ])),

            if (e.nKeys == 0) ...[
              const SizedBox(height: 12),
              GlassPanel(radius: 16, child: Row(children: [
                const CcIcon('key', size: 20, color: T.amber),
                const SizedBox(width: 10),
                const Expanded(child: Text('הוסיפו מפתח מלפחות ספק אחד בעמוד «מפתחות» כדי להפעיל.',
                    style: TextStyle(color: T.muted, fontSize: 13))),
                TextButton(onPressed: goToKeys, child: const Text('למפתחות')),
              ])),
            ],
          ],
        );
      },
    );
  }

  Widget _stat(String cap, String val, String icon, Color c) =>
      _statBox(cap, icon, c, Text(val, maxLines: 1,
          style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: c)));

  // like _stat, but the number COUNTS UP smoothly toward [value] — so a batch of
  // 50 committed lines is shown ticking up one-by-one, not jumping all at once.
  Widget _statLive(String cap, int value, String icon, Color c) => _statBox(cap, icon, c,
        TweenAnimationBuilder<int>(
          tween: IntTween(begin: 0, end: value),
          duration: Prefs.I.dur(1400),
          curve: Curves.easeOut,
          builder: (_, v, __) => Text(_fmt(v), maxLines: 1,
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: c)),
        ));

  Widget _statBox(String cap, String icon, Color c, Widget value) => GlassPanel(
        radius: 16, padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
        child: Column(children: [
          CcIcon(icon, size: 18, color: c),
          const SizedBox(height: 8),
          // scale-down (never ellipsis) so a big number / larger text size still fits
          FittedBox(fit: BoxFit.scaleDown, child: value),
          const SizedBox(height: 2),
          Text(cap, textAlign: TextAlign.center, softWrap: true,
              style: const TextStyle(fontSize: 11, color: T.muted)),
        ]),
      );

  Widget _row(String icon, String label, String value, Color valColor, {String? hint}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 11),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          CcIcon(icon, size: 18, color: T.muted),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, softWrap: true,
                style: const TextStyle(color: T.text, fontSize: 14, fontWeight: FontWeight.w600)),
            if (hint != null) Text(hint, softWrap: true,
                style: const TextStyle(color: T.muted, fontSize: 11)),
          ])),
          const SizedBox(width: 8),
          // value WRAPS (up to 2 lines) instead of ever showing "…"
          Flexible(child: Text(value, textAlign: TextAlign.left, softWrap: true, maxLines: 2,
              style: TextStyle(color: valColor, fontSize: 14, fontWeight: FontWeight.w700))),
        ]),
      );

  Widget _div() => Container(height: 1, color: T.line);

  String _fmt(int n) => n.toString().replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');
}
