// Static, non-bundled bindings — eel's HTML/JS scanner parses this file
// directly to discover @eel.expose names. The bundled React code only writes
// to / reads from the registries below; it never calls eel.expose() itself,
// because the bundler may emit string literals as backticks which eel's
// parser then mis-captures.

// ── Download progress (existing) ─────────────────────────────
window.__eelDLHandlers = [];

function update_download_progress(itemId, pct, speed, state) {
  var list = window.__eelDLHandlers || [];
  for (var i = 0; i < list.length; i++) {
    try { list[i](itemId, pct, speed, state); } catch (e) { /* swallow */ }
  }
}

// ── SWR cache push (new) ─────────────────────────────────────
// Python calls eel.cache_refreshed(kind, data, subKey)() whenever the
// background SWR refresh notices the server returned different data.
// React components register a callback into __eelCacheHandlers via the
// useSWRSource hook to get live updates without polling.
window.__eelCacheHandlers = [];

function cache_refreshed(kind, data, subKey) {
  var list = window.__eelCacheHandlers || [];
  for (var i = 0; i < list.length; i++) {
    try { list[i](kind, data, subKey); } catch (e) { /* swallow */ }
  }
}

(function register() {
  if (window.eel && typeof window.eel.expose === "function") {
    eel.expose(update_download_progress, "update_download_progress");
    eel.expose(cache_refreshed,          "cache_refreshed");
  } else {
    setTimeout(register, 50);
  }
})();
