import copy

import numpy as np
import pytest
from pydantic import ValidationError

from modalityops.engine import analyze
from modalityops.models import AnalysisConfig, DemoConfig, Event, Session
from modalityops.sync import estimate_audio_offset, estimate_clock
from modalityops.synthetic import generate


@pytest.mark.parametrize(
    "scenario", ["clean", "clock-drift", "dropouts", "signal-quality", "mixed"]
)
def test_end_to_end_ground_truth(scenario):
    session, truth = generate(DemoConfig(scenario=scenario, duration=10))
    before = copy.deepcopy(session.model_dump())
    result = analyze(session)
    for stream in result["streams"]:
        expected = truth[stream["id"]]
        assert stream["sync"]["offset_ms"] == pytest.approx(expected["offset_ms"], abs=1e-5)
        assert stream["sync"]["drift_ppm"] == pytest.approx(expected["drift_ppm"], abs=1e-5)
    codes = {i["code"] for i in result["issues"]}
    if scenario == "clean":
        assert not codes
    if scenario in ("mixed", "signal-quality"):
        assert {"FLATLINE", "AUDIO_CLIPPING", "LINE_NOISE"} <= codes
    if scenario in ("mixed", "dropouts"):
        assert "SAMPLE_GAP" in codes
    assert session.model_dump() == before
    assert result["correction_manifest"]["raw_data_modified"] is False
    assert analyze(session)["id"] == result["id"]
    assert analyze(session, AnalysisConfig(line_frequency=60))["id"] != result["id"]


@pytest.mark.parametrize("offset,ppm", [(-1200, -1800), (0, 0), (180, 120), (1750, 1500)])
def test_clock_outlier_and_held_out_events(offset, ppm):
    rng = np.random.default_rng(2026)
    t = np.linspace(0, 120, 25)
    reference = [Event(id=str(i), timestamp=x) for i, x in enumerate(t)]
    observed = [
        Event(
            id=e.id, timestamp=e.timestamp * (1 + ppm / 1e6) + offset / 1000 + rng.normal(0, 0.0001)
        )
        for e in reference
    ]
    observed[4].timestamp += 0.8  # An incorrect trigger association in the calibration set.
    calibration = list(range(0, 25, 2))
    fit = estimate_clock([reference[i] for i in calibration], [observed[i] for i in calibration])
    assert fit["status"] == "estimated"
    assert fit["inliers"] == len(calibration) - 1
    assert fit["offset_ms"] == pytest.approx(offset, abs=0.2)
    assert fit["drift_ppm"] == pytest.approx(ppm, abs=4)
    for i in range(1, 25, 2):
        corrected = (observed[i].timestamp - fit["intercept_s"]) / fit["scale"]
        assert abs(corrected - reference[i].timestamp) < 0.0005


@pytest.mark.parametrize("count", [0, 1, 2])
def test_insufficient_anchors(count):
    markers = [Event(id=str(i), timestamp=i) for i in range(count)]
    assert estimate_clock(markers, markers)["status"] == "unidentifiable"


def test_clock_resets_are_not_corrected():
    session, _ = generate(DemoConfig(scenario="clean", duration=10))
    session.streams[0].timestamps[50] = -1
    report = analyze(session)
    assert report["streams"][0]["sync"]["status"] == "unidentifiable"
    assert len(report["correction_manifest"]["corrections"]) == 2
    assert any(i["code"] == "TIMESTAMP_ORDER" for i in report["issues"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s["streams"][0]["timestamps"].pop(),
        lambda s: s["streams"][0]["values"][0].append(1),
        lambda s: s["streams"][0].update(unit="normalized"),
        lambda s: s["streams"][0]["timestamps"].__setitem__(0, float("nan")),
        lambda s: s["streams"][0]["channels"].__setitem__(0, "C4"),
        lambda s: s.update(streams=[s["streams"][0], s["streams"][0]]),
    ],
)
def test_invalid_sessions(mutate):
    payload = generate(DemoConfig(duration=10))[0].model_dump()
    mutate(payload)
    with pytest.raises(ValidationError):
        Session.model_validate(payload)


def test_null_samples_are_flagged_not_fabricated():
    session, _ = generate(DemoConfig(scenario="clean", duration=10))
    session.streams[0].values[0] = [None] * 4
    report = analyze(session)
    assert sum(i["code"] == "MISSING_VALUES" for i in report["issues"]) == 4


def test_audio_correlation_lag_sign_and_silence():
    rng = np.random.default_rng(7)
    x = rng.normal(size=5000)
    y = np.r_[np.zeros(35), x[:-35]]
    result = estimate_audio_offset(x, y, 1000)
    assert result["offset_ms"] == pytest.approx(35)
    assert estimate_audio_offset(np.zeros(100), np.zeros(100), 1000)["status"] == "unidentifiable"


def test_periodic_audio_is_ambiguous():
    x = np.sin(np.arange(10000) * 2 * np.pi / 100)
    assert estimate_audio_offset(x, x, 1000)["status"] == "unidentifiable"


def test_bad_clock_scale_rejected():
    refs = [Event(id=str(i), timestamp=i) for i in range(10)]
    obs = [Event(id=str(i), timestamp=i * 1.2) for i in range(10)]
    assert estimate_clock(refs, obs)["status"] == "unidentifiable"
