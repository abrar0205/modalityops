"""Pure report generation, content-addressed provenance and non-destructive corrections."""

import hashlib
import json

import numpy as np

from . import __version__
from .models import AnalysisConfig, Session
from .qc import inspect_stream
from .sync import estimate_clock


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def analyze(session: Session, config: AnalysisConfig | None = None):
    config = config or AnalysisConfig()
    source_hash = digest(session.model_dump())
    config_hash = digest(config.model_dump())
    issues, results, corrections = [], [], []
    for stream in session.streams:
        qc, findings = inspect_stream(stream, config)
        issues.extend(findings)
        sync = estimate_clock(session.reference_events, stream.events, config.anchor_tolerance_ms)
        if qc["order_error_count"]:
            sync.update(
                status="unidentifiable",
                reason="Timestamp resets/repeats require inspection before a clock correction can be offered.",
                offset_ms=None,
                drift_ppm=None,
                scale=None,
                intercept_s=None,
                valid_range_s=None,
            )
        if sync["status"] != "estimated":
            issues.append(
                {
                    "code": "SYNC_UNIDENTIFIABLE",
                    "severity": "warning",
                    "stream_id": stream.id,
                    "channel": None,
                    "message": sync["reason"],
                    "start_s": min(stream.timestamps),
                    "end_s": max(stream.timestamps),
                    "evidence": {"matched_events": sync["matched_events"]},
                }
            )
        else:
            if abs(sync["offset_ms"]) > 10 or abs(sync["drift_ppm"]) > 20:
                issues.append(
                    {
                        "code": "CLOCK_MISALIGNMENT",
                        "severity": "warning",
                        "stream_id": stream.id,
                        "channel": None,
                        "message": "Device clock differs from the reference clock.",
                        "start_s": min(stream.timestamps),
                        "end_s": max(stream.timestamps),
                        "evidence": {
                            "offset_ms": sync["offset_ms"],
                            "drift_ppm": sync["drift_ppm"],
                        },
                    }
                )
            corrections.append(
                {
                    "stream_id": stream.id,
                    "from_clock": stream.clock,
                    "to_clock": session.reference_clock,
                    "scale": sync["scale"],
                    "intercept_s": sync["intercept_s"],
                    "valid_range_s": sync["valid_range_s"],
                    "formula": "reference_time = (device_time - intercept_s) / scale",
                }
            )
        # Min/max buckets preserve transients without shipping the raw recording to the UI.
        values = np.asarray(stream.values, dtype=float)
        preview = []
        for c, name in enumerate(stream.channels):
            points = []
            for indices in np.array_split(np.arange(len(values)), min(360, len(values))):
                valid = indices[np.isfinite(values[indices, c])]
                if valid.size:
                    a = valid[np.argmin(values[valid, c])]
                    b = valid[np.argmax(values[valid, c])]
                    points.extend(
                        [
                            {"t": stream.timestamps[int(i)], "v": float(values[i, c])}
                            for i in sorted({a, b})
                        ]
                    )
                else:
                    points.append({"t": stream.timestamps[int(indices[0])], "v": None})
            preview.append({"name": name, "points": points})
        results.append(
            {
                "id": stream.id,
                "modality": stream.modality,
                "clock": stream.clock,
                "unit": stream.unit,
                "sample_rate": stream.sample_rate,
                "qc": qc,
                "sync": sync,
                "preview": preview,
            }
        )
    for index, issue in enumerate(issues):
        issue["id"] = f"issue-{index + 1}"
    return {
        "schema_version": "1.0",
        "engine_version": __version__,
        "id": source_hash[:12] + "-" + digest({"config": config_hash, "engine": __version__})[:8],
        "session_id": session.id,
        "title": session.title,
        "source": session.source,
        "reference_clock": session.reference_clock,
        "provenance": {
            "input_sha256": source_hash,
            "config_sha256": config_hash,
            "config": config.model_dump(),
        },
        "summary": {
            "stream_count": len(results),
            "issue_count": len(issues),
            "error_count": sum(i["severity"] == "error" for i in issues),
            "alignment_count": len(corrections),
        },
        "streams": results,
        "issues": issues,
        "correction_manifest": {
            "schema_version": "1.0",
            "input_sha256": source_hash,
            "raw_data_modified": False,
            "corrections": corrections,
        },
        "limitations": [
            "Research infrastructure, not a diagnostic or clinical device.",
            "Affine correction is validated only within the shared-event span.",
            "QC thresholds require calibration for each acquisition system.",
            "Displayed traces are min/max summaries, not analysis-ready raw signals.",
        ],
    }
