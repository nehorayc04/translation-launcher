// Encrypted storage for the volunteer's 3 provider keys — Android Keystore-backed
// (flutter_secure_storage). Keys are NEVER transmitted; used locally to call the
// providers. Mirrors desktop/keystore.py.
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class KeyStore {
  static const _s = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  static const _providerIds = ['groq', 'sambanova', 'nim'];

  static Future<Map<String, String>> load() async {
    final out = <String, String>{};
    for (final p in _providerIds) {
      final v = await _s.read(key: 'cc_key_$p');
      if (v != null && v.trim().isNotEmpty) out[p] = v.trim();
    }
    return out;
  }

  static Future<void> save(Map<String, String> keys) async {
    for (final p in _providerIds) {
      final v = (keys[p] ?? '').trim();
      if (v.isEmpty) {
        await _s.delete(key: 'cc_key_$p');
      } else {
        await _s.write(key: 'cc_key_$p', value: v);
      }
    }
  }

  static List<String> available(Map<String, String> keys) =>
      _providerIds.where((p) => (keys[p] ?? '').isNotEmpty).toList();
}
