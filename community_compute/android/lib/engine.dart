// The worker engine — a resilient LINE-MODEL pull-loop as a ChangeNotifier.
// Mirrors desktop/engine.py. Each tick: flush outbox -> heartbeat -> refill the
// line buffer -> translate one batch -> flush. A drop to the control plane does
// NOT stop translation; work buffers locally and syncs on reconnect. The store
// (Supabase) owns what is out and what is in: a claimed line that never comes
// back lease-expires and returns to the pool for OTHER workers - no reslice.
//
// Exposes a live PHASE so the UI can show, on a rainbow arc, exactly what is
// happening now: fetch -> translate/review (+auto-check) -> send.
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'client.dart' as api;
import 'config.dart';
import 'fg_service.dart';
import 'keystore.dart';
import 'providers.dart' as prov;
import 'state.dart';
import 'theme.dart' show Prefs;

class Engine extends ChangeNotifier {
  final AppState st;
  bool _alive = true;
  bool on;
  bool online = false;
  bool providersOk = false;
  int nKeys = 0;

  // live pipeline phase (drives the arc + notification)
  String phase = 'off'; // off|nokeys|fetch|translate|review|check|submit|idle|buffer|provfail
  String mode = 'translate'; // translate | review (from the job's sys)
  String provDetail = '';
  int _provFails = 0;
  DateTime _lastRenew = DateTime.fromMillisecondsSinceEpoch(0);
  DateTime _lastNotif = DateTime.fromMillisecondsSinceEpoch(0);
  DateTime _lastIpAt = DateTime.fromMillisecondsSinceEpoch(0);   // live IP refresh
  int _emptyClaims = 0;   // consecutive claims that came back empty (real drain vs a blip)
  bool _releasedOnOff = false;

  Timer? _uiTimer;   // refreshes the live data + rotates the explanations
  int _variant = 0;  // which phrasing of the current phase is shown
  int _tick = 0;     // 3s ticks; the explanation only changes every ~10s

  Engine(this.st) : on = st.enabled;

  Future<void> setOn(bool v) async {
    on = v;
    _releasedOnOff = false;
    phase = v ? 'idle' : 'off';
    await st.setEnabled(v);
    _pushNotif(force: true);
    notifyListeners();
  }

  void stop() { _alive = false; _uiTimer?.cancel(); }

  Future<void> refreshKeys() async {
    nKeys = KeyStore.available(await KeyStore.load()).length;
    notifyListeners();
  }

  void _setPhase(String p) { phase = p; notifyListeners(); _pushNotif(); }

  // ---- what the ring reads (4 stages: fetch · translate/review · check · send) --
  int get ringStage => switch (phase) {
        'fetch' => 0,
        'translate' || 'review' => 1,
        'check' => 2,
        'submit' => 3,
        _ => -1,
      };
  int get arcSegment => switch (phase) {
        'fetch' => 0,
        'translate' || 'review' || 'check' => 1,
        'submit' => 2,
        _ => -1,
      };
  // true only when the SERVER really had nothing for us (≥2 empty claims) — so the
  // UI never falsely says "no lines in queue" on a momentary blip.
  bool get queueEmpty => _emptyClaims >= 2;
  bool get arcRunning => on && (phase == 'fetch' || phase == 'translate' ||
      phase == 'review' || phase == 'check' || phase == 'submit');

  String get stageTitle => switch (phase) {
        'off' => 'כבוי',
        'nokeys' => 'צריך מפתח',
        'fetch' => 'שולף שורות',
        'translate' => 'מתרגם',
        'review' => 'בודק ומשפר',
        'check' => 'בדיקת תקינות',
        'submit' => 'שולח בחזרה',
        'buffer' => 'נאגר מקומית',
        'provfail' => 'תקלת ספק',
        _ => queueEmpty ? 'אין שורות בתור' : 'מתחבר לתור',
      };
  // rotating, plural/impersonal explanations — a fresh phrasing every few seconds
  // so the screen always feels alive, never stuck.
  List<String> _subVariants() => switch (phase) {
        'off' => const ['הפעילו את המתג כדי לתרום כוח-תרגום', 'המתג כבוי - שום עבודה לא רצה כרגע'],
        'nokeys' => const ['הוסיפו מפתח של ספק אחד לפחות בעמוד «מפתחות»',
              'בלי מפתח אין במה לתרגם - הוסיפו אחד בעמוד «מפתחות»'],
        'fetch' => const ['מושכים מנת שורות חדשה מהתור', 'התור שולח את המנה הבאה לתרגום',
              'מקבלים שורות טריות מהשרת'],
        'translate' => const ['המפתחות שלכם מתרגמים לעברית מול כמה שפות',
              'משווים לכמה שפות ובוחרים את הניסוח הטוב ביותר', 'מייצרים תרגום עברי איכותי'],
        'review' => const ['סוקרים תרגום קיים ומתקנים רק טעויות אמת',
              'עוברים על השורות ומשפרים מה שצריך', 'בקרת איכות - תרגום טוב נשאר כמו שהוא'],
        'check' => const ['מוודאים שהתוצאות שלמות ושהטוקנים נשמרו',
              'בדיקת תקינות אוטומטית לפני השליחה', 'מאמתים כל שורה לפני שהיא נשלחת'],
        'submit' => const ['מחזירים את השורות המתורגמות אל השרת',
              'שולחים את המנה שהושלמה בחזרה', 'המנה מסתנכרנת חזרה לתור'],
        'buffer' => const ['אין קשר לשרת - ממשיכים ואוגרים, יסתנכרן אוטומטית',
              'עובדים במצב לא-מקוון - הכול יישלח כשהחיבור יחזור',
              'שומרים את התוצאות מקומית עד שהשרת יחזור'],
        'provfail' => [provDetail.isEmpty ? 'אין קשר לספקים - מנסים שוב' : provDetail],
        _ => queueEmpty
            ? const ['אין כרגע שורות פנויות בתור - יתחדש כשיתווספו שורות',
                  'התור התרוקן לרגע - מוכנים לתרגם ברגע שיתווספו שורות']
            : const ['מתחברים לתור ובודקים שורות חדשות', 'מתארגנים לסבב הבא - עוד רגע ממשיכים'],
      };
  String get stageSub { final v = _subVariants(); return v[_variant % v.length]; }

  Future<void> start() async {
    var backoff = Config.pollIdleS;
    // refresh the on-screen data every 3s (rate / buffer / uptime), but only
    // change the wording of the explanation every ~10s so it never looks jittery.
    _uiTimer ??= Timer.periodic(const Duration(seconds: 3), (_) {
      _tick++;
      if (_tick % 3 == 0) _variant++;   // new phrasing ~every 9-10s
      notifyListeners();
      _pushNotif();
    });
    notifyListeners();
    while (_alive) {
      try {
      final keys = await KeyStore.load();
      nKeys = KeyStore.available(keys).length;
      final proxy = st.proxy;

      if (!on) {
        await _flush(proxy);
        if (!_releasedOnOff && st.inbox.isNotEmpty) {
          try {
            await api.release(st.workerId, proxy);
            await st.clearInbox();
            _releasedOnOff = true; online = true;
          } on api.NetworkError { online = false; } on api.ApiError { _releasedOnOff = true; }
        }
        _setPhase('off');
        await _sleep(Config.pollIdleS);
        backoff = Config.pollIdleS;
        continue;
      }
      if (nKeys == 0) {
        _setPhase('nokeys');
        await _sleep(Config.pollIdleS);
        continue;
      }

      // 0. enroll
      try {
        await api.enroll(st.workerId, proxy);
        online = true;
        // refresh the public IP live — on first run and whenever it may have
        // changed (network switch); updates the display only if it actually differs.
        if (st.ip.isEmpty || DateTime.now().difference(_lastIpAt).inSeconds > 90) {
          _lastIpAt = DateTime.now();
          unawaited(_refreshIp(proxy));
        }
      } on api.NetworkError {
        online = false;
      } on api.ApiError catch (e) {
        provDetail = 'השרת דחה: ${e.m}'; _setPhase('provfail');
        await _sleep(backoff);
        backoff = (backoff * 2).clamp(Config.pollIdleS, Config.pollMaxS);
        continue;
      }

      var didWork = false;

      // 1. flush finished results
      if (st.outbox.isNotEmpty) { _setPhase('submit'); }
      await _flush(proxy);

      // 2. heartbeat — ONE cheap write, at the interval the SERVER dictates
      // (ServerConfig.heartbeatS, default 5 min). Only while we can actually
      // translate, so we never hold lines hostage.
      if (online && providersOk && st.inbox.isNotEmpty &&
          DateTime.now().difference(_lastRenew).inSeconds >= ServerConfig.heartbeatS) {
        try {
          await api.renew(st.workerId, proxy); _lastRenew = DateTime.now(); online = true;
          if (api.needsReenroll) {                       // our worker row vanished
            await api.enroll(st.workerId, proxy);
          }
        }
        on api.NetworkError { online = false; } on api.ApiError { /* ignore */ }
      }

      // 3. refill. Small PROBE while providers are failing so we self-recover.
      if (online && st.inbox.length < Config.prefetchLines) {
        if (st.inbox.isEmpty) { _setPhase('fetch'); }
        final n = _provFails >= 2 ? 5 : ServerConfig.batchSize;
        try {
          final jobs = await api.claim(st.workerId, n, proxy);
          if (jobs.isNotEmpty) { await st.addInbox(jobs); online = true; _emptyClaims = 0; }
          else if (st.inbox.isEmpty) { _emptyClaims++; }   // server had nothing for us
        } on api.NetworkError { online = false; }
        on api.ApiError catch (e) { provDetail = 'השרת דחה: ${e.m}'; }
      }

      // 4. translate ONE batch (providers, not the server)
      final batch = await st.takeBatch(Config.workBatch);
      if (batch.isNotEmpty) {
        mode = batch.first.sys.contains('REVIEW') ? 'review' : 'translate';
        _setPhase(mode == 'review' ? 'review' : 'translate');
        final items = {for (final j in batch) j.id: j.src};
        Map<String, String> out = {};
        Map<String, int> counts = {};
        Map<String, String> statuses = {};
        try {
          final r = await prov.translateBatch(keys, batch.first.sys, items, proxy);
          out = r.$1; counts = r.$2; statuses = r.$3;
        } catch (_) {}
        if (out.isNotEmpty) {
          _setPhase('check');
          await st.addOutbox(out, counts);
          providersOk = true; didWork = true; _provFails = 0; provDetail = '';
          final missed = batch.where((j) => !out.containsKey(j.id)).toList();
          if (missed.isNotEmpty) await st.requeueFront(missed);
          _setPhase('submit');
          await _flush(proxy);
        } else {
          providersOk = false; _provFails++;
          provDetail = _statusNote(statuses);
          await st.requeueFront(batch);
          // a SINGLE momentary blip (rate-limit / network hiccup) recovers on the
          // next retry — don't flash a red "provider fault"; only surface it once
          // it has failed ≥2 times in a row (a genuine sustained problem).
          _setPhase(_provFails >= 2 ? 'provfail' : (online ? 'idle' : 'buffer'));
          if (online && _provFails >= 2) {
            try { await api.release(st.workerId, proxy); await st.clearInbox(); }
            on api.NetworkError { online = false; } on api.ApiError { /* ignore */ }
          }
        }
      }

      if (didWork) {
        backoff = Config.pollIdleS;
        _setPhase(online ? 'idle' : 'buffer');   // brief resting label between batches
      } else {
        if (!providersOk && _provFails >= 2 && provDetail.isNotEmpty) { _setPhase('provfail'); }
        else if (!online) { _setPhase('buffer'); }
        else { _setPhase('idle'); }
        // when we're online and the queue is NOT confirmed-drained, re-check SOON —
        // a spurious empty response / blip must never strand us on a long idle sleep
        // while thousands of lines wait. Only back off far when offline / truly drained.
        final ceiling = (online && !queueEmpty) ? 18 : Config.pollMaxS;
        backoff = (backoff * 2).clamp(Config.pollIdleS, ceiling);
      }
      if (!didWork) await _sleep(backoff);
      } catch (_) {
        // NEVER let an unexpected error kill the pull-loop (a dead loop = a frozen
        // "idle" screen forever). Breathe and continue — the queue keeps its lines.
        online = false;
        await _sleep(Config.pollIdleS);
      }
    }
    await _flush(st.proxy);
  }

  String _statusNote(Map<String, String> s) {
    const label = {'groq': 'Groq', 'sambanova': 'SambaNova', 'nim': 'NIM'};
    final bad = <String>[];
    s.forEach((p, code) {
      if (code == 'ok') return;
      final why = switch (code) {
        '401' || '403' => 'מפתח שגוי/נדחה',
        '429' => 'עומס - מנסה שוב',
        '402' => 'דורש תשלום',
        '503' => 'שירות לא זמין',
        'http' => 'שגיאת שרת',
        'parse' => 'תשובה לא תקינה',
        'timeout' => 'איטי מדי (זמן קצוב)',
        'cooldown' => 'בהמתנה',
        _ => 'שגיאת רשת',
      };
      bad.add('${label[p] ?? p}: $why');
    });
    return bad.isEmpty ? 'אין קשר לספקים - מנסה שוב' : bad.join(' · ');
  }

  Future<void> _flush(String proxy) async {
    if (st.outbox.isEmpty) return;
    final snap = st.outboxSnapshot();
    try {
      final committed = await api.submit(st.workerId, snap, proxy);
      await st.clearOutbox(snap.keys, committed);
      online = true;
    } on api.NetworkError {
      online = false;
    } on api.ApiError {
      await st.clearOutbox(snap.keys, 0);
    }
  }

  Future<void> _refreshIp(String proxy) async {
    try {
      final ip = await api.fetchIp(proxy);
      if (ip.isNotEmpty && ip != st.ip) { await st.setIp(ip); notifyListeners(); }
    } catch (_) {}
  }

  /// Push the live counters into the persistent notification (throttled).
  void _pushNotif({bool force = false}) {
    if (!Prefs.I.notif) return;
    final now = DateTime.now();
    if (!force && now.difference(_lastNotif).inSeconds < 12) return;
    _lastNotif = now;
    if (!on) { FgService.updateStats(paused: true); return; }
    FgService.updateStats(
      lastHour: st.linesLastHour(),
      ratePerMin: st.ratePerMin(),
      stage: stageTitle,
      total: st.linesDone,
      uptime: st.uptimeText(),
    );
  }

  Future<void> _sleep(int secs) async {
    final end = DateTime.now().add(Duration(seconds: secs));
    while (_alive && DateTime.now().isBefore(end)) {
      await Future.delayed(const Duration(milliseconds: 250));
    }
  }
}
