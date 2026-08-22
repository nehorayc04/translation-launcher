import 'package:flutter/material.dart';
import '../fg_service.dart';
import '../icons.dart';
import '../theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool? _batteryOk;

  @override
  void initState() { super.initState(); _refreshBattery(); }
  Future<void> _refreshBattery() async {
    final ok = await FgService.isBatteryUnrestricted();
    if (mounted) setState(() => _batteryOk = ok);
  }

  @override
  Widget build(BuildContext context) {
    final p = Prefs.I;
    final acc = p.accent;
    return AnimatedBuilder(
      animation: p,
      builder: (_, __) => ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 88),
        children: [
          const Text('הגדרות', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: T.text)),
          const SizedBox(height: 14),

          _section('מראה', 'gear'),
          GlassPanel(radius: 16, child: Column(children: [
            _label('אנימציות'),
            _segmented(const ['מלאה', 'רגילה', 'מופחתת', 'כבויה'], 3 - p.anim,
                (i) => p.setAnim(3 - i), acc),
            _div(),
            _label('צבע מודגש'),
            const Align(alignment: Alignment.centerRight,
                child: Text('הצבע של הכפתורים וההדגשות', style: TextStyle(color: T.muted, fontSize: 11))),
            const SizedBox(height: 8),
            Wrap(spacing: 12, runSpacing: 12, children: [
              for (final e in T.accents.entries) _swatch(e.key, e.value, p.accentKey == e.key, () => p.setAccent(e.key)),
            ]),
            _div(),
            _toggleRow('צבעים מתחלפים ברקע', 'הרקע מחליף גוונים אוטומטית', p.rainbowBg,
                (v) => p.setRainbowBg(v), acc),
            _div(),
            _label('גודל טקסט · ${(p.textScale * 100).round()}%  (ברירת מחדל 85%)'),
            Slider(value: p.textScale.clamp(0.70, 1.40), min: 0.70, max: 1.40, divisions: 14,
                activeColor: acc,
                onChanged: (v) => p.setTextScale(double.parse(v.toStringAsFixed(2)))),
          ])),
          const SizedBox(height: 14),

          _section('רקע והרשאות', 'activity'),
          GlassPanel(radius: 16, child: Column(children: [
            _toggleRow('הודעה קבועה', 'תרגום בשעה האחרונה + קצב, בזמן אמת', p.notif,
                (v) => p.setNotif(v), acc),
            _div(),
            Row(children: [
              CcIcon('battery', size: 20, color: _batteryOk == true ? T.green : T.amber),
              const SizedBox(width: 10),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('אופטימיזציית סוללה', style: TextStyle(color: T.text, fontWeight: FontWeight.w600)),
                Text(_batteryOk == true ? 'ללא הגבלה - מצוין' : 'מומלץ להגדיר «ללא הגבלה» כדי שלא ייעצר ברקע',
                    style: TextStyle(color: _batteryOk == true ? T.green : T.muted, fontSize: 12)),
              ])),
              if (_batteryOk != true)
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: acc, foregroundColor: T.ink,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10))),
                  onPressed: () async { await FgService.requestBatteryUnrestricted(); await _refreshBattery(); },
                  child: const Text('הגדר', style: TextStyle(fontWeight: FontWeight.w800)),
                ),
            ]),
          ])),
        ],
      ),
    );
  }

  Widget _section(String t, String icon) => Padding(
    padding: const EdgeInsets.only(bottom: 8, right: 2),
    child: Row(children: [
      CcIcon(icon, size: 16, color: T.muted), const SizedBox(width: 8),
      Text(t, style: const TextStyle(color: T.muted, fontSize: 13, fontWeight: FontWeight.w700, letterSpacing: 0.4)),
    ]),
  );

  Widget _label(String t) => Padding(padding: const EdgeInsets.only(bottom: 4, top: 2),
      child: Align(alignment: Alignment.centerRight,
          child: Text(t, style: const TextStyle(color: T.text, fontWeight: FontWeight.w600))));

  Widget _div() => Container(height: 1, color: T.line, margin: const EdgeInsets.symmetric(vertical: 12));

  Widget _toggleRow(String t, String sub, bool v, ValueChanged<bool> on, Color acc) => Row(children: [
    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(t, style: const TextStyle(color: T.text, fontWeight: FontWeight.w600)),
      Text(sub, style: const TextStyle(color: T.muted, fontSize: 12)),
    ])),
    Switch(value: v, activeColor: acc, onChanged: on),
  ]);

  // launcher-style segmented control with a sliding highlight
  Widget _segmented(List<String> items, int index, ValueChanged<int> onTap, Color acc) {
    return LayoutBuilder(builder: (_, cs) {
      final w = cs.maxWidth / items.length;
      return Container(
        height: 40, padding: const EdgeInsets.all(3),
        decoration: BoxDecoration(color: Colors.white.withOpacity(0.05), borderRadius: BorderRadius.circular(12)),
        child: Stack(children: [
          AnimatedAlign(
            duration: Prefs.I.dur(280), curve: Curves.easeOutCubic,
            // RTL: item[0] is on the RIGHT, so negate the LTR alignment
            alignment: Alignment(items.length == 1 ? 0 : -((index / (items.length - 1)) * 2 - 1), 0),
            child: Container(width: w - 6, height: 34,
                decoration: BoxDecoration(color: acc.withOpacity(0.22), borderRadius: BorderRadius.circular(9),
                    border: Border.all(color: acc.withOpacity(0.5)))),
          ),
          Row(children: [
            for (var i = 0; i < items.length; i++)
              Expanded(child: GestureDetector(
                onTap: () => onTap(i), behavior: HitTestBehavior.opaque,
                child: Center(child: Text(items[i], style: TextStyle(
                    fontSize: 13, fontWeight: i == index ? FontWeight.w800 : FontWeight.w500,
                    color: i == index ? T.text : T.muted))),
              )),
          ]),
        ]),
      );
    });
  }

  Widget _swatch(String key, Color c, bool sel, VoidCallback on) => GestureDetector(
    onTap: on,
    child: AnimatedContainer(duration: Prefs.I.dur(200), width: 34, height: 34,
      decoration: BoxDecoration(shape: BoxShape.circle, color: c,
        border: Border.all(color: sel ? Colors.white : Colors.transparent, width: 3),
        boxShadow: sel ? [BoxShadow(color: c.withOpacity(0.6), blurRadius: 12)] : null),
      child: sel ? const CcIcon('check', size: 16, color: T.ink, stroke: 3) : null),
  );
}
