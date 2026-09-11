"""Atomic report exports; HTML escapes all source-controlled or user-controlled text."""

import html
import json
import os
import tempfile
from pathlib import Path


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".modalityops-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, allow_nan=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_html(path: Path, report):
    def e(value):
        return html.escape(str(value))

    rows = "".join(
        f"<tr><td>{e(s['id'])}</td><td>{e(s['sync']['status'])}</td><td>{e(s['sync']['offset_ms'])}</td><td>{e(s['sync']['drift_ppm'])}</td></tr>"
        for s in report["streams"]
    )
    findings = "".join(
        f"<li><strong>{e(i['code'])}</strong> · {e(i['stream_id'])}: {e(i['message'])}</li>"
        for i in report["issues"]
    )
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ModalityOps — {e(report["title"])}</title><style>body{{font:16px/1.6 system-ui;max-width:1000px;margin:3rem auto;padding:0 1.5rem;background:#0c1220;color:#e7edf7}}h1{{color:#67e8c3}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:.7rem;border-bottom:1px solid #344055}}code{{overflow-wrap:anywhere}}a{{color:#67e8c3}}</style>
<h1>ModalityOps</h1><h2>{e(report["title"])}</h2><p>Source: {e(report["source"])} · Engine {e(report["engine_version"])} · Raw data unchanged</p>
<table><thead><tr><th>Stream</th><th>Alignment</th><th>Offset (ms)</th><th>Drift (ppm)</th></tr></thead><tbody>{rows}</tbody></table><h2>Quality findings</h2><ul>{findings or "<li>No findings under the configured thresholds.</li>"}</ul>
<h2>Provenance</h2><p>Input SHA-256: <code>{e(report["provenance"]["input_sha256"])}</code></p><p>Research infrastructure. No clinical interpretation. Correction is validated only within the shared-event span.</p></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
