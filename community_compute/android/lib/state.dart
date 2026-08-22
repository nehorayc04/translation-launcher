// Persistent local state — the OFFLINE BUFFER (inbox/outbox) + settings + stats.
// LINE-MODEL: inbox = claimed single LINES; outbox = a {lineId: hebrew} map of
// finished lines awaiting one submit. When the server is unreachable the worker
// keeps translating from the inbox and piles results in the outbox, syncing on
// reconnect. Nothing is lost across a blip or an app restart. Holds only game
// text + translations (no secrets) → plain JSON in shared_preferences.
import 'dart:convert';
import 'dart:math';
import 'package:shared_preferences/shared_preferences.dart';

class Job {
  final String id, sys, target, src;
  Job(this.id, this.sys, this.target, this.src);
  Map<String, dynamic> toJson() => {'id': id, 'sys': sys, 'target': target, 'src': src};
  static Job fromJson(Map j) =>
      Job(j['id'].toString(), j['sys'] ?? '', j['target'] ?? '', j['src'] ?? '');
}

class AppState {
  late SharedPreferences _p;
  String workerId = '';
  bool enabled = false;
  String proxy = '';
  bool consent = false;
  int linesDone = 0, jobsDone = 0;
  Map<String, int> byProvider = {};
  List<Job> inbox = [];
  Map<String, String> outbox = {}; // lineId -> hebrew, awaiting submit
  String ip = '';                  // device public IP (shown locally only)
  List<List<int>> submitLog = [];  // [[epochSec, count], ...] for rate + last-hour
  DateTime? startedAt;             // when the switch was last turned ON (for uptime)

  Future<void> init() async {
    _p = await SharedPreferences.getInstance();
    workerId = _p.getString('worker_id') ?? '';
    if (workerId.isEmpty) {
      final r = Random.secure();
      workerId = List.generate(16, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
      await _p.setString('worker_id', workerId);
    }
    enabled = _p.getBool('enabled') ?? false;
    proxy = _p.getString('proxy') ?? '';
    consent = _p.getBool('consent') ?? false;
    linesDone = _p.getInt('lines_done') ?? 0;
    jobsDone = _p.getInt('jobs_done') ?? 0;
    byProvider = Map<String, int>.from(jsonDecode(_p.getString('by_provider') ?? '{}'));
    inbox = (jsonDecode(_p.getString('inbox') ?? '[]') as List).map((e) => Job.fromJson(e)).toList();
    outbox = Map<String, String>.from(jsonDecode(_p.getString('outbox') ?? '{}'));
    ip = _p.getString('ip') ?? '';
    submitLog = (jsonDecode(_p.getString('submit_log') ?? '[]') as List)
        .map((e) => List<int>.from(e)).toList();
    final startMs = _p.getInt('started_at');
    if (enabled && startMs != null) startedAt = DateTime.fromMillisecondsSinceEpoch(startMs);
  }

  /// Human uptime since the switch was last turned on (updates on the 4s UI tick).
  String uptimeText() {
    if (startedAt == null) return '';
    var s = DateTime.now().difference(startedAt!).inSeconds;
    if (s < 0) s = 0;
    final h = s ~/ 3600, m = (s % 3600) ~/ 60;
    if (h > 0) return "$h שע' $m דק'";
    if (m > 0) return "$m דק'";
    return "$s שנ'";
  }

  Future<void> setIp(String v) async { ip = v; await _p.setString('ip', v); }

  int _nowSec() => DateTime.now().millisecondsSinceEpoch ~/ 1000;

  Future<void> logSubmit(int n) async {
    if (n <= 0) return;
    final now = _nowSec();
    submitLog.add([now, n]);
    submitLog.removeWhere((e) => e[0] < now - 3600);   // keep 1h
    if (submitLog.length > 4000) submitLog = submitLog.sublist(submitLog.length - 4000);
    await _p.setString('submit_log', jsonEncode(submitLog));
  }

  /// Lines committed in the last hour (for the persistent notification).
  int linesLastHour() {
    final cut = _nowSec() - 3600;
    return submitLog.where((e) => e[0] >= cut).fold(0, (s, e) => s + e[1]);
  }

  /// Live rate per minute — measured over the last 10 minutes; falls back to the
  /// hour if the short window is empty.
  double ratePerMin() {
    final now = _nowSec();
    final r10 = submitLog.where((e) => e[0] >= now - 600).fold(0, (s, e) => s + e[1]);
    if (r10 > 0) return r10 / 10.0;
    return linesLastHour() / 60.0;
  }

  Future<void> setEnabled(bool v) async {
    enabled = v;
    await _p.setBool('enabled', v);
    if (v) {
      startedAt = DateTime.now();
      await _p.setInt('started_at', startedAt!.millisecondsSinceEpoch);
    } else {
      startedAt = null;
      await _p.remove('started_at');
    }
  }
  Future<void> setProxy(String v) async { proxy = v; await _p.setString('proxy', v); }
  Future<void> setConsent(bool v) async { consent = v; await _p.setBool('consent', v); }

  Future<void> _saveInbox() async =>
      _p.setString('inbox', jsonEncode(inbox.map((e) => e.toJson()).toList()));
  Future<void> _saveOutbox() async => _p.setString('outbox', jsonEncode(outbox));

  Future<void> addInbox(List<Job> jobs) async {
    final have = inbox.map((j) => j.id).toSet();
    for (final j in jobs) { if (!have.contains(j.id)) inbox.add(j); }
    await _saveInbox();
  }

  /// Take up to [n] lines from the front that SHARE the first line's sys prompt
  /// (so one provider call uses one prompt). Removes them from the inbox.
  Future<List<Job>> takeBatch(int n) async {
    if (inbox.isEmpty) return [];
    final sys = inbox.first.sys;
    final out = <Job>[];
    while (inbox.isNotEmpty && out.length < n && inbox.first.sys == sys) {
      out.add(inbox.removeAt(0));
    }
    await _saveInbox();
    return out;
  }

  Future<void> requeueFront(List<Job> jobs) async {
    inbox.insertAll(0, jobs);
    await _saveInbox();
  }

  /// Clear the whole inbox (used on graceful OFF after a server-side release).
  Future<void> clearInbox() async { inbox = []; await _saveInbox(); }

  Future<void> addOutbox(Map<String, String> out, Map<String, int> counts) async {
    outbox.addAll(out);
    counts.forEach((k, v) => byProvider[k] = (byProvider[k] ?? 0) + v);
    await _p.setString('by_provider', jsonEncode(byProvider));
    await _saveOutbox();
  }

  Map<String, String> outboxSnapshot() => Map<String, String>.from(outbox);

  /// Drop the submitted ids; [committed] = how many the server actually accepted.
  Future<void> clearOutbox(Iterable<String> ids, int committed) async {
    for (final k in ids) { outbox.remove(k); }
    linesDone += committed;
    jobsDone += 1;
    await _p.setInt('lines_done', linesDone);
    await _p.setInt('jobs_done', jobsDone);
    await logSubmit(committed);
    await _saveOutbox();
  }
}
