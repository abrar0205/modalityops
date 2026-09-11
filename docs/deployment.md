# Deployment

## Local full product

`docker compose up --build` serves the static UI and Python API on the same origin at `http://localhost:8000`. The service runs as a non-root user, with a read-only root filesystem, writable report volume, memory/CPU limits and loopback-only published port.

Docker is an isolation and packaging layer, not a guarantee that untrusted medical files are safe. The default service is not internet-ready. Do not change the bind address to a public interface without adding the controls described in `SECURITY.md`.

## Public portfolio demo on GitHub Pages

The included `Publish static demo` workflow is manual to avoid assuming repository settings:

1. In repository **Settings → Pages**, choose **GitHub Actions** as the source.
2. In **Actions**, run **Publish static demo** from `main`.
3. Use the successful workflow's deployment URL.

The build sets `/modalityops` as its base path. This publishes only synthetic precomputed reports and browser-only report inspection. No Python API or private recording is deployed. Do not replace demo JSON with real-session reports.

## Other static hosts

Run `pnpm build:static` inside `web` and publish `web/out`. Set `NEXT_PUBLIC_BASE_PATH` during the build for a subpath. The repository also retains an alternative static build configuration used for the hosted handover; it does not affect the local FastAPI workflow.

## Stopping and preserving reports

`docker compose down` stops the service and preserves the named volume. Export any reports you need before deliberately deleting that volume. No automatic report-deletion endpoint is shipped.
