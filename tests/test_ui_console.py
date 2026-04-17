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
    assert "Configuration Studio" in response.text
    assert "Low-code configuration" in response.text
    assert "New Agent" in response.text
    assert "New Workflow" in response.text
    assert "Talk to LeadBot" in response.text
    assert "Send to LeadBot" in response.text
    assert "Send & Apply" in response.text
    assert "Reset Thread" in response.text
    assert "Apply to Studio" in response.text
    assert "Vibe Prompts" in response.text
    assert "Manifest Impact" in response.text
    assert "Workflow Review" in response.text
    assert "Flow Composer" in response.text
    assert "Drag steps to reorder" in response.text
    assert "Template System" in response.text
    assert "Researcher, Developer, QA, Publisher" in response.text
    assert "Run Controls" in response.text
    assert "Step Controls" in response.text
    assert "Apply Run Status" in response.text
    assert "Update Step" in response.text
    assert "OpenClaw Export" in response.text
    assert "Copy JSON" in response.text
