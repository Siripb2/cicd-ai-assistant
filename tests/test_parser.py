from app.services.parser import parse_llm_response


def test_parses_clean_json():
    raw = '{"root_cause": "missing dependency", "affected_component": "build", "fix_suggestion": "add to requirements.txt", "confidence_level": 0.9, "additional_context": ""}'
    result = parse_llm_response(raw)
    assert result.parse_succeeded
    assert result.root_cause == "missing dependency"
    assert result.confidence_level == 0.9


def test_parses_json_wrapped_in_code_fences():
    raw = '```json\n{"root_cause": "flaky test", "affected_component": "test_foo", "fix_suggestion": "retry", "confidence_level": 0.6, "additional_context": ""}\n```'
    result = parse_llm_response(raw)
    assert result.parse_succeeded
    assert result.root_cause == "flaky test"


def test_extracts_json_with_preamble_text():
    raw = 'Sure, here is the analysis:\n{"root_cause": "syntax error", "affected_component": "lint", "fix_suggestion": "fix line 10", "confidence_level": 0.8, "additional_context": ""}\nLet me know if you need more.'
    result = parse_llm_response(raw)
    assert result.parse_succeeded
    assert result.root_cause == "syntax error"


def test_falls_back_gracefully_on_freeform_text():
    raw = "The build failed because of a missing import statement on line 42."
    result = parse_llm_response(raw)
    assert result.parse_succeeded is False
    assert result.confidence_level is None
    assert result.fix_suggestion == raw


def test_handles_non_numeric_confidence():
    raw = '{"root_cause": "x", "affected_component": "y", "fix_suggestion": "z", "confidence_level": "high", "additional_context": ""}'
    result = parse_llm_response(raw)
    assert result.parse_succeeded
    assert result.confidence_level is None
