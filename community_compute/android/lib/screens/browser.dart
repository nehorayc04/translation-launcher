// In-app browser tab — the project's website, comfortable to operate, with
// downloads handed to Android's system download manager so files (mods / the
// APK) actually save to the phone's Downloads folder.
import 'dart:ui' show ImageFilter;
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../icons.dart';
import '../theme.dart';

const _home = 'https://hebrew-translation-hub.com';

class BrowserScreen extends StatefulWidget {
  const BrowserScreen({super.key});
  @override
  State<BrowserScreen> createState() => _BrowserScreenState();
}

class _BrowserScreenState extends State<BrowserScreen> {
  double _progress = 0;
  bool _loading = true;
  bool _error = false;

  late final WebViewController _c = WebViewController()
    ..setJavaScriptMode(JavaScriptMode.unrestricted)
    ..setBackgroundColor(T.canvas)
    ..setNavigationDelegate(NavigationDelegate(
      onProgress: (p) => setState(() => _progress = p / 100),
      onPageStarted: (_) => setState(() { _loading = true; _error = false; }),
      onPageFinished: (_) => setState(() => _loading = false),
      onWebResourceError: (e) {
        if (e.isForMainFrame ?? true) setState(() { _error = true; _loading = false; });
      },
      onNavigationRequest: (req) {
        // a real download link → let Android's download manager handle it
        if (_isDownload(req.url)) {
          launchUrl(Uri.parse(req.url), mode: LaunchMode.externalApplication);
          return NavigationDecision.prevent;
        }
        return NavigationDecision.navigate;
      },
    ))
    ..loadRequest(Uri.parse(_home));

  static bool _isDownload(String url) {
    final u = Uri.tryParse(url);
    if (u == null) return false;
    final path = u.path.toLowerCase();
    if (u.host.contains('github') && path.contains('/releases/download/')) return true;
    const ext = ['.apk', '.exe', '.zip', '.7z', '.rar', '.dmg', '.msi', '.iso', '.pkg'];
    return ext.any(path.endsWith);
  }

  Future<void> _back() async {
    if (await _c.canGoBack()) _c.goBack();
  }

  Future<void> _forward() async {
    if (await _c.canGoForward()) _c.goForward();
  }

  @override
  Widget build(BuildContext context) {
    final acc = Prefs.I.accent;
    return Column(children: [
      // slim chrome — a floating GLASS bar (home / back / forward / reload)
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topCenter, end: Alignment.bottomCenter,
                  colors: [Color(0x2EFFFFFF), Color(0x14FFFFFF), Color(0x120C0C1A)],
                  stops: [0, 0.55, 1],
                ),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0x33FFFFFF)),
              ),
              child: Row(children: [
                _navBtn('home', 'דף הבית', () => _c.loadRequest(Uri.parse(_home))),
                _navBtn('chevron-right', 'אחורה', _back),      // RTL: back = points right
                _navBtn('chevron-left', 'קדימה', _forward),
                const Spacer(),
                _navBtn('refresh', 'רענון', () => _c.reload()),
              ]),
            ),
          ),
        ),
      ),
      SizedBox(
        height: 2.5,
        child: (_loading && _progress < 1)
            ? LinearProgressIndicator(value: _progress == 0 ? null : _progress,
                backgroundColor: Colors.transparent, color: acc, minHeight: 2.5)
            : const SizedBox.shrink(),
      ),
      // clear the floating glass nav at the bottom (extendBody lets us reach it)
      Expanded(child: Padding(
        padding: const EdgeInsets.only(bottom: 84),
        child: _error ? _errorView(acc) : WebViewWidget(controller: _c))),
    ]);
  }

  // a small ROUND glass button — consistent, clearly tappable
  Widget _navBtn(String icon, String tip, VoidCallback on) => Tooltip(
        message: tip,
        child: Padding(
          padding: const EdgeInsets.all(2),
          child: Material(
            color: Colors.white.withOpacity(0.06),
            shape: const CircleBorder(),
            child: InkWell(
              customBorder: const CircleBorder(),
              onTap: on,
              child: Padding(padding: const EdgeInsets.all(9),
                  child: CcIcon(icon, size: 19, color: T.text)),
            ),
          ),
        ),
      );

  Widget _errorView(Color acc) => Center(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const CcIcon('globe', size: 40, color: T.muted),
          const SizedBox(height: 12),
          const Text('לא ניתן לטעון את האתר כרגע', textAlign: TextAlign.center,
              style: TextStyle(color: T.text, fontWeight: FontWeight.w800, fontSize: 16)),
          const SizedBox(height: 4),
          const Text('בדקו את חיבור האינטרנט ונסו שוב', textAlign: TextAlign.center,
              style: TextStyle(color: T.muted)),
          const SizedBox(height: 16),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: acc, foregroundColor: T.ink,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
            onPressed: () { setState(() => _error = false); _c.loadRequest(Uri.parse(_home)); },
            child: const Text('נסו שוב', style: TextStyle(fontWeight: FontWeight.w800)),
          ),
        ]),
      ));
}
