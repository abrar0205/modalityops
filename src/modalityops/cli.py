"""Small CLI, deterministic outputs and nonzero exits for invalid input."""

import argparse
import json
from pathlib import Path

from .engine import analyze
from .io import load_manifest
from .models import AnalysisConfig, DemoConfig, Session
from .report import write_html, write_json
from .synthetic import generate


def main(argv=None):
    parser = argparse.ArgumentParser(prog="modalityops")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate and analyze a deterministic synthetic session")
    demo.add_argument(
        "--scenario",
        choices=["clean", "clock-drift", "dropouts", "signal-quality", "mixed"],
        default="mixed",
    )
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--duration", type=float, default=30)
    demo.add_argument("--offset-ms", type=float, default=180)
    demo.add_argument("--drift-ppm", type=float, default=120)
    demo.add_argument("--out", type=Path, default=Path("runs/demo"))
    inspect = sub.add_parser("analyze", help="Analyze a session JSON or local-file manifest")
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--manifest", action="store_true")
    inspect.add_argument("--config", type=Path)
    inspect.add_argument("--out", type=Path, default=Path("runs/analysis"))
    inspect.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            config = DemoConfig(
                scenario=args.scenario,
                seed=args.seed,
                duration=args.duration,
                offset_ms=args.offset_ms,
                drift_ppm=args.drift_ppm,
            )
            session, truth = generate(config)
            report = analyze(session)
            write_json(args.out / "session.json", session.model_dump())
            write_json(args.out / "ground-truth.json", truth)
        else:
            session = (
                load_manifest(args.input)
                if args.manifest
                else Session.model_validate_json(args.input.read_text())
            )
            config = (
                AnalysisConfig.model_validate_json(args.config.read_text()) if args.config else None
            )
            report = analyze(session, config)
        write_json(args.out / "report.json", report)
        write_json(args.out / "correction.json", report["correction_manifest"])
        write_html(args.out / "report.html", report)
        print(json.dumps({"report": str(args.out / "report.json"), **report["summary"]}))
        if getattr(args, "fail_on_error", False) and report["summary"]["error_count"]:
            raise SystemExit(2)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"modalityops: {exc}\n")


if __name__ == "__main__":
    main()
