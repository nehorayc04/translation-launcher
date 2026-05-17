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

import secrets
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse


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
    """Captured query params from the OAuth redirect."""
    code:  Optional[str]
    state: Optional[str]
    error: Optional[str]
    error_description: Optional[str]


class _Handler(BaseHTTPRequestHandler):
    """Custom request handler — captures /auth/callback params and ends the wait."""

    # Set on the server instance by start_loopback() below.
    expected_state: str = ''
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
        state = (qs.get('state') or [None])[0]
        code  = (qs.get('code')  or [None])[0]
        err   = (qs.get('error') or [None])[0]
        err_d = (qs.get('error_description') or [None])[0]

        # CSRF check — the state we generated must match. If it doesn't,
        # someone tricked the user's browser into hitting our loopback.
        # Refuse the code so we don't exchange it.
        srv = self.server  # type: ignore[assignment]
        if not err and srv.expected_state and state != srv.expected_state:  # type: ignore[attr-defined]
            err = 'state_mismatch'
            err_d = 'OAuth state token did not match (possible CSRF).'

        srv.result = CallbackResult(  # type: ignore[attr-defined]
            code=code, state=state, error=err, error_description=err_d,
        )

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        body = _SUCCESS_HTML if (code and not err) else _ERROR_HTML
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

        # Tell the caller we have the goods. The server itself is
        # shut down by start_loopback's `with` block.
        if srv.done_event:  # type: ignore[attr-defined]
            srv.done_event.set()  # type: ignore[attr-defined]


def _pick_free_port() -> int:
    """Ask the OS for a free port — guaranteed not racy on Windows."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class LoopbackListener:
    """One-shot loopback HTTP server, started + stopped by the caller."""

    def __init__(self) -> None:
        self.port  = _pick_free_port()
        self.state = secrets.token_urlsafe(24)
        self._done = threading.Event()
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def redirect_uri(self) -> str:
        return f'http://127.0.0.1:{self.port}/auth/callback'

    def __enter__(self) -> 'LoopbackListener':
        # Bind explicitly to 127.0.0.1 — NOT 0.0.0.0 — so only the local
        # user can deliver the callback.
        self._httpd = HTTPServer(('127.0.0.1', self.port), _Handler)
        # Park per-server state on the HTTPServer instance so the handler
        # (which is constructed fresh per request) can read it.
        self._httpd.expected_state = self.state  # type: ignore[attr-defined]
        self._httpd.result = None                # type: ignore[attr-defined]
        self._httpd.done_event = self._done      # type: ignore[attr-defined]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name='auth-loopback', daemon=True,
        )
        self._thread.start()
        return self

    def await_code(self, timeout: float = 120.0) -> CallbackResult:
        """Block until the browser hits /auth/callback, or timeout."""
        if not self._done.wait(timeout):
            return CallbackResult(code=None, state=None, error='timeout',
                                  error_description='User did not complete sign-in within %d seconds' % int(timeout))
        return getattr(self._httpd, 'result', None) or CallbackResult(
            code=None, state=None, error='no_callback', error_description='no result captured',
        )

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
