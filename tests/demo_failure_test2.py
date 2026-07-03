def test_demo_failure_branch():
    # Intentional failure for PR-triggered CI analysis.
    assert 1 + 1 == 3
