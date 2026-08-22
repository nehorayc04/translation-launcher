// BYOK 3-provider adapter — shard a batch across the volunteer's providers, run
// them in parallel, retry any dropped line. Mirrors desktop/providers.py.
// Browser User-Agent is mandatory (Groq is behind Cloudflare). An optional
// user proxy is honored (the app bundles NO VPN).
//
// Each provider's slice is translated in SMALL CHUNKS (~15 lines/call) so no
// single request is huge — this matters when only ONE (possibly slow) provider
// is configured. Every call reports a per-provider STATUS so the UI can say WHY
// it failed: ok | 401 | 403 | 429 | 402 | 503 | http | timeout | neterr | parse.
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';
import 'config.dart';

const _ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/126.0 Safari/537.36';
const _chunk = 10; // max lines per provider call (smaller = friendlier to slow free tiers)

final _cooldown = <String, DateTime>{};

Map<String, List<String>> get _ep {
  final m = <String, List<String>>{};
  for (final p in Config.providers) {
    m[p[1]] = [p[2], p[3]]; // id -> [base, model]
  }
  return m;
}

http.Client _client(String proxy) {
  if (proxy.trim().isEmpty) return http.Client();
  final hc = HttpClient();
  final u = Uri.parse(proxy);
  hc.findProxy = (uri) => 'PROXY ${u.host}:${u.port}';
  return IOClient(hc);
}

List<String> available(Map<String, String> keys) =>
    ['groq', 'sambanova', 'nim'].where((p) => (keys[p] ?? '').trim().isNotEmpty).toList();

/// One HTTP call for a small chunk. Returns (translated, status).
Future<(Map<String, String>, String)> _call(String provider, String key, String sys,
    Map<String, dynamic> chunk, String proxy) async {
  if (chunk.isEmpty) return (<String, String>{}, 'ok');
  final cd = _cooldown[provider];
  if (cd != null && cd.isAfter(DateTime.now())) return (<String, String>{}, 'cooldown');
  final ep = _ep[provider]!;
  final user = 'Translate every value to Hebrew. Return ONLY a JSON object mapping the SAME '
      'ids to the Hebrew translation:\n${jsonEncode(chunk)}';
  final client = _client(proxy);
  try {
    final r = await client.post(Uri.parse('${ep[0]}/chat/completions'),
        headers: {
          'Authorization': 'Bearer $key',
          'Content-Type': 'application/json',
          'User-Agent': _ua,
        },
        body: jsonEncode({
          'model': ep[1], 'temperature': 0.2, 'max_tokens': 2000, 'stream': false,
          'messages': [
            {'role': 'system', 'content': sys},
            {'role': 'user', 'content': user},
          ],
        })).timeout(const Duration(seconds: 120));
    if (r.statusCode == 429 || r.statusCode == 402 || r.statusCode == 503) {
      _cooldown[provider] = DateTime.now().add(const Duration(seconds: 60));
      return (<String, String>{}, '${r.statusCode}');
    }
    if (r.statusCode == 401 || r.statusCode == 403) {
      _cooldown[provider] = DateTime.now().add(const Duration(seconds: 120)); // bad key — don't hammer
      return (<String, String>{}, '${r.statusCode}');
    }
    if (r.statusCode >= 400) {
      _cooldown[provider] = DateTime.now().add(const Duration(seconds: 30));
      return (<String, String>{}, 'http');
    }
    String content;
    try {
      content = jsonDecode(utf8.decode(r.bodyBytes))['choices'][0]['message']['content'] as String;
    } catch (_) {
      return (<String, String>{}, 'parse');
    }
    final m = RegExp(r'\{.*\}', dotAll: true).firstMatch(content);
    if (m == null) return (<String, String>{}, 'parse');
    Map got;
    try { got = jsonDecode(m.group(0)!) as Map; } catch (_) { return (<String, String>{}, 'parse'); }
    final out = <String, String>{};
    chunk.forEach((k, _) {
      final v = got[k] ?? got[k.toString()];
      if (v is String && v.trim().isNotEmpty) out[k] = v.trim();
    });
    return (out, out.isEmpty ? 'parse' : 'ok');
  } on TimeoutException {
    _cooldown[provider] = DateTime.now().add(const Duration(seconds: 30)); // slow key — back off briefly
    return (<String, String>{}, 'timeout');
  } on SocketException {
    _cooldown[provider] = DateTime.now().add(const Duration(seconds: 20));
    return (<String, String>{}, 'neterr');
  } on HttpException {
    _cooldown[provider] = DateTime.now().add(const Duration(seconds: 20));
    return (<String, String>{}, 'neterr');
  } catch (_) {
    _cooldown[provider] = DateTime.now().add(const Duration(seconds: 20));
    return (<String, String>{}, 'neterr');
  } finally {
    client.close();
  }
}

/// Translate a provider's whole slice in chunks of [_chunk]. Stops early if the
/// provider goes on cooldown (429/402/503). Returns (translated, worst status).
Future<(Map<String, String>, String)> _shard(String provider, String key, String sys,
    Map<String, dynamic> shard, String proxy) async {
  if (shard.isEmpty) return (<String, String>{}, 'ok');
  // a HARD failure means the whole key/provider is unhealthy right now — stop
  // spending another 120s per chunk on it (a bad/slow key used to hang the batch
  // for up to ~15 min, showing "מתרגם" while producing nothing). 'parse' is
  // per-chunk (the model may fix the next one), so it does NOT break.
  const hard = {'timeout', 'neterr', '401', '403', 'http', '429', '402', '503', 'cooldown'};
  final ids = shard.keys.toList();
  final out = <String, String>{};
  var worst = 'ok';
  for (var i = 0; i < ids.length; i += _chunk) {
    final sub = {for (final k in ids.skip(i).take(_chunk)) k: shard[k]};
    final (got, stat) = await _call(provider, key, sys, sub, proxy);
    out.addAll(got);
    if (stat != 'ok' && got.isEmpty) {
      worst = stat;
      if (hard.contains(stat)) break;   // fail fast — don't grind all chunks on a dead key
    }
  }
  return (out, out.isEmpty ? worst : 'ok');
}

/// Returns (out {id:he}, counts {provider:lines}, statuses {provider:code}).
Future<(Map<String, String>, Map<String, int>, Map<String, String>)> translateBatch(
    Map<String, String> keys, String sys, Map<String, dynamic> items, String proxy) async {
  final provs = available(keys);
  if (provs.isEmpty) throw StateError('no provider keys');
  final ids = items.keys.toList();
  final shards = {for (final p in provs) p: <String, dynamic>{}};
  for (var i = 0; i < ids.length; i++) {
    shards[provs[i % provs.length]]![ids[i]] = items[ids[i]];
  }
  final results = await Future.wait(
      provs.map((p) => _shard(p, keys[p]!, sys, shards[p]!, proxy)));
  final out = <String, String>{};
  final counts = <String, int>{};
  final statuses = <String, String>{};
  for (var i = 0; i < provs.length; i++) {
    out.addAll(results[i].$1);
    counts[provs[i]] = (counts[provs[i]] ?? 0) + results[i].$1.length;
    statuses[provs[i]] = results[i].$2;
  }
  // retry dropped lines on a not-cooling provider
  var missing = {for (final k in ids) if (!out.containsKey(k)) k: items[k]};
  if (missing.isNotEmpty) {
    for (final p in provs) {
      final cd = _cooldown[p];
      if (cd != null && cd.isAfter(DateTime.now())) continue;
      final (got, stat) = await _shard(p, keys[p]!, sys, missing, proxy);
      out.addAll(got);
      counts[p] = (counts[p] ?? 0) + got.length;
      if (got.isNotEmpty) statuses[p] = 'ok';
      else if (statuses[p] == 'ok') statuses[p] = stat;
      missing = {for (final k in ids) if (!out.containsKey(k)) k: items[k]};
      if (missing.isEmpty) break;
    }
  }
  return (out, counts, statuses);
}
