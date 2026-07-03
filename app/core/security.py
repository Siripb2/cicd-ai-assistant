"""
Inbound request auth.

This service is called by GitHub Actions runners, not end users, so a
shared-secret API key (passed as a header) is sufficient and far simpler
than OAuth/JWT for this use case. If multi-tenant support is added (see
README "Multi-tenant design"), this would be upgraded to a per-org API key
or JWT that resolves to an org_id, which is why `org_id` already exists as
a field in the data model.
"""
from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    # If no API key is configured (e.g. local dev), auth is skipped — but
    # this should never be the case in staging/production (enforced by
    # deployment config, not by this code, to keep local dev frictionless).
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
