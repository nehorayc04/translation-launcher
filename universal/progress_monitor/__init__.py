"""Universal progress monitor.

Push per-game progress snapshots to /api/admin/progress for any project
(extraction, translation, packaging, QA, deployment, …) regardless of
which game it is.
"""
from .core import Monitor, Snapshot, Stage  # noqa: F401
