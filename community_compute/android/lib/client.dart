// Control-plane client — the Worker's secret-gated /cc/* routes (line-model).
// v1.0.1: moved off the site's Supabase RPCs to the dedicated Turso queue, so a
// busy volunteer fleet can never touch the site's AUTH/storage.
// Pull model: the worker connects OUT, so the operator never learns its IP.
// NetworkError = "unreachable now → buffer + retry"; ApiError = a real 4xx.
// Every reply carries the server's live `config` → ServerConfig.apply (that is
// what lets the operator retune heartbeat/batch with no app rebuild).
// Mirrors desktop/client.py.
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';
import 'config.dart';
import 'state.dart';

class NetworkError implements Exception { final String m; NetworkError(this.m); }
class ApiError implements Exception { final String m; ApiError(this.m); }

/// Set when the server says this device must re-enroll (its worker row is gone).
bool needsReenroll = false;

http.Client _client(String proxy) {
  if (proxy.trim().isEmpty) return http.Client();
  final hc = HttpClient();
  final u = Uri.parse(proxy);
  hc.findProxy = (uri) => 'PROXY ${u.host}:${u.port}';
  return IOClient(hc);
}

Future<Map<String, dynamic>> _cc(String op, Map<String, dynamic> body, String proxy) async {
  final client = _client(proxy);
  try {
    final r = await client.post(
      Uri.parse('${Config.ccBase}/$op'),
      headers: {
        'x-cc-secret': Config.ccSecret,
        'Content-Type': 'application/json',
      },
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 45));
    if (r.statusCode >= 500) throw NetworkError('$op ${r.statusCode}');
    if (r.statusCode >= 400) throw ApiError('$op ${r.statusCode}: ${r.body}');
    final b = utf8.decode(r.bodyBytes).trim();
    final j = b.isEmpty ? <String, dynamic>{} : jsonDecode(b);
    final m = (j is Map) ? j.cast<String, dynamic>() : <String, dynamic>{};
    ServerConfig.apply(m['config']);                 // live tuning, every reply
    if (m['blocked'] == true) ServerConfig.blocked = true;
    if (m['reenroll'] == true) needsReenroll = true;
    return m;
  } on SocketException catch (e) {
    throw NetworkError(e.message);
  } on HttpException catch (e) {
    throw NetworkError(e.message);
  } on Exception catch (e) {
    if (e is ApiError || e is NetworkError) rethrow;
    throw NetworkError(e.toString());
  } finally {
    client.close();
  }
}

Future<void> enroll(String workerId, String proxy) async {
  final m = await _cc('enroll', {'worker': workerId, 'platform': 'android'}, proxy);
  ServerConfig.blocked = m['blocked'] == true;
  needsReenroll = false;
}

/// Claim up to [maxLines] single LINES. Returns Jobs {id, sys, target, src}.
/// The server caps the batch at its live `batch_size`.
Future<List<Job>> claim(String workerId, int maxLines, String proxy) async {
  final m = await _cc('claim', {'worker': workerId, 'max': maxLines}, proxy);
  final out = <Job>[];
  for (final r in (m['lines'] as List? ?? [])) {
    out.add(Job(r['id'].toString(), r['sys'] ?? '', r['target'] ?? '', r['src'] ?? ''));
  }
  return out;
}

/// Submit MANY finished lines in one call. Returns the count the server
/// committed — it accepts ONLY lines this worker still holds (poison-safe).
Future<int> submit(String workerId, Map<String, String> out, String proxy) async {
  final m = await _cc('submit', {'worker': workerId, 'out': out}, proxy);
  final v = m['accepted'];
  return (v is num) ? v.toInt() : int.tryParse('$v') ?? 0;
}

/// Heartbeat — ONE cheap write (the per-worker lease). Keeps this device's
/// claimed lines from being reclaimed while it is alive.
Future<int> renew(String workerId, String proxy) async {
  final m = await _cc('renew', {'worker': workerId}, proxy);
  return m['ok'] == true ? 1 : 0;
}

/// Graceful release — return this worker's claimed lines to the pool now.
Future<int> release(String workerId, String proxy) async {
  final m = await _cc('release', {'worker': workerId}, proxy);
  final v = m['released'];
  return (v is num) ? v.toInt() : int.tryParse('$v') ?? 0;
}

/// The device's own public IP — shown LOCALLY to its owner only, never sent to
/// our server (the pull model keeps the IP private).
Future<String> fetchIp(String proxy) async {
  final client = _client(proxy);
  try {
    final r = await client.get(Uri.parse('https://api.ipify.org?format=json'))
        .timeout(const Duration(seconds: 12));
    if (r.statusCode == 200) {
      final j = jsonDecode(utf8.decode(r.bodyBytes));
      return (j['ip'] ?? '').toString();
    }
  } catch (_) {}
  finally { client.close(); }
  return '';
}
