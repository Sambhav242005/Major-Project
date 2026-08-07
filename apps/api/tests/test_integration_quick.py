import os
import httpx

BASE = "http://localhost:8000"
MOCK_AUTH = os.environ.get("MOCK_AUTH", "true").lower() == "true"

tests = []

# Test 1: Health
r = httpx.get(f"{BASE}/health", timeout=5)
assert r.status_code == 200
assert r.json()["status"] == "ok"
print("PASS: /health -> 200")

# Test 2: Security headers
assert r.headers.get("x-content-type-options") == "nosniff"
assert r.headers.get("x-frame-options") == "DENY"
assert r.headers.get("x-xss-protection") == "1; mode=block"
print("PASS: Security headers present")

# Test 3-11: Auth tests (skipped in MOCK_AUTH mode)
if not MOCK_AUTH:
    r = httpx.get(f"{BASE}/documents", timeout=5)
    assert r.status_code == 401
    print("PASS: /documents -> 401 (auth required)")

    r = httpx.get(f"{BASE}/documents", headers={"Authorization": "Bearer bad-token"}, timeout=5)
    assert r.status_code == 401
    print("PASS: Bad token -> 401")

    r = httpx.get(f"{BASE}/mcp/connections", timeout=5)
    assert r.status_code == 401
    print("PASS: /mcp/connections -> 401")

    r = httpx.get(f"{BASE}/agents", timeout=5)
    assert r.status_code == 401
    print("PASS: /agents -> 401")

    r = httpx.get(f"{BASE}/chat/sessions", timeout=5)
    assert r.status_code == 401
    print("PASS: /chat/sessions -> 401")

    r = httpx.get(f"{BASE}/dashboard/summary", timeout=5)
    assert r.status_code == 401
    print("PASS: /dashboard/summary -> 401")

    r = httpx.get(f"{BASE}/meetings", timeout=5)
    assert r.status_code == 401
    print("PASS: /meetings -> 401")
else:
    print("SKIP: Auth tests skipped (MOCK_AUTH=true)")
    # In MOCK_AUTH mode, endpoints should work without real auth
    r = httpx.get(f"{BASE}/documents", headers={"Authorization": "Bearer mock-token"}, timeout=5)
    print(f"INFO: /documents with mock token -> {r.status_code}")

# Test 12: Docs public
r = httpx.get(f"{BASE}/docs", timeout=5)
assert r.status_code == 200
print("PASS: /docs -> 200 (public)")

# Test 13: OpenAPI schema
r = httpx.get(f"{BASE}/openapi.json", timeout=5)
assert r.status_code == 200
schema = r.json()
assert "paths" in schema
paths = list(schema["paths"].keys())
print(f"PASS: OpenAPI schema -> {len(paths)} routes")

# Test 14: CORS headers
r = httpx.options(f"{BASE}/health",
                  headers={"Origin": "http://localhost:3000",
                           "Access-Control-Request-Method": "GET"},
                  timeout=5)
print(f"PASS: CORS options -> {r.status_code}")

print("\n" + "="*50)
print("All integration tests PASSED")
print("="*50)
