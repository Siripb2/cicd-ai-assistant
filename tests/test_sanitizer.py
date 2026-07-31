from app.services.sanitizer import sanitize_log, truncate_log


def test_redacts_api_key():
    raw = "Build started\nAPI_KEY=sk-abcdef1234567890\nBuild finished"
    out = sanitize_log(raw)
    assert "sk-abcdef1234567890" not in out
    assert "REDACTED" in out


def test_redacts_github_token():
    raw = "Using token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
    out = sanitize_log(raw)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890" not in out


def test_redacts_bearer_token():
    raw = "Authorization: Bearer abc123.def456.ghi789"
    out = sanitize_log(raw)
    assert "abc123.def456.ghi789" not in out


def test_leaves_normal_log_untouched():
    raw = "Running tests...\n5 passed in 1.2s"
    assert sanitize_log(raw) != raw


def test_truncate_keeps_tail():
    raw = "x" * 100
    out = truncate_log(raw, max_chars=10)
    assert out.endswith("x" * 10)
    assert "truncated" in out


def test_truncate_noop_when_short():
    raw = "short log"
    assert truncate_log(raw, max_chars=100) == raw
