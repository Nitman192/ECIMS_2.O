"""Backward-compat wrappers for licensing module path.

New hardened licensing code lives in app.licensing_core.
"""

from app.licensing_core import *  # noqa: F401,F403
