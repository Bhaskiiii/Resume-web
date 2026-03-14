import pytest
import httpx
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_contact_submission():
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "1234567890",
        "message": "This is a test message from automated tests."
    }
    # Note: This might fail if MongoDB is not running and SQLite fails, 
    # but the code has fallbacks.
    response = client.post("/api/contact", json=payload)
    assert response.status_code == 201
    assert response.json()["status"] == "success"

def test_contact_validation_error():
    payload = {
        "name": "T", # Too short
        "email": "invalid-email",
        "message": "" # Too short
    }
    response = client.post("/api/contact", json=payload)
    assert response.status_code == 422
