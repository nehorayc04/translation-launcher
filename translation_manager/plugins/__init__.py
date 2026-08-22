"""
plugins - the launcher's cloud-delivered add-on system.

A plugin is an OPTIONAL feature the user can turn on WITHOUT reinstalling the
launcher. Its DEFINITION (name, description, version, icon, config schema, any
data it needs) is fetched from the CLOUD - nothing ships in the installer - and
"installing" it just registers + enables it locally.

Security by design: a plugin is DECLARATIVE data, never downloaded-and-executed
code. Each plugin `kind` is run by a built-in, audited HOST in this package
(`save_backup` is the first). So a hostile manifest can, at worst, mis-configure
a feature the app already knows how to run safely - it can never run arbitrary
code on the user's machine (which would defeat the whole signed-installer /
SHA-verified-download posture the launcher is built on).

Access: plugins are for a signed-in user who has bought at least one GAME
(not software) - enforced in `registry.can_use_plugins()` and re-checked by
every plugin RPC, never only in the UI.

Public surface (see registry.py):
    available()          # the cloud catalog of installable plugins
    installed()          # what this machine has installed + its config
    install(pid)         # register + enable a plugin (gated)
    remove(pid)          # unregister + stop
    set_enabled(pid, on)
    get_config(pid) / set_config(pid, cfg)
    can_use_plugins()    # the DRM gate
"""
from __future__ import annotations

from . import registry  # noqa: F401  (re-exported entry point)

# `host` is imported HERE on purpose, not left to the caller. Callers reach it
# as an ATTRIBUTE (`plugins.host.on_boot()`), and a submodule only becomes an
# attribute of its package once something imports it - so with `registry` alone
# in here, every `plugins.host.…` raised AttributeError. Each of those call
# sites is wrapped in a broad `except`, so the failure was completely silent:
# the scheduler never started at boot (only when a plugin was toggled, which
# imports host on the way through registry), and a background plugin therefore
# looked "on" while doing nothing until the user toggled it off and on again.
from . import host  # noqa: F401,E402  (attribute access: plugins.host.…)

__all__ = ["registry", "host"]
