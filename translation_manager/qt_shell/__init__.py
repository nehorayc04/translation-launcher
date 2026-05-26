"""
qt_shell — PySide6 host that replaces the Eel/Chromium shell.

Strangler-fig migration: the React frontend in frontend/dist/ is loaded
into a QWebEngineView; Python ↔ JS RPC goes through QWebChannel instead
of Eel's gevent WebSocket. All backend modules (auth, game_mod,
swr_cache, etc.) are reused unchanged through main_eel.py with the eel
import shimmed out — see eel_shim.py.
"""
