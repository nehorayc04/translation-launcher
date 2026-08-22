import 'dart:ui' show ImageFilter;
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import 'config.dart';
import 'engine.dart';
import 'fg_service.dart';
import 'icons.dart';
import 'screens/about.dart';
import 'screens/browser.dart';
import 'screens/home.dart';
import 'screens/keys.dart';
import 'screens/settings.dart';
import 'state.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Prefs.I.init();
  final st = AppState();
  await st.init();
  final engine = Engine(st);
  engine.start(); // fire-and-forget resilient loop
  await FgService.requestPermissions(); // notification perm — the status notification needs it
  if (st.enabled) {
    await FgService.start();
    await WakelockPlus.enable();
  }
  runApp(CommunityComputeApp(engine: engine, st: st));
}

class CommunityComputeApp extends StatelessWidget {
  final Engine engine;
  final AppState st;
  const CommunityComputeApp({super.key, required this.engine, required this.st});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Prefs.I, // live accent + text-size + anim
      builder: (_, __) => MaterialApp(
        title: Config.appName,
        debugShowCheckedModeBanner: false,
        theme: T.build(),
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(Prefs.I.textScale)),
          child: Directionality(textDirection: TextDirection.rtl, child: child!),
        ),
        home: RootScaffold(engine: engine, st: st),
      ),
    );
  }
}

class RootScaffold extends StatefulWidget {
  final Engine engine;
  final AppState st;
  const RootScaffold({super.key, required this.engine, required this.st});
  @override
  State<RootScaffold> createState() => _RootScaffoldState();
}

class _RootScaffoldState extends State<RootScaffold> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeBatteryPrompt());
  }

  Future<void> _maybeBatteryPrompt() async {
    final p = await SharedPreferences.getInstance();
    if (p.getBool('battery_prompted') ?? false) return;
    await p.setBool('battery_prompted', true);
    if (await FgService.isBatteryUnrestricted()) return;
    if (!mounted) return;
    final acc = Prefs.I.accent;
    showDialog(context: context, builder: (ctx) => Directionality(
      textDirection: TextDirection.rtl,
      child: AlertDialog(
        backgroundColor: const Color(0xFF12121E),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(children: [
          CcIcon('battery', size: 24, color: acc), const SizedBox(width: 10),
          const Text('הרשאת רקע', style: TextStyle(color: T.text, fontSize: 18, fontWeight: FontWeight.w900)),
        ]),
        content: const Text(
            'כדי שהאפליקציה תמשיך לתרום גם כשהמסך כבוי, כדאי להגדיר אותה ל«ללא הגבלה» '
            'באופטימיזציית הסוללה. אחרת אנדרואיד עלול לעצור אותה ברקע.',
            style: TextStyle(color: T.muted, height: 1.4)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('אחר כך')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: acc, foregroundColor: T.ink,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10))),
            onPressed: () async { Navigator.pop(ctx); await FgService.requestBatteryUnrestricted(); },
            child: const Text('הגדר עכשיו', style: TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    ));
  }

  Future<void> _onToggle(bool on) async {
    await widget.engine.setOn(on);
    if (on) { await FgService.start(); await WakelockPlus.enable(); }
    else { await FgService.stop(); await WakelockPlus.disable(); }
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final screens = [
      HomeScreen(engine: widget.engine, onToggle: _onToggle, goToKeys: () => setState(() => _index = 1)),
      KeysScreen(st: widget.st, onSaved: () => widget.engine.refreshKeys()),
      const BrowserScreen(),
      const SettingsScreen(),
      const AboutScreen(),
    ];
    return Scaffold(
      backgroundColor: T.canvas,
      // the body (incl. the colourful Ambient) reaches BEHIND the bottom nav, so
      // the nav's backdrop-blur has real colour to refract = floating glass, not black.
      extendBody: true,
      body: Stack(children: [
        Ambient(accent: Prefs.I.accent, cycle: Prefs.I.bgCycles),
        // cap the content width so on a large display (tablet) everything stays a
        // comfortable STANDARD size, centred — never stretched across the screen.
        SafeArea(child: Center(child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: _GlassSwitcher(index: _index, child: KeyedSubtree(
              key: ValueKey(_index), child: screens[_index]))))),
      ]),
      bottomNavigationBar: _GlassNav(index: _index, onTap: (i) => setState(() => _index = i)),
    );
  }
}

/// Liquid-glass screen transition (the launcher's look): the outgoing view blurs
/// away + fades while the incoming MATERIALISES from a blur into focus, with a
/// tiny scale — a fluid "melt" between tabs. Instant when animations are off.
class _GlassSwitcher extends StatelessWidget {
  final int index;
  final Widget child;
  const _GlassSwitcher({required this.index, required this.child});

  @override
  Widget build(BuildContext context) {
    if (!Prefs.I.animOn) return child;
    return AnimatedSwitcher(
      duration: Prefs.I.dur(360),
      switchInCurve: Curves.easeOutCubic,
      switchOutCurve: Curves.easeInCubic,
      // overlap outgoing + incoming so the melt is continuous
      layoutBuilder: (cur, prev) => Stack(alignment: Alignment.topCenter,
          children: [...prev, if (cur != null) cur]),
      transitionBuilder: (c, anim) => AnimatedBuilder(
        animation: anim,
        builder: (_, __) {
          final v = anim.value.clamp(0.0, 1.0);
          final blur = (1 - v) * 14;                 // 14→0 as it comes into focus
          return Opacity(
            opacity: v,
            child: ImageFiltered(
              imageFilter: ImageFilter.blur(sigmaX: blur, sigmaY: blur, tileMode: TileMode.decal),
              child: Transform.scale(scale: 0.965 + 0.035 * v, child: c),
            ),
          );
        },
      ),
      child: child,
    );
  }
}

class _GlassNav extends StatelessWidget {
  final int index;
  final ValueChanged<int> onTap;
  const _GlassNav({required this.index, required this.onTap});

  static const _items = [
    ['הפעלה', 'power'],
    ['מפתחות', 'key'],
    ['דפדפן', 'globe'],
    ['הגדרות', 'gear'],
    ['מידע', 'info'],
  ];

  @override
  Widget build(BuildContext context) {
    final acc = Prefs.I.accent;
    final r = BorderRadius.circular(22);
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      // a FLOATING GLASS pill: real backdrop blur + frosted sheen (so the shifting
      // colourful background reads THROUGH it) — never a flat black rectangle.
      child: DecoratedBox(
        decoration: BoxDecoration(borderRadius: r, boxShadow: [
          BoxShadow(color: acc.withOpacity(0.12), blurRadius: 26, spreadRadius: -8),
        ]),
        child: ClipRRect(
          borderRadius: r,
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topCenter, end: Alignment.bottomCenter,
                  colors: [Color(0x2EFFFFFF), Color(0x14FFFFFF), Color(0x120C0C1A)],
                  stops: [0, 0.55, 1],
                ),
                borderRadius: r,
                border: Border.all(color: const Color(0x38FFFFFF), width: 1),
              ),
              child: Row(children: [
        for (var i = 0; i < _items.length; i++)
          Expanded(child: GestureDetector(
            onTap: () => onTap(i),
            behavior: HitTestBehavior.opaque,
            child: AnimatedContainer(
              duration: Prefs.I.dur(260), curve: Curves.easeOutBack,
              padding: const EdgeInsets.symmetric(vertical: 9),
              margin: const EdgeInsets.symmetric(horizontal: 3),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                color: i == index ? acc.withOpacity(0.16) : Colors.transparent,
                boxShadow: i == index ? [BoxShadow(color: acc.withOpacity(0.30), blurRadius: 18, spreadRadius: -6)] : null,
              ),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                CcIcon(_items[i][1], size: 21, color: i == index ? acc : T.muted, stroke: 2),
                const SizedBox(height: 3),
                Text(_items[i][0], style: TextStyle(fontSize: 11.5,
                    fontWeight: i == index ? FontWeight.w800 : FontWeight.w500,
                    color: i == index ? T.text : T.muted)),
              ]),
            ),
          )),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
