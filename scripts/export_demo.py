"""Regenerate public reports from the Python engine. No university or participant data."""

from pathlib import Path

from modalityops.engine import analyze
from modalityops.models import DemoConfig, Session
from modalityops.report import write_json
from modalityops.synthetic import generate

root = Path(__file__).resolve().parents[1]
for scenario in ("clean", "clock-drift", "dropouts", "signal-quality", "mixed"):
    session, truth = generate(DemoConfig(scenario=scenario))
    report = analyze(session)
    report["benchmark"] = {
        "description": "Exact synthetic event timestamps; not real-device accuracy.",
        "ground_truth": truth,
        "max_offset_error_ms": max(
            abs(s["sync"]["offset_ms"] - truth[s["id"]]["offset_ms"]) for s in report["streams"]
        ),
        "max_drift_error_ppm": max(
            abs(s["sync"]["drift_ppm"] - truth[s["id"]]["drift_ppm"]) for s in report["streams"]
        ),
    }
    write_json(root / "web" / "public" / "demo" / f"{scenario}.json", report)
    (root / "web" / "public" / "demo" / f"{scenario}.json").chmod(0o644)
    print(scenario, report["summary"])
write_json(root / "docs" / "session.schema.json", Session.model_json_schema())
