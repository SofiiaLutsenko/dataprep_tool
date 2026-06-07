import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

HEADERS = {"X-API-Key": "supersecretkey123"}


# --- Health ---

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- Text endpoint ---

def test_mask_text_success():
    response = client.post(
        "/api/v1/mask/text",
        json={"text": "Email: john@example.com, Phone: +1 555-123-4567"},
        headers=HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert "[EMAIL]" in data["masked_text"]
    assert "[PHONE]" in data["masked_text"]
    assert "john@example.com" not in data["masked_text"]
    assert "chars_processed" in data


def test_mask_text_empty():
    response = client.post(
        "/api/v1/mask/text",
        json={"text": ""},
        headers=HEADERS
    )
    assert response.status_code == 200


def test_mask_text_too_large():
    response = client.post(
        "/api/v1/mask/text",
        json={"text": "a" * 100_001},
        headers=HEADERS
    )
    assert response.status_code == 422


def test_mask_text_missing_field():
    response = client.post(
        "/api/v1/mask/text",
        json={},
        headers=HEADERS
    )
    assert response.status_code == 422


def test_mask_text_no_api_key():
    response = client.post(
        "/api/v1/mask/text",
        json={"text": "hello"}
    )
    assert response.status_code == 401


def test_mask_text_wrong_api_key():
    response = client.post(
        "/api/v1/mask/text",
        json={"text": "hello"},
        headers={"X-API-Key": "wrongkey"}
    )
    assert response.status_code == 401


# --- File endpoint ---

def test_mask_file_txt_success():
    content = b"Contact: hr@company.com, +49 151 12345678"
    response = client.post(
        "/api/v1/mask/file",
        files={"file": ("resume.txt", io.BytesIO(content), "text/plain")},
        headers=HEADERS
    )
    assert response.status_code == 200
    assert b"[EMAIL]" in response.content
    assert b"[PHONE]" in response.content


def test_mask_file_wrong_extension():
    response = client.post(
        "/api/v1/mask/file",
        files={"file": ("resume.pdf", io.BytesIO(b"some content"), "application/pdf")},
        headers=HEADERS
    )
    assert response.status_code == 415


def test_mask_file_binary_content():
    response = client.post(
        "/api/v1/mask/file",
        files={"file": ("data.txt", io.BytesIO(b"\x00\x01\x02\x03"), "text/plain")},
        headers=HEADERS
    )
    assert response.status_code == 422


def test_mask_file_too_large():
    large_content = b"a" * 100_001
    response = client.post(
        "/api/v1/mask/file",
        files={"file": ("big.txt", io.BytesIO(large_content), "text/plain")},
        headers=HEADERS
    )
    assert response.status_code == 413


def test_mask_file_no_api_key():
    content = b"Contact: hr@company.com"
    response = client.post(
        "/api/v1/mask/file",
        files={"file": ("resume.txt", io.BytesIO(content), "text/plain")}
    )
    assert response.status_code == 401