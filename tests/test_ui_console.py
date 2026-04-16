from fastapi.testclient import TestClient

from app.main import app


def test_root_redirects_to_console():
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/studio/console"


def test_console_page_renders():
    client = TestClient(app)

    response = client.get("/studio/console")

    assert response.status_code == 200
    assert "LeadBot Studio Console" in response.text
    assert "/studio/summary" in response.text
