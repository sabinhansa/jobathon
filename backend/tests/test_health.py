import os

os.environ["DATABASE_URL"] = "sqlite:///./test_jobathon_health.db"

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_status_shape():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "model" in body
    assert "database" in body
    assert "ollama" in body
    assert "chroma" in body
