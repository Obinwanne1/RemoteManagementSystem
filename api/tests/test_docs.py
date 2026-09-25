"""Tests for routes/docs.py — public SwaggerUI + OpenAPI spec endpoints
(audits/testing_audit.md Finding C2)."""


class TestSwaggerUi:
    def test_serves_html_no_auth_required(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200
        assert b"swagger-ui" in r.data
        assert b"RMM Platform API" in r.data


class TestOpenApiSpec:
    def test_serves_json_no_auth_required(self, client):
        r = client.get("/api/openapi.json")
        assert r.status_code == 200
        body = r.get_json()
        assert isinstance(body, dict)
        assert "paths" in body
