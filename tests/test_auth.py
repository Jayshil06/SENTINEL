"""
Test Suite: Authentication & Session Security
Tests officer authentication, session cookie handling, /api/v1/auth/session, logout, and protected endpoints.
"""
import sys
import os
from fastapi.testclient import TestClient

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app

def test_login_success():
    """Verify valid credentials set sentinel_session cookie."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"badge": "GP-POL-001", "name": "Inspector ABC", "role": "Investigating Officer (IO)"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data.get("status") == "authenticated"
    assert data.get("badge") == "GP-POL-001"
    assert "sentinel_session" in response.cookies

def test_login_invalid_credentials():
    """Verify empty/invalid badge returns 400."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"badge": "  ", "name": "Unknown"}
    )
    assert response.status_code == 400
    assert "required" in response.json().get("detail", "").lower()

def test_auth_me_with_session():
    """Verify /api/v1/auth/session returns session information when authenticated."""
    client = TestClient(app)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"badge": "GP-POL-001", "name": "Inspector ABC"}
    )
    session_cookie = login_resp.cookies.get("sentinel_session")

    client.cookies.set("sentinel_session", session_cookie)
    me_resp = client.get("/api/v1/auth/session")
    assert me_resp.status_code == 200
    user_info = me_resp.json()
    assert user_info["authenticated"] is True
    assert user_info["badge"] == "GP-POL-001"

def test_auth_logout():
    """Verify /api/v1/auth/logout clears the session cookie."""
    client = TestClient(app)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"badge": "GP-POL-001", "name": "Inspector ABC"}
    )
    client.cookies.set("sentinel_session", login_resp.cookies.get("sentinel_session"))

    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json().get("status") == "logged_out"

def test_login_page_accessible():
    """Verify /login serves the login HTML page."""
    client = TestClient(app)
    response = client.get("/login")
    assert response.status_code == 200
    assert "SENTINEL" in response.text

if __name__ == "__main__":
    print("🚀 Running Authentication & Session Tests...")
    test_login_success()
    print("✅ Valid login verified.")
    test_login_invalid_credentials()
    print("✅ Invalid credentials rejection verified.")
    test_auth_me_with_session()
    print("✅ Session /api/v1/auth/session verified.")
    test_auth_logout()
    print("✅ Logout cookie clearing verified.")
    test_login_page_accessible()
    print("✅ Login HTML page verified.")
    print("🎉 All Authentication Tests Passed!")
