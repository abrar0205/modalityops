"""Local-only HTTP service. Report persistence, bounded requests, no raw-file upload."""

import json
import logging
import os
import re
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .engine import analyze
from .models import DemoConfig, Session
from .report import write_json
from .synthetic import generate

log = logging.getLogger("modalityops")
MAX_BODY = 32 * 1024 * 1024


def create_app(run_dir: Path | None = None, web_dir: Path | None = None):
    app = FastAPI(
        title="ModalityOps",
        version=__version__,
        description="Local-first research signal QC. Not a clinical device.",
    )
    reports = run_dir or Path(os.environ.get("MODALITYOPS_RUN_DIR", "runs/api"))
    slots = threading.BoundedSemaphore(2)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        # No CORS wildcard: the UI is served from the same origin.
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return JSONResponse(
                    {"detail": "Cross-origin requests are not allowed"}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    async def read_body(request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                raise HTTPException(413, "Request exceeds 32 MiB")
        try:
            return json.loads(body)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, "Invalid JSON") from exc

    async def execute(fn):
        if not slots.acquire(blocking=False):
            raise HTTPException(503, "Analysis capacity reached. Try again shortly.")
        start = time.perf_counter()
        try:
            result = await run_in_threadpool(fn)
            await run_in_threadpool(write_json, reports / f"{result['id']}.json", result)
            log.info(
                json.dumps(
                    {
                        "event": "analysis_complete",
                        "report_id": result["id"],
                        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                        "issue_count": result["summary"]["issue_count"],
                    }
                )
            )
            return result
        finally:
            slots.release()

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "engine_version": __version__, "mode": "local"}

    @app.post("/api/v1/demo")
    async def demo(request: Request):
        body = await read_body(request)
        try:
            config = DemoConfig.model_validate(body)
        except ValidationError as exc:
            raise HTTPException(422, "Invalid demo configuration") from exc
        return await execute(lambda: analyze(generate(config)[0]))

    @app.post("/api/v1/analyze")
    async def analyze_session(request: Request):
        body = await read_body(request)
        try:
            session = Session.model_validate(body)
        except ValidationError as exc:
            # Do not echo raw signals or private values in validation errors.
            raise HTTPException(
                422, "Invalid session. Validate against the documented Session schema."
            ) from exc
        return await execute(lambda: analyze(session))

    @app.get("/api/v1/reports")
    def list_reports():
        paths = (
            sorted(reports.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:100]
            if reports.exists()
            else []
        )
        entries = []
        for path in paths:
            data = json.loads(path.read_text())
            entries.append(
                {
                    "id": data["id"],
                    "title": data["title"],
                    "source": data["source"],
                    "summary": data["summary"],
                }
            )
        return entries

    @app.get("/api/v1/reports/{report_id}")
    def get_report(report_id: str):
        if not re.fullmatch(r"[0-9a-f]{12}-[0-9a-f]{8}", report_id):
            raise HTTPException(404, "Report not found")
        path = reports / f"{report_id}.json"
        if not path.is_file():
            raise HTTPException(404, "Report not found")
        return json.loads(path.read_text())

    static = web_dir or Path(os.environ.get("MODALITYOPS_WEB_DIR", "web/out"))
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="dashboard")
    return app


app = create_app()
