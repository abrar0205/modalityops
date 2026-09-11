FROM node:22-bookworm-slim AS web
WORKDIR /build/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack install && pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build:static

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MODALITYOPS_RUN_DIR=/var/lib/modalityops MODALITYOPS_WEB_DIR=/app/web
WORKDIR /app
COPY requirements.lock pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home app && mkdir -p /var/lib/modalityops && chown app:app /var/lib/modalityops
COPY --from=web /build/web/out/ ./web/
RUN chmod -R a+rX /app/web
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "modalityops.api:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "8"]
