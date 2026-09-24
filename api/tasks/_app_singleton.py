"""Shared Flask app singleton for Celery task modules.

Every task module needs a Flask app context to touch the DB, but calling
create_app() once per task invocation exhausted the DB connection pool under
load (the original Tier-1 fix). That fix was previously copy-pasted
identically into 15 separate task files — this module centralizes it so
future task files import get_app() instead of re-deriving the same
boilerplate (and risk forgetting it, silently reintroducing the pool
exhaustion bug).

Safe under Celery's `--pool=solo` (single-threaded, per CLAUDE.md). Not safe
if the worker pool mode is ever changed to prefork/threads/gevent without
adding a lock around the write below.
"""
_app = None


def get_app():
    global _app
    if _app is None:
        from app import create_app
        _app = create_app()
    return _app
