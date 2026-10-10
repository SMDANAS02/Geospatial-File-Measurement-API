from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_health_endpoint():
    """Verify GET /health returns 200 OK and expected structure."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_status"] == "connected"
    assert data["app_name"] == settings.PROJECT_NAME
    assert data["environment"] == settings.APP_ENV
    assert data["version"] == settings.VERSION
    assert "timestamp" in data


def test_api_v1_health_endpoint():
    """Verify versioned GET /api/v1/health returns 200 OK."""
    response = client.get(f"{settings.API_V1_STR}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_status"] == "connected"


def test_root_endpoint():
    """Verify root endpoint returns welcome message and links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["docs_url"] == "/docs"
    assert data["health_url"] == "/health"


def test_docs_endpoint():
    """Verify /docs endpoint loads properly with 200 OK."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "swagger" in response.text.lower()
