import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

_HOMEPAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>{app_name}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; background: #0f172a; color: #e2e8f0;
         margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 2.5rem 3rem;
           max-width: 560px; }}
  h1 {{ margin: 0 0 0.25rem; font-size: 24px; font-weight: 600; }}
  p.tagline {{ color: #94a3b8; margin: 0 0 1.5rem; font-size: 14px; }}
  .badge {{ display: inline-block; background: #064e3b; color: #6ee7b7; font-size: 12px;
            padding: 3px 10px; border-radius: 999px; margin-bottom: 1.5rem; }}
  .links {{ display: flex; flex-direction: column; gap: 10px; }}
  a.link {{ display: flex; justify-content: space-between; align-items: center; text-decoration: none;
            color: #e2e8f0; background: #0f172a; border: 1px solid #334155; border-radius: 8px;
            padding: 12px 16px; font-size: 14px; transition: border-color 0.15s; }}
  a.link:hover {{ border-color: #6366f1; }}
  a.link span.desc {{ color: #94a3b8; font-size: 12px; }}
  .meta {{ margin-top: 1.5rem; font-size: 12px; color: #64748b; }}
</style>
</head>
<body>
  <div class="card">
    <span class="badge">&#9679; running &middot; {environment}</span>
    <h1>{app_name}</h1>
    <p class="tagline">LLM-powered root-cause analysis for CI/CD pipeline failures.</p>
    <div class="links">
      <a class="link" href="/docs">
        <span>Interactive API docs (Swagger UI)</span><span class="desc">/docs</span>
      </a>
      <a class="link" href="/redoc">
        <span>API reference (ReDoc)</span><span class="desc">/redoc</span>
      </a>
      <a class="link" href="/health">
        <span>Health check</span><span class="desc">/health</span>
      </a>
      <a class="link" href="/reports">
        <span>Analysis history</span><span class="desc">/reports</span>
      </a>
    </div>
    <p class="meta">version 1.0.0</p>
  </div>
</body>
</html>
"""

from app.config import settings
from app.database import Base, engine
from app.routers import analyze, reports
from app.schemas import HealthResponse

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="LLM-powered root-cause analysis for CI/CD pipeline failures.",
    version="1.0.0",
)

# In production, schema changes are managed by Alembic migrations (see
# alembic/), not create_all(). create_all() is convenient for local dev /
# tests and is a no-op for tables that already exist.
Base.metadata.create_all(bind=engine)

app.include_router(analyze.router)
app.include_router(reports.router)


@app.get("/", response_class=HTMLResponse, tags=["meta"])
def homepage() -> HTMLResponse:
    """
    Landing page. An API service has no UI of its own beyond this, but a
    bare 404 on '/' is a bad first impression — this gives a human visitor
    a real page with links to the docs, health check, and reports.
    """
    html = _HOMEPAGE_HTML.format(app_name=settings.app_name, environment=settings.environment)
    return HTMLResponse(content=html)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(environment=settings.environment)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Last-resort handler. The goal is that GitHub Actions callers always get
    a clean JSON response, never a bare 500 with an HTML traceback — an
    unparseable response from *this* service would defeat the purpose of a
    tool meant to reduce debugging friction.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
