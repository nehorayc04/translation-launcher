"""
One-shot HTTP server on http://127.0.0.1:<random-port>/auth/callback.

Used as the OAuth redirect target for the launcher (RFC 8252 §7.3,
"loopback interface redirection"). Lifecycle:

  1. Caller opens a free port via OS allocation (port=0).
  2. Starts the server in a daemon thread.
  3. Opens the system browser to the OAuth authorize URL with
     redirect_to=http://127.0.0.1:<port>/auth/callback.
  4. After Google + Supabase finish their dance, the browser is
     redirected back here with ?code=...&state=... or ?error=...
  5. Server captures the params, returns a small "you can close
     this tab" HTML page, then shuts itself down on the next tick.

Security notes:
  • Binding to 127.0.0.1 (NOT 0.0.0.0) — only the local user can
    talk to us. Other machines on the LAN cannot intercept the
    code.
  • A `state` token is generated per login and checked on callback
    to defend against cross-origin request forgery on the
    redirect.
  • The whole listener exits within ~120 s whether or not a
    callback arrives; the caller's `await_code()` re-raises a
    timeout so the UI can show "login cancelled".
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse


# Fixed loopback port. Supabase's Redirect URLs whitelist must contain
# `http://localhost:8085/auth/callback` exactly — Supabase's GoTrue
# engine often REJECTS bare IPs (127.0.0.1) for desktop OAuth loopbacks
# and falls back to the project's Site URL on mismatch, which is why
# the launcher used to send users to the Vercel homepage instead of
# completing the OAuth handshake. We bind the server to 127.0.0.1
# (loopback only, no LAN exposure) but ADVERTISE the redirect URI as
# `localhost` because the browser resolves both to the same socket
# while Supabase only accepts the hostname form.
LOOPBACK_HOST_BIND     = '127.0.0.1'   # what we listen on (security)
LOOPBACK_HOST_ADVERTISE = 'localhost'  # what we tell Supabase + browser
LOOPBACK_PORT          = 8085


class _ReuseHTTPServer(HTTPServer):
    """HTTPServer with SO_REUSEADDR so a freshly-aborted listener can
    rebind to port 8085 immediately — otherwise rapid Cancel → Google
    → Cancel cycles would hit `OSError: Address already in use` while
    the OS holds the socket in TIME_WAIT."""
    allow_reuse_address = True


# NOTE: these MUST be Unicode strings encoded to bytes at module level —
# Python bytes literals (b"...") may only contain ASCII. Embedding Hebrew
# directly inside b"""...""" is a hard SyntaxError. We keep the source
# as a regular triple-quoted str and call .encode('utf-8') once so the
# wire-format bytes are still ready at import time.
_SUCCESS_HTML = """<!doctype html>
<html lang="he" dir="rtl"><head>
<meta charset="utf-8"><title>התחברות הושלמה</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; min-height:100vh; display:grid; place-items:center;
         background:
           radial-gradient(circle at 50% 30%, rgba(0,255,224,0.15), transparent 60%),
           #050510;
         font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial; color:#e2e8f0; }
  .card { text-align:center; padding:40px 48px; border-radius:20px;
          background:rgba(15,15,30,0.55); backdrop-filter: blur(20px);
          border:1px solid rgba(255,255,255,0.08);
          box-shadow:0 30px 60px -20px rgba(0,0,0,0.7);
          max-width:420px; }
  .badge { width:48px; height:48px; border-radius:14px; display:inline-grid; place-items:center;
           background:#00ffe0; color:#0a0a14; font-weight:800; font-size:22px;
           box-shadow:0 4px 20px -4px rgba(0,255,224,0.5); margin-bottom:14px; }
  h1 { margin:0 0 6px; font-size:22px; }
  p  { margin:0; color:#94a3b8; font-size:14px; line-height:1.6; }
  .pulse { display:inline-block; width:6px; height:6px; background:#00ffe0; border-radius:50%;
           margin-left:6px; animation: pulse 1.2s ease-in-out infinite; vertical-align:middle; }
  @keyframes pulse { 0%,100% { opacity:0.3; } 50% { opacity:1; } }
</style></head>
<body><div class="card">
  <div class="badge">✓</div>
  <h1>ההתחברות הושלמה</h1>
  <p>חזור ללאנצ’ר — אפשר לסגור את החלון הזה.<span class="pulse"></span></p>
</div></body></html>
""".encode('utf-8')

_ERROR_HTML = """<!doctype html>
<html lang="he" dir="rtl"><head>
<meta charset="utf-8"><title>ההתחברות נכשלה</title>
<style>
  body { margin:0; min-height:100vh; display:grid; place-items:center;
         background:#050510; font-family: system-ui, sans-serif; color:#fda4af; }
  .card { text-align:center; padding:32px 40px; border-radius:16px;
          background:rgba(120,30,40,0.15); border:1px solid rgba(244,63,94,0.3); }
</style></head>
<body><div class="card">
  <h1>ההתחברות נכשלה</h1>
  <p>סגור את החלון הזה ונסה שוב מהלאנצ’ר.</p>
</div></body></html>
""".encode('utf-8')


@dataclass
class CallbackResult:
    """Captured query params from the OAuth redirect.

    No `state` field — we no longer send a client-supplied state on
    the authorize URL (it conflicts with Supabase GoTrue's own
    sb-provider-state cookie verification and causes the entire flow
    to fail with `bad_oauth_state`). CSRF protection on the loopback
    relies entirely on the PKCE code_verifier: only this process
    knows the verifier, so even if a stranger forged a hit on our
    /auth/callback the auth_code can't be redeemed for tokens."""
    code:  Optional[str]
    error: Optional[str]
    error_description: Optional[str]


class _Handler(BaseHTTPRequestHandler):
    """Custom request handler — captures /auth/callback params and ends the wait."""

    # Set on the server instance by LoopbackListener.__enter__ below.
    # `result` is the captured CallbackResult; `done_event` is the
    # caller's wakeup signal. No `expected_state` — we no longer send
    # a client-supplied state on the authorize URL (it conflicts with
    # Supabase GoTrue's own state cookie).
    result: Optional[CallbackResult] = None
    done_event: Optional[threading.Event] = None

    def log_message(self, fmt, *args):
        # Silence default stderr logging — this is a launcher, not a server.
        pass

    def do_GET(self):  # noqa: N802 — required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        if parsed.path not in ('/auth/callback', '/auth/callback/'):
            self.send_response(404)
            self.end_headers()
            return

        qs = parse_qs(parsed.query)
        code  = (qs.get('code')  or [None])[0]
        err   = (qs.get('error') or [None])[0]
        err_d = (qs.get('error_description') or [None])[0]
        # `state` is deliberately ignored — see CallbackResult docstring.

        srv = self.server  # type: ignore[assignment]
        srv.result = CallbackResult(  # type: ignore[attr-defined]
            code=code, error=err, error_description=err_d,
        )

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        body = _SUCCESS_HTML if (code and not err) else _ERROR_HTML
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

        # Tell the caller we have the goods. The server itself is
        # shut down by LoopbackListener.__exit__.
        if srv.done_event:  # type: ignore[attr-defined]
            srv.done_event.set()  # type: ignore[attr-defined]


class LoopbackListener:
    """One-shot loopback HTTP server, started + stopped by the caller.
    Pinned to LOOPBACK_PORT (8085) because Supabase's URL Configuration
    must whitelist the exact redirect — wildcard ports trigger a
    fallback to the project's Site URL instead of the loopback."""

    def __init__(self) -> None:
        # Use gevent.event.Event explicitly — NOT threading.Event.
        # await_code() calls self._done.wait(timeout) from inside a
        # greenlet (the auth-login worker spawned via gevent.spawn).
        # threading.Event.wait is a native blocking call that pins
        # the entire OS thread, including the gevent hub — Eel's
        # websocket loop stalls, the serve-loop greenlet can't run,
        # and the React UI freezes until the timeout expires.
        # gevent.event.Event.wait yields cooperatively so the hub
        # stays alive and every other greenlet (serve loop, abort
        # bridge, copy-link bridge) keeps dispatching.
        import gevent.event                                                       # type: ignore[import-not-found]
        self.port  = LOOPBACK_PORT
        self._done = gevent.event.Event()
        self._httpd: Optional[HTTPServer] = None
        # _greenlet runs the non-blocking serve loop. Typed loosely
        # because gevent.Greenlet isn't available at type-checking
        # time.
        self._greenlet = None
        # Aborted flag: True iff abort() was called and we should
        # treat any pending await_code wait as cancelled rather than
        # as a real callback.
        self._aborted = False

    @property
    def redirect_uri(self) -> str:
        # The advertised hostname is `localhost`, not `127.0.0.1`.
        # Supabase's GoTrue rejects bare IP loopbacks in its redirect
        # allowlist matching even when the URL is listed — but it
        # accepts `localhost:<port>`. The browser resolves localhost
        # back to 127.0.0.1 (where we're actually listening) so the
        # callback still lands on our HTTP server.
        return f'http://{LOOPBACK_HOST_ADVERTISE}:{self.port}/auth/callback'

    def __enter__(self) -> 'LoopbackListener':
        # Bind explicitly to 127.0.0.1 — NOT 0.0.0.0 — so only the local
        # user can deliver the callback. _ReuseHTTPServer sets
        # SO_REUSEADDR so a rapid abort→retry sequence doesn't fail
        # with "Address already in use" while the OS holds TIME_WAIT.
        self._httpd = _ReuseHTTPServer((LOOPBACK_HOST_BIND, self.port), _Handler)
        # Park per-server slots on the HTTPServer instance so the handler
        # (which is constructed fresh per request) can read/write them.
        self._httpd.result = None                # type: ignore[attr-defined]
        self._httpd.done_event = self._done      # type: ignore[attr-defined]
        # handle_request() blocks waiting for a connection up to this
        # many seconds, then returns. Short enough that abort() is
        # responsive without needing a dummy self-request hack; long
        # enough to amortize syscall overhead while idle.
        self._httpd.timeout = 0.2                # type: ignore[attr-defined]

        # CRITICAL: spawn the serve loop as a GREENLET, not a native
        # thread. Eel/gevent monkey-patches the socket module, so the
        # patched socket inside handle_request() needs the gevent hub —
        # running it on a native OS thread would deadlock the first
        # inbound connection. The greenlet's loop body explicitly
        # yields via gevent.sleep(0.05) so the Eel websocket loop
        # keeps dispatching frontend bridge calls (auth_abort_login,
        # auth_get_authorize_url) while we're waiting for the
        # callback.
        import gevent                                                              # type: ignore[import-not-found]
        self._greenlet = gevent.spawn(self._serve_loop)
        return self

    def _serve_loop(self) -> None:
        """Non-blocking serve loop. Replaces serve_forever() so the
        Eel/gevent hub never wedges. Each iteration:
          1. handle_request()  → blocks up to httpd.timeout (0.2s)
                                 for an inbound connection.
          2. gevent.sleep(0.05) → explicit cooperative yield.

        Exits when _done is set (handler captured a callback) or when
        _aborted flips true (user clicked בטל וחזור). Worst-case
        responsiveness to either: ~250ms."""
        import gevent                                                              # type: ignore[import-not-found]
        httpd = self._httpd
        while not self._done.is_set() and not self._aborted:
            try:
                httpd.handle_request()  # type: ignore[union-attr]
            except Exception:
                # Per-request error must not kill the loop — a valid
                # callback might still arrive on a later request.
                pass
            gevent.sleep(0.05)

    def await_code(self, timeout: float = 120.0) -> CallbackResult:
        """Block until the browser hits /auth/callback, until abort()
        is called from another greenlet, or until timeout — whichever
        comes first. Each terminus produces a distinct CallbackResult
        so the caller can branch.

        Runs in the login() greenlet. self._done.wait() is monkey-
        patched to be gevent-cooperative, so the wait yields the hub
        — which means the serve-loop greenlet keeps running and can
        actually fire the _done event when a request lands."""
        if not self._done.wait(timeout):
            return CallbackResult(
                code=None, error='timeout',
                error_description='User did not complete sign-in within %d seconds' % int(timeout),
            )
        if self._aborted:
            return CallbackResult(
                code=None, error='cancelled',
                error_description='Sign-in cancelled by user',
            )
        return getattr(self._httpd, 'result', None) or CallbackResult(
            code=None, error='no_callback', error_description='no result captured',
        )

    def abort(self) -> None:
        """Release any blocked await_code() caller immediately. Just
        sets the two flags — the serve loop notices on its next
        iteration (within ~250ms, given timeout=0.2 + sleep 0.05) and
        exits cleanly on its own. No self-request hack required, and
        no separate teardown thread: the socket close is handled by
        __exit__ when the worker's `with LoopbackListener()` block
        unwinds. Idempotent."""
        if self._aborted:
            return
        self._aborted = True
        self._done.set()

    def __exit__(self, exc_type, exc, tb) -> None:
        # Signal the serve loop to stop (idempotent with abort()).
        self._aborted = True
        self._done.set()
        # Wait for the greenlet to exit. With handle_request timeout
        # of 0.2s + a 0.05s explicit yield, the loop notices and
        # exits within ~250ms — the 2s cap is just defence-in-depth.
        if self._greenlet is not None:
            try:
                self._greenlet.join(timeout=2.0)
            except Exception:
                pass
        # Close the socket after the loop is gone so we never race
        # the greenlet's handle_request against server_close.
        if self._httpd is not None:
            try: self._httpd.server_close()
            except Exception: pass
