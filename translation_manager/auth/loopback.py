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
  • Binding to 127.0.0.1 (NOT 0.0.0.0) - only the local user can
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

import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse


# Fixed loopback port. Supabase's Redirect URLs whitelist must contain
# `http://localhost:8085/auth/callback` exactly - Supabase's GoTrue
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
    """HTTPServer that (1) sets SO_REUSEADDR so a freshly-aborted listener can
    rebind to port 8085 immediately (rapid Cancel → Google → Cancel cycles
    would otherwise hit `OSError: Address already in use` in TIME_WAIT), and
    (2) is built on an UNPATCHED (original) stdlib socket so its serve thread
    needs NO gevent hub.

    main_eel monkey-patches the `socket` module process-wide. A patched socket
    does its blocking accept()/recv() COOPERATIVELY and REQUIRES a running
    gevent hub on its thread - which a plain daemon thread (or, under Qt, a
    freshly-spawned native OS thread on the 2nd login attempt) does not
    reliably have. That was the "browser opens the first time, then never
    again" bug. Using the pristine stdlib socket makes the whole serve loop
    ordinary blocking I/O that behaves identically in BOTH the Eel and the
    shipped Qt build, on every attempt."""
    allow_reuse_address = True

    def __init__(self, server_address, handler_cls):
        # Grab the pristine (pre-monkey-patch) socket class so the serve
        # thread's accept() is a real blocking call, not a hub-bound greenlet op.
        try:
            from gevent.monkey import get_original
            orig_socket_cls = get_original('socket', 'socket')
        except Exception:
            import socket as _s
            orig_socket_cls = _s.socket
        # Defer bind so we can swap the (patched) socket the base __init__
        # creates for the pristine one BEFORE binding/listening.
        super().__init__(server_address, handler_cls, bind_and_activate=False)
        try:
            self.socket.close()
        except Exception:
            pass
        self.socket = orig_socket_cls(self.address_family, self.socket_type)
        # allow_reuse_address=True → server_bind() sets SO_REUSEADDR itself.
        self.server_bind()
        self.server_activate()


# NOTE: these MUST be Unicode strings encoded to bytes at module level -
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
  <p>חזור ללאנצ’ר - אפשר לסגור את החלון הזה.<span class="pulse"></span></p>
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

    No `state` field - we no longer send a client-supplied state on
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
    """Custom request handler - captures /auth/callback params and ends the wait."""

    # Set on the server instance by LoopbackListener.__enter__ below.
    # `result` is the captured CallbackResult; `done_event` is the
    # caller's wakeup signal. No `expected_state` - we no longer send
    # a client-supplied state on the authorize URL (it conflicts with
    # Supabase GoTrue's own state cookie).
    result: Optional[CallbackResult] = None
    done_event: Optional[threading.Event] = None

    def log_message(self, fmt, *args):
        # Silence default stderr logging - this is a launcher, not a server.
        pass

    def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        if parsed.path not in ('/auth/callback', '/auth/callback/'):
            self.send_response(404)
            self.end_headers()
            return

        qs = parse_qs(parsed.query)
        code  = (qs.get('code')  or [None])[0]
        err   = (qs.get('error') or [None])[0]
        err_d = (qs.get('error_description') or [None])[0]
        # `state` is deliberately ignored - see CallbackResult docstring.

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


def _cooperative_sleep(seconds: float) -> None:
    """Sleep that yields the gevent hub under Eel but plain-sleeps under Qt.

    Under Eel, login() runs as a GREENLET on the main gevent hub - a blocking
    time.sleep there would freeze the whole hub, so auth_abort_login could
    never dispatch (the "בטל וחזור does nothing for 180s" freeze). gevent.sleep
    yields. Under Qt (PySide6 loaded), login() runs on a NATIVE OS thread with
    no hub, so a plain time.sleep is correct and avoids spinning a throwaway
    per-thread gevent hub - the fragility behind "browser opens once, then not
    again". `'PySide6' in sys.modules` is the build discriminator (the Eel dev
    build never imports PySide6)."""
    if 'PySide6' not in sys.modules:
        try:
            import gevent                                                     # type: ignore[import-not-found]
            gevent.sleep(seconds)
            return
        except Exception:
            pass
    time.sleep(seconds)


class LoopbackListener:
    """One-shot loopback HTTP server on 127.0.0.1:8085 for the OAuth redirect.
    Pinned to LOOPBACK_PORT (8085) because Supabase's URL Configuration must
    whitelist the exact redirect - wildcard ports trigger a fallback to the
    project's Site URL instead of the loopback.

    Built to be gevent-INDEPENDENT so it behaves identically in both builds:
      • The serve loop runs on a PLAIN daemon OS thread doing ordinary blocking
        accept() on an UNPATCHED socket - no gevent hub required. (A gevent
        greenlet or a patched socket needs a running hub on its thread; under
        Qt, login() runs on a fresh native thread whose per-attempt throwaway
        hub was the "opens once, wedges the 2nd time" bug.)
      • abort() and the callback both signal PLAIN threading.Events, so the
        cross-thread signal (the Qt GUI thread aborts a login running on a
        worker thread) is standard, thread-safe threading - never a cross-thread
        gevent .set() (which hangs libev's non-thread-safe run_callback).
      • await_code() polls those Events with a COOPERATIVE sleep (gevent.sleep
        under Eel, time.sleep under Qt) so the wait never freezes the Eel hub."""

    def __init__(self) -> None:
        self.port  = LOOPBACK_PORT
        # Plain threading.Events - safe to set/read across ANY threads in BOTH
        # builds (no gevent involvement, so no cross-thread-hub hazard).
        self._captured  = threading.Event()   # set by the HTTP handler on callback
        self._cancelled = threading.Event()   # set by abort() / __exit__
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def redirect_uri(self) -> str:
        # The advertised hostname is `localhost`, not `127.0.0.1`.
        # Supabase's GoTrue rejects bare IP loopbacks in its redirect
        # allowlist matching even when the URL is listed - but it
        # accepts `localhost:<port>`. The browser resolves localhost
        # back to 127.0.0.1 (where we're actually listening) so the
        # callback still lands on our HTTP server.
        return f'http://{LOOPBACK_HOST_ADVERTISE}:{self.port}/auth/callback'

    def __enter__(self) -> 'LoopbackListener':
        # Bind explicitly to 127.0.0.1 - NOT 0.0.0.0 - so only the local user
        # can deliver the callback. _ReuseHTTPServer builds on an UNPATCHED
        # socket + SO_REUSEADDR (rapid abort→retry never hits TIME_WAIT).
        # Short bind RETRY: a just-cancelled attempt may still be releasing
        # port 8085 for a few ms; SO_REUSEADDR usually covers it, but retry so
        # a rapid cancel→retry never dead-ends with "browser never opens".
        self._httpd = None
        last_err: Optional[BaseException] = None
        for _attempt in range(5):
            try:
                self._httpd = _ReuseHTTPServer((LOOPBACK_HOST_BIND, self.port), _Handler)
                break
            except OSError as e:
                last_err = e
                self._httpd = None
                time.sleep(0.2)
        if self._httpd is None:
            raise last_err if last_err is not None else OSError('could not bind loopback :8085')
        # Park per-server slots on the HTTPServer instance so the handler
        # (constructed fresh per request) can read/write them.
        self._httpd.result = None                 # type: ignore[attr-defined]
        self._httpd.done_event = self._captured   # type: ignore[attr-defined]
        # PLAIN daemon OS thread - real blocking accept() on the unpatched
        # socket, no gevent hub. Identical in Eel and Qt, every attempt.
        self._thread = threading.Thread(
            target=self._serve_loop, name="oauth-loopback", daemon=True)
        self._thread.start()
        return self

    def _serve_loop(self) -> None:
        """Plain blocking accept loop on the unpatched socket. No gevent.

        settimeout(0.3) makes accept() return roughly every 0.3s so the loop
        re-checks the cancel/captured flags promptly. Each accepted request is
        processed synchronously (BaseHTTPRequestHandler → _Handler.do_GET),
        which sets self._captured via the handler's done_event."""
        srv = self._httpd
        if srv is None:
            return
        try:
            srv.socket.settimeout(0.3)
        except Exception:
            pass
        while not self._captured.is_set() and not self._cancelled.is_set():
            try:
                request, client_addr = srv.get_request()   # blocking accept (0.3s timeout)
            except OSError:
                # socket.timeout (no connection) OR socket closed on teardown →
                # loop back and re-check the flags. Never kills the loop.
                continue
            try:
                request.settimeout(None)   # the callback exchange must fully block
            except Exception:
                pass
            try:
                srv.process_request(request, client_addr)   # → _Handler.do_GET (sync)
            except Exception:
                try: srv.shutdown_request(request)          # type: ignore[attr-defined]
                except Exception: pass

    def await_code(self, timeout: float = 120.0) -> CallbackResult:
        """Block (cooperatively) until the browser hits /auth/callback, abort()
        is called from another thread, or timeout - whichever comes first. Each
        terminus produces a distinct CallbackResult so the caller can branch.

        Polls plain threading.Events with a cooperative sleep so it NEVER
        freezes the Eel hub (login() there is a greenlet) yet stays a cheap
        native poll under Qt (login() there is an OS thread)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._captured.is_set() or self._cancelled.is_set():
                break
            _cooperative_sleep(0.05)
        if self._cancelled.is_set():
            return CallbackResult(
                code=None, error='cancelled',
                error_description='Sign-in cancelled by user',
            )
        if not self._captured.is_set():
            return CallbackResult(
                code=None, error='timeout',
                error_description='User did not complete sign-in within %d seconds' % int(timeout),
            )
        return getattr(self._httpd, 'result', None) or CallbackResult(
            code=None, error='no_callback', error_description='no result captured',
        )

    def abort(self) -> None:
        """Cancel a pending login. SAFE from ANY thread (the Qt GUI thread
        calls it CROSS-THREAD): sets a PLAIN threading.Event that both the
        serve loop and await_code poll. No gevent primitive is ever touched
        across threads, so there is no libev run_callback hazard. Idempotent."""
        self._cancelled.set()

    def __exit__(self, exc_type, exc, tb) -> None:
        # Signal the serve loop to stop (idempotent with abort()).
        self._cancelled.set()
        # Wait for the serve thread to exit. With a 0.3s accept() timeout it
        # notices within ~300ms - the 2s cap is defence-in-depth.
        if self._thread is not None:
            try:
                self._thread.join(timeout=2.0)
            except Exception:
                pass
        # Close the socket after the loop is gone so we never race the serve
        # thread's accept() against server_close.
        if self._httpd is not None:
            try: self._httpd.server_close()
            except Exception: pass
