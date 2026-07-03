def test_demo_failure():
    # Intentionally failing test to trigger analyze-on-failure workflow
    assert False, "Intentional failure for CI demo"
