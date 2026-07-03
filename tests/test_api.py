from unittest.mock import patch

from app.routers import analyze as analyze_router


def _mock_generate_success(self, prompt: str) -> str:
    return (
        '{"root_cause": "module not found: requests", "affected_component": "pip install", '
        '"fix_suggestion": "add requests to requirements.txt", "confidence_level": 0.85, '
        '"additional_context": ""}'
    )


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@patch.object(analyze_router._gemini_client.__class__, "generate", _mock_generate_success)
def test_analyze_endpoint_success(client):
    payload = {
        "pipeline_name": "build-and-test",
        "log": "ModuleNotFoundError: No module named 'requests'",
        "repository": "org/repo",
        "commit_sha": "abc123",
    }
    resp = client.post("/analyze", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ANALYZED"
    assert "requests" in body["root_cause"]
    assert body["low_confidence_warning"] is False


def test_analyze_endpoint_validates_input(client):
    resp = client.post("/analyze", json={"pipeline_name": "", "log": ""})
    assert resp.status_code == 422


@patch.object(analyze_router._gemini_client.__class__, "generate", _mock_generate_success)
def test_reports_pagination(client):
    payload = {"pipeline_name": "ci", "log": "some error"}
    for _ in range(3):
        client.post("/analyze", json=payload)

    resp = client.get("/reports?page=1&page_size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


@patch.object(analyze_router._gemini_client.__class__, "generate", _mock_generate_success)
def test_get_single_report(client):
    payload = {"pipeline_name": "ci", "log": "some error"}
    client.post("/analyze", json=payload)

    list_resp = client.get("/reports")
    report_id = list_resp.json()["items"][0]["id"]

    resp = client.get(f"/reports/{report_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == report_id


def test_get_nonexistent_report_404(client):
    resp = client.get("/reports/99999")
    assert resp.status_code == 404
