import 'package:flutter/material.dart';
import '../config.dart';
import '../icons.dart';
import '../theme.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});
  @override
  Widget build(BuildContext context) {
    const rows = [
      ['activity', 'כשהמתג פעיל, האפליקציה מושכת מנות-תרגום קטנות, מתרגמת אותן עם המפתחות שלכם '
          '(Groq · SambaNova · NVIDIA NIM), ומחזירה את התוצאה.'],
      ['shield', 'המפתחות מוצפנים במכשיר (Android Keystore) ולעולם לא נשלחים.'],
      ['globe', 'מודל משיכה: השרת אף פעם לא מתחבר אליכם - כתובת ה-IP שלכם לא נחשפת.'],
      ['download', 'אם אין קשר לשרת - העבודה נאגרת מקומית ונשלחת אוטומטית כשהחיבור חוזר.'],
      ['check', 'התרגומים עוברים בקרת-איכות ואישור לפני שהם נכנסים לתרגום עצמו.'],
      ['key', 'אין קוד שרירותי - האפליקציה מבצעת אך ורק קריאות-תרגום לספקים שבחרתם.'],
    ];
    final acc = Prefs.I.accent;
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 88),
      children: [
        const Text('על האפליקציה', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: T.text)),
        const SizedBox(height: 10),
        const Text('מחשוב קהילתי מאפשר למתנדבים לתרום כוח-תרגום לפרויקט התרגום העברי - '
            'בבטחה, בפרטיות, ובשליטה מלאה.', style: TextStyle(color: T.text, height: 1.4)),
        const SizedBox(height: 14),
        for (final r in rows)
          Padding(padding: const EdgeInsets.only(bottom: 10), child: GlassPanel(
            radius: 14, padding: const EdgeInsets.all(13),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              CcIcon(r[0], size: 19, color: acc), const SizedBox(width: 11),
              Expanded(child: Text(r[1], style: const TextStyle(color: T.muted, height: 1.4))),
            ]),
          )),
        const SizedBox(height: 12),
        Center(child: Text('גרסה ${Config.appVersion}', style: const TextStyle(color: T.muted))),
      ],
    );
  }
}
