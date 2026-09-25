"""Regression tests for api/app.py startup guards that don't fit the normal
Flask-test-client shape (audits/testing_audit.md Finding M2)."""
from app import _refuse_debug_in_production


class TestDebugProductionGuard:
    def test_raises_when_debug_and_production(self):
        try:
            _refuse_debug_in_production("1", "production")
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "FLASK_DEBUG=1" in str(exc)

    def test_allows_debug_in_development(self):
        _refuse_debug_in_production("1", "development")  # must not raise

    def test_allows_production_without_debug(self):
        _refuse_debug_in_production("0", "production")  # must not raise
