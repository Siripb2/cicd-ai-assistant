# Intentionally failing test to trigger analyze-on-failure workflow
def test_demo_failure():
    x = 10
    y = 0
    result = x / y
    assert result == 5
