"""Deterministic noisy-marker benchmark using independent held-out events."""

from pathlib import Path

import numpy as np

from modalityops.models import Event
from modalityops.report import write_json
from modalityops.sync import estimate_clock


def benchmark():
    results = []
    for seed in range(12):
        for offset, drift in [(-250, -400), (0, 0), (180, 120), (1000, 1500)]:
            rng = np.random.default_rng(seed)
            times = np.linspace(0, 120, 25)
            reference = [Event(id=str(i), timestamp=t) for i, t in enumerate(times)]
            observed = [
                Event(
                    id=e.id,
                    timestamp=e.timestamp * (1 + drift / 1e6)
                    + offset / 1000
                    + rng.normal(0, 0.0001),
                )
                for e in reference
            ]
            observed[4].timestamp += 0.8
            fit = estimate_clock(reference[::2], observed[::2])
            if fit["status"] != "estimated":
                raise AssertionError("Expected an identifiable synthetic clock")
            errors = [
                abs(
                    (observed[i].timestamp - fit["intercept_s"]) / fit["scale"]
                    - reference[i].timestamp
                )
                * 1000
                for i in range(1, 25, 2)
            ]
            results.append(
                {
                    "seed": seed,
                    "offset_ms": offset,
                    "drift_ppm": drift,
                    "offset_error_ms": abs(fit["offset_ms"] - offset),
                    "drift_error_ppm": abs(fit["drift_ppm"] - drift),
                    "heldout_max_error_ms": max(errors),
                    "rejected_calibration_events": fit["matched_events"] - fit["inliers"],
                }
            )
    summary = {
        "cases": len(results),
        "heldout_events_per_case": 12,
        "marker_noise_std_ms": 0.1,
        "mislabeled_calibration_marker_shift_ms": 800,
        "max_heldout_error_ms": max(r["heldout_max_error_ms"] for r in results),
        "max_offset_error_ms": max(r["offset_error_ms"] for r in results),
        "max_drift_error_ppm": max(r["drift_error_ppm"] for r in results),
        "all_outliers_rejected": all(r["rejected_calibration_events"] == 1 for r in results),
        "scope": "Synthetic affine clocks. Does not measure real devices or clinical performance.",
    }
    assert summary["max_heldout_error_ms"] < 0.5
    assert summary["all_outliers_rejected"]
    return {"summary": summary, "cases": results}


if __name__ == "__main__":
    output = benchmark()
    write_json(Path(__file__).resolve().parents[1] / "docs" / "benchmark.json", output)
    print(output["summary"])
