"""Application-factory integration checks without listeners or external services.

Unlike the legacy localhost smoke scripts, these exercise the registered router
and middleware stack through Starlette's in-process ASGI transport. No model,
Supabase account, database contents, or running backend is required.
"""

import pytest
from fastapi.testclient import TestClient

from core.config import settings


@pytest.fixture
def client(monkeypatch):
    from app.factory import create_app

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "MOCK_AUTH", True)
    with TestClient(create_app()) as app_client:
        yield app_client


def test_public_health_has_security_headers(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in response.headers
    assert "permissions-policy" in response.headers


def test_csp_uses_configured_lan_origins(client, monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["https://192.168.1.100:13000"])
    policy = client.get("/health").headers["content-security-policy"]
    assert "connect-src 'self' https://192.168.1.100:13000;" in policy
    assert "http://localhost:8000" not in policy


@pytest.mark.parametrize(
    "path", ["/documents", "/chat/sessions", "/agents", "/mcp/connections"]
)
def test_protected_routes_require_token_before_database_access(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid Authorization header"


def test_allowed_cors_preflight_does_not_require_token(client):
    origin = settings.CORS_ORIGINS[0]
    response = client.options(
        "/documents",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_openapi_contains_registered_application_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in ("/health", "/documents", "/chat/sessions", "/agents", "/kb/search"):
        assert path in paths


def test_production_factory_disables_swagger_page(monkeypatch):
    from app.factory import create_app

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "MOCK_AUTH", False)
    app = create_app()
    assert app.docs_url is None
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404


def test_mock_identity_passes_middleware_without_external_auth(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer local-test"})
    assert response.status_code == 200
    assert response.json()["id"] == "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
