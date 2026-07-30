# Intentionally failing test to trigger analyze-on-failure workflow
def test_demo_failure():
    assert False, "Intentional failure for CI demo"
