// Baked constants — mirror desktop/config.py so both clients hit the same API.
//
// v1.0.1: the control plane moved OFF the site's Supabase to its own Turso queue,
// reached through the mod Worker's secret-gated /cc/* routes. The site's AUTH can
// no longer be affected by the volunteer fleet (the 500MB wall that once broke
// login is gone: Turso = 5GB + 10M writes/mo). BYOK is unchanged — provider keys
// stay on the device and are never transmitted.
//
// ccSecret is a soft anti-spam gate (discoverable in any distributed binary); the
// real protections are the per-worker lease queue, the max_inflight cap, the
// operator block-switch, and the QA gate on returned text.

class Config {
  static const appName = 'מחשוב קהילתי';
  static const appVersion = '1.0.2';

  // The community-compute control plane — NOT the site.
  //
  // v1.0.2: Turso itself now hard-blocks reads (plan quota exceeded), so the
  // Worker/Turso route above is DEAD. The queue moved to the self-hosted
  // server on the Home Assistant machine (same secrets, byte-compatible
  // /cc/* contract, reached via a Cloudflare Tunnel).
  static const ccBase = 'https://pool.hebrew-translation-hub.com/cc';
  static const ccSecret = 'bff947baf4b340ec303dbabd377dd7aaa9f10ebc143ece3e';

  // label, keystore id, base url, model, where-to-get-key
  static const providers = [
    ['Groq', 'groq', 'https://api.groq.com/openai/v1', 'openai/gpt-oss-120b', 'console.groq.com/keys'],
    ['SambaNova', 'sambanova', 'https://api.sambanova.ai/v1', 'DeepSeek-V3.2', 'cloud.sambanova.ai'],
    ['NVIDIA NIM', 'nim', 'https://integrate.api.nvidia.com/v1', 'meta/llama-3.1-70b-instruct', 'build.nvidia.com'],
  ];

  // LINE-MODEL tuning. The queue hands out single LINES; we claim a bundle,
  // translate it in one batched provider call, submit the results in one call.
  //
  // ⚠️ claimBatch / renewEveryS below are only the STARTING values. The server
  // returns a live `config` on every enroll/claim/renew and the app OBEYS it
  // (see ServerConfig), so the operator can retune the whole fleet — e.g. raise
  // the heartbeat from 5 min as the device count grows — with NO app rebuild.
  static const claimBatch = 50;      // lines pulled per claim (server caps it)
  static const workBatch = 50;       // lines translated per provider round
  static const prefetchLines = 50;   // refill the local buffer below this
  static const renewEveryS = 300;    // heartbeat default (5 min) — server may override
  static const pollIdleS = 6;
  static const pollMaxS = 60;
}

/// The server's live tuning, refreshed from every control-plane reply.
/// One place to read it from, so a value can never go stale in two spots.
class ServerConfig {
  static int heartbeatS = Config.renewEveryS;
  static int leaseTtlS = 1200;
  static int batchSize = Config.claimBatch;
  static int maxInflight = 300;
  static bool blocked = false;

  static void apply(dynamic cfg) {
    if (cfg is! Map) return;
    int pick(String k, int cur, int lo, int hi) {
      final v = cfg[k];
      final n = (v is num) ? v.toInt() : int.tryParse('$v');
      if (n == null) return cur;
      return n < lo ? lo : (n > hi ? hi : n);
    }
    heartbeatS = pick('heartbeat_seconds', heartbeatS, 30, 3600);
    leaseTtlS = pick('lease_ttl_seconds', leaseTtlS, 60, 86400);
    batchSize = pick('batch_size', batchSize, 1, 200);
    maxInflight = pick('max_inflight', maxInflight, 1, 5000);
  }
}
