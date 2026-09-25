"""Tests for the security response headers added in app.py's _log_request
after_request hook (audits/security_audit.md Finding H1)."""


class TestSecurityHeaders:
    def test_json_api_response_gets_strict_headers(self, client):
        r = client.get("/api/health")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Content-Security-Policy"] == "default-src 'self'; frame-ancestors 'none'"
        assert r.headers["Referrer-Policy"] == "no-referrer"

    def test_docs_page_gets_relaxed_csp_for_its_own_cdn(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200
        csp = r.headers["Content-Security-Policy"]
        assert "unpkg.com" in csp
        assert "frame-ancestors 'none'" in csp
        # still not wide open
        assert "default-src 'self'" in csp
