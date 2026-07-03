"""
Log sanitization.

CI/CD logs frequently contain secrets (API keys, tokens, passwords,
cloud credentials) printed accidentally by build tools. Before any log
content leaves this service — to an LLM provider or to storage — it is
scrubbed for known secret patterns.

This is defense-in-depth, not a guarantee: it catches well-known patterns,
not every possible secret shape. Treat this as one layer of a larger
secrets-hygiene strategy (the other layer being: don't print secrets in
your CI in the first place).
"""
import re

_REDACTION = "***REDACTED***"

# Each pattern captures the *value* in group 1 so we can replace only the
# value and keep the surrounding key name for context (helps the LLM and
# the human reader understand *what kind* of secret was there).
_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([A-Za-z0-9\-_./+]{8,})"),
    re.compile(r"(?i)(secret[_-]?key\s*[=:]\s*)([A-Za-z0-9\-_./+]{8,})"),
    re.compile(r"(?i)(access[_-]?token\s*[=:]\s*)([A-Za-z0-9\-_./+]{8,})"),
    re.compile(r"(?i)(token\s*[=:]\s*)([A-Za-z0-9\-_./+]{8,})"),
    re.compile(r"(?i)(password\s*[=:]\s*)(\S+)"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)([A-Za-z0-9\-_./+]+)"),
    re.compile(r"(AKIA[0-9A-Z]{16})"),  # AWS access key ID
    re.compile(r"(?i)(aws_secret_access_key\s*[=:]\s*)([A-Za-z0-9/+=]{20,})"),
    re.compile(r"(ghp_[A-Za-z0-9]{30,})"),  # GitHub personal access token
    re.compile(r"(gho_[A-Za-z0-9]{30,})"),  # GitHub OAuth token
    re.compile(
        r"(?i)(-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)"
        r"([\s\S]*?)"
        r"(-----END (?:RSA |EC )?PRIVATE KEY-----)"
    ),
]


def sanitize_log(raw_log: str) -> str:
    """Return a copy of raw_log with known secret patterns redacted."""
    sanitized = raw_log
    for pattern in _SECRET_PATTERNS:
        if pattern.groups >= 2:
            sanitized = pattern.sub(lambda m: m.group(1) + _REDACTION, sanitized)
        else:
            sanitized = pattern.sub(_REDACTION, sanitized)
    return sanitized


def truncate_log(log: str, max_chars: int) -> str:
    """
    Keep the *tail* of the log, not the head.

    The actual failing assertion/stack trace is almost always at the end of
    a CI log; the head is typically dependency installation noise. Keeping
    the last `max_chars` characters maximizes the chance the real error is
    inside the token budget sent to the LLM.
    """
    if len(log) <= max_chars:
        return log
    return f"...[truncated {len(log) - max_chars} earlier characters]...\n" + log[-max_chars:]
