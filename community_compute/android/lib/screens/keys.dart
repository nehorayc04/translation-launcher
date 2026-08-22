import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import '../config.dart';
import '../icons.dart';
import '../keystore.dart';
import '../state.dart';
import '../theme.dart';

const _ids = ['groq', 'sambanova', 'nim'];

// step-by-step Hebrew guide per provider (easy, for every user level)
const _guides = <String, Map<String, dynamic>>{
  'groq': {
    'url': 'https://console.groq.com/keys',
    'note': 'Groq הוא המהיר והיציב ביותר - מומלץ בחום להתחיל ממנו.',
    'steps': [
      'פתחו את console.groq.com והתחברו (אפשר עם Google או GitHub - חינם).',
      'בתפריט בצד לחצו על «API Keys».',
      'לחצו «Create API Key», תנו שם כלשהו ואשרו.',
      'העתיקו את המפתח שמופיע (מתחיל ב-gsk_) - הוא מוצג פעם אחת בלבד!',
      'הדביקו אותו בשדה כאן למטה ולחצו שמירה.',
    ],
  },
  'sambanova': {
    'url': 'https://cloud.sambanova.ai',
    'note': 'דרגה חינמית לפיתוח - מהיר ואיכותי.',
    'steps': [
      'פתחו cloud.sambanova.ai והירשמו או התחברו (חינם).',
      'בתפריט לחצו על «APIs» / «API Keys».',
      'לחצו «Generate» / «Create» כדי ליצור מפתח חדש.',
      'העתיקו את המפתח שנוצר.',
      'הדביקו אותו בשדה כאן למטה ולחצו שמירה.',
    ],
  },
  'nim': {
    'url': 'https://build.nvidia.com',
    'note': 'NIM החינמי איטי ועמוס לעיתים - עדיף להוסיף גם Groq לצידו.',
    // אין צורך לבחור מודל - המפתח נוצר מהתפריט של חשבון המשתמש.
    'steps': [
      'פתחו build.nvidia.com והירשמו או התחברו עם חשבון NVIDIA (חינם).',
      'לחצו על סמל המשתמש בפינת האתר כדי לפתוח את התפריט הנפתח.',
      'בחרו בתפריט את האפשרות של מפתחות API («API Keys»).',
      'לחצו על יצירת מפתח חדש והעתיקו אותו (מתחיל ב-nvapi-).',
      'הדביקו אותו בשדה כאן למטה ולחצו שמירה.',
    ],
  },
};

class KeysScreen extends StatefulWidget {
  final AppState st;
  final VoidCallback onSaved;
  const KeysScreen({super.key, required this.st, required this.onSaved});
  @override
  State<KeysScreen> createState() => _KeysScreenState();
}

class _KeysScreenState extends State<KeysScreen> {
  final _edits = <String, TextEditingController>{};
  final _show = <String, bool>{};   // per-field: reveal the key (eye toggle)
  late final _proxy = TextEditingController(text: widget.st.proxy);
  late bool _consent = widget.st.consent;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    final keys = await KeyStore.load();
    for (final p in Config.providers) {
      _edits[p[1]] = TextEditingController(text: keys[p[1]] ?? '');
    }
    setState(() {});
  }

  @override
  void dispose() {
    for (final c in _edits.values) { c.dispose(); }
    _proxy.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_consent) return;
    await KeyStore.save({for (final e in _edits.entries) e.key: e.value.text});
    await widget.st.setConsent(_consent);
    await widget.st.setProxy(_proxy.text.trim());
    widget.onSaved();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('המפתחות נשמרו מוצפנים במכשיר.')));
    }
  }

  Future<void> _open(String url) async {
    final u = Uri.parse(url);
    if (await canLaunchUrl(u)) { await launchUrl(u, mode: LaunchMode.externalApplication); }
  }

  // ---- import / export (one block, or a single line, easy to save/paste) -----
  String _exportText() {
    final b = StringBuffer();
    for (final id in _ids) {
      final v = (_edits[id]?.text ?? '').trim();
      if (v.isNotEmpty) b.writeln('$id=$v');
    }
    return b.toString().trim();
  }

  String? _detect(String v) {
    if (v.startsWith('gsk_')) return 'groq';
    if (v.startsWith('nvapi-')) return 'nim';
    if (!v.contains(' ') && v.length >= 20) return 'sambanova'; // no fixed prefix
    return null;
  }

  Map<String, String> _parseKeys(String text) {
    final out = <String, String>{};
    final t = text.trim();
    if (t.isEmpty) return out;
    // 1) JSON object {"groq":"...", ...}
    try {
      final j = jsonDecode(t);
      if (j is Map) {
        for (final e in j.entries) {
          final id = e.key.toString().toLowerCase().trim();
          if (_ids.contains(id) && e.value is String && (e.value as String).trim().isNotEmpty) {
            out[id] = (e.value as String).trim();
          }
        }
        if (out.isNotEmpty) return out;
      }
    } catch (_) {}
    // 2) line-based `id=value` / `id: value`, else a bare token auto-detected
    for (final raw in const LineSplitter().convert(t)) {
      final line = raw.trim();
      if (line.isEmpty) continue;
      final m = RegExp(r'^([A-Za-z]+)\s*[:=]\s*(.+)$').firstMatch(line);
      if (m != null) {
        final id = m.group(1)!.toLowerCase();
        if (_ids.contains(id)) { out[id] = m.group(2)!.trim(); continue; }
      }
      final id = _detect(line);
      if (id != null) out[id] = line;
    }
    return out;
  }

  Future<void> _exportDialog() async {
    final text = _exportText();
    if (text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('אין מפתחות לייצוא.')));
      return;
    }
    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    showDialog(context: context, builder: (ctx) => Directionality(textDirection: TextDirection.rtl,
      child: AlertDialog(
        backgroundColor: const Color(0xFF12121E),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Text('ייצוא מפתחות', style: TextStyle(color: T.text, fontWeight: FontWeight.w900)),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('הבלוק הועתק ללוח. אפשר להדביק אותו לקובץ/הערה כדי לשמור, או להעביר למכשיר אחר.',
              style: TextStyle(color: T.muted, fontSize: 13)),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: Colors.white.withOpacity(0.05),
                borderRadius: BorderRadius.circular(10)),
            child: SelectableText(text, textDirection: TextDirection.ltr,
                style: const TextStyle(color: T.text, fontFamily: 'monospace', fontSize: 12.5)),
          ),
        ]),
        actions: [
          TextButton(onPressed: () => Clipboard.setData(ClipboardData(text: text)),
              child: const Text('העתק שוב')),
          FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('סגור')),
        ],
      )));
  }

  Future<void> _importDialog() async {
    final c = TextEditingController();
    final acc = Prefs.I.accent;
    await showDialog(context: context, builder: (ctx) => Directionality(textDirection: TextDirection.rtl,
      child: AlertDialog(
        backgroundColor: const Color(0xFF12121E),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Text('ייבוא מפתחות', style: TextStyle(color: T.text, fontWeight: FontWeight.w900)),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('הדביקו בלוק (שורה לכל ספק), או מפתח בודד — נזהה אוטומטית לפי סוג המפתח.',
              style: TextStyle(color: T.muted, fontSize: 13)),
          const SizedBox(height: 10),
          TextField(controller: c, maxLines: 6, textDirection: TextDirection.ltr,
              style: const TextStyle(color: T.text, fontSize: 13),
              decoration: _dec('groq=gsk_...\nsambanova=...\nnim=nvapi-...')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('ביטול')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: acc, foregroundColor: T.ink),
            onPressed: () {
              final parsed = _parseKeys(c.text);
              Navigator.pop(ctx);
              if (parsed.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('לא זוהו מפתחות בטקסט.')));
                return;
              }
              setState(() { parsed.forEach((id, v) { _edits[id]?.text = v; }); });
              ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('יובאו ${parsed.length} מפתחות. לחצו «שמירה» כדי לאשר.')));
            },
            child: const Text('ייבא'),
          ),
        ],
      )));
    c.dispose();
  }

  InputDecoration _dec(String hint) => InputDecoration(
    hintText: hint, hintStyle: const TextStyle(color: T.muted),
    filled: true, fillColor: Colors.white.withOpacity(0.05),
    isDense: true,
    enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: Colors.white.withOpacity(0.12))),
    focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: Prefs.I.accent)),
  );

  @override
  Widget build(BuildContext context) {
    final acc = Prefs.I.accent;
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 88),
      children: [
        const Text('מפתחות API חינמיים',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: T.text)),
        const SizedBox(height: 8),
        const Text('שלושה ספקים בעלי דרגה חינמית. הוסיפו מפתח מכל ספק שתרצו (מומלץ לפחות Groq). '
            'המפתחות נשמרים מוצפנים במכשיר שלכם בלבד - לעולם לא נשלחים לשום שרת.',
            style: TextStyle(color: T.muted, height: 1.35)),
        const SizedBox(height: 14),

        for (final p in Config.providers) _providerCard(p, acc),

        // import / export — one block, or a single key; easy to save or paste
        GlassPanel(radius: 14, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            const CcIcon('copy', size: 18, color: T.muted), const SizedBox(width: 8),
            const Text('ייבוא / ייצוא מפתחות', style: TextStyle(fontWeight: FontWeight.w700, color: T.text)),
          ]),
          const SizedBox(height: 4),
          const Text('שמרו את כל המפתחות בבלוק אחד להעברה/גיבוי, או הדביקו קובץ מוכן מראש.',
              style: TextStyle(color: T.muted, fontSize: 12)),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: OutlinedButton.icon(
              style: OutlinedButton.styleFrom(foregroundColor: acc,
                  side: BorderSide(color: acc.withOpacity(0.5)),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10))),
              icon: CcIcon('upload', size: 16, color: acc),
              label: const Text('ייצוא'), onPressed: _exportDialog,
            )),
            const SizedBox(width: 8),
            Expanded(child: OutlinedButton.icon(
              style: OutlinedButton.styleFrom(foregroundColor: acc,
                  side: BorderSide(color: acc.withOpacity(0.5)),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10))),
              icon: CcIcon('download', size: 16, color: acc),
              label: const Text('ייבוא'), onPressed: _importDialog,
            )),
          ]),
        ])),
        const SizedBox(height: 12),

        const SizedBox(height: 6),
        // consent GATE
        GlassPanel(radius: 14, glow: _consent ? acc : null, child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: () => setState(() => _consent = !_consent),
          child: Row(children: [
            _checkBox(_consent, acc),
            const SizedBox(width: 10),
            const Expanded(child: Text(
                'אני מאשר/ת: המפתחות שלי ישמשו לתרגום קהילתי דרך הספקים שבחרתי, '
                'נשמרים מוצפנים במכשיר ולעולם לא נשלחים לגורם אחר. חובה לאשר כדי לשמור.',
                style: TextStyle(color: T.text, fontSize: 13, height: 1.3))),
          ]),
        )),
        const SizedBox(height: 12),

        // proxy (optional)
        GlassPanel(radius: 14, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            const CcIcon('globe', size: 18, color: T.muted), const SizedBox(width: 8),
            const Text('פרוקסי (אופציונלי)', style: TextStyle(fontWeight: FontWeight.w700, color: T.text)),
          ]),
          const SizedBox(height: 4),
          const Text('האפליקציה לא כוללת VPN. אפשר להפעיל VPN מערכתי, או להזין כאן פרוקסי משלכם.',
              style: TextStyle(color: T.muted, fontSize: 12)),
          const SizedBox(height: 8),
          TextField(controller: _proxy, style: const TextStyle(color: T.text),
              decoration: _dec('http://host:port')),
        ])),
        const SizedBox(height: 18),

        if (!_consent) const Padding(padding: EdgeInsets.only(bottom: 8),
            child: Text('סמנו את תיבת האישור למעלה כדי לשמור.',
                textAlign: TextAlign.center, style: TextStyle(color: T.amber, fontSize: 12.5))),
        FilledButton(
          style: FilledButton.styleFrom(
              backgroundColor: _consent ? acc : Colors.white24,
              foregroundColor: T.ink, minimumSize: const Size.fromHeight(50),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14))),
          onPressed: _consent ? _save : null,
          child: const Text('שמירה', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
        ),
      ],
    );
  }

  Widget _providerCard(List<String> p, Color acc) {
    final id = p[1];
    final has = (_edits[id]?.text ?? '').trim().isNotEmpty;
    final g = _guides[id]!;
    return Padding(padding: const EdgeInsets.only(bottom: 12), child: GlassPanel(
      radius: 16, glow: has ? acc : null,
      padding: const EdgeInsets.fromLTRB(14, 6, 14, 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Theme(
          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
          child: ExpansionTile(
            tilePadding: EdgeInsets.zero,
            childrenPadding: const EdgeInsets.only(bottom: 6),
            iconColor: T.muted, collapsedIconColor: T.muted,
            title: Row(children: [
              Container(width: 9, height: 9, decoration: BoxDecoration(shape: BoxShape.circle,
                  color: has ? T.green : T.muted.withOpacity(0.5),
                  boxShadow: has ? [BoxShadow(color: T.green.withOpacity(0.6), blurRadius: 8)] : null)),
              const SizedBox(width: 8),
              Text(p[0], style: const TextStyle(fontWeight: FontWeight.w800, color: T.text, fontSize: 15)),
            ]),
            subtitle: const Padding(padding: EdgeInsets.only(top: 2),
                child: Text('איך משיגים מפתח? (שלב אחרי שלב)', style: TextStyle(color: T.muted, fontSize: 12))),
            children: [
              Text(g['note'] as String, style: TextStyle(color: acc, fontSize: 12.5, height: 1.3)),
              const SizedBox(height: 8),
              for (var i = 0; i < (g['steps'] as List).length; i++)
                Padding(padding: const EdgeInsets.only(bottom: 7), child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Container(width: 20, height: 20, alignment: Alignment.center,
                        decoration: BoxDecoration(shape: BoxShape.circle, color: acc.withOpacity(0.18)),
                        child: Text('${i + 1}', style: TextStyle(color: acc, fontSize: 12, fontWeight: FontWeight.w800))),
                    const SizedBox(width: 8),
                    Expanded(child: Text((g['steps'] as List)[i] as String,
                        style: const TextStyle(color: T.text, fontSize: 13, height: 1.35))),
                  ])),
              const SizedBox(height: 6),
              Row(children: [
                Expanded(child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(foregroundColor: acc,
                      side: BorderSide(color: acc.withOpacity(0.5)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10))),
                  icon: CcIcon('external', size: 16, color: acc),
                  label: const Text('פתחו את האתר'),
                  onPressed: () => _open(g['url'] as String),
                )),
                const SizedBox(width: 8),
                IconButton(
                  tooltip: 'העתקת הקישור',
                  icon: const CcIcon('copy', size: 18, color: T.muted),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: g['url'] as String));
                    ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('הקישור הועתק')));
                  }),
              ]),
            ],
          ),
        ),
        const SizedBox(height: 6),
        TextField(controller: _edits[id], obscureText: !(_show[id] ?? false),
            onChanged: (_) => setState(() {}),
            style: const TextStyle(color: T.text),
            decoration: _dec('הדביקו כאן את מפתח ${p[0]}').copyWith(
              suffixIcon: IconButton(
                tooltip: (_show[id] ?? false) ? 'הסתרה' : 'הצגה',
                icon: CcIcon((_show[id] ?? false) ? 'eye-off' : 'eye', size: 18, color: T.muted),
                onPressed: () => setState(() => _show[id] = !(_show[id] ?? false)),
              ),
            )),
      ]),
    ));
  }

  Widget _checkBox(bool on, Color acc) => AnimatedContainer(
    duration: Prefs.I.dur(200), width: 24, height: 24,
    decoration: BoxDecoration(borderRadius: BorderRadius.circular(7),
        color: on ? acc : Colors.transparent,
        border: Border.all(color: on ? acc : T.muted, width: 2)),
    child: on ? const CcIcon('check', size: 16, color: T.ink, stroke: 3) : null,
  );
}
