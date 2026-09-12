import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy.io import wavfile

from modalityops.api import create_app
from modalityops.cli import main
from modalityops.io import load_manifest
from modalityops.models import DemoConfig
from modalityops.report import write_html, write_json
from modalityops.synthetic import generate


def test_api_demo_report_round_trip(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/v1/health").json()["status"] == "ok"
    response = client.post("/api/v1/demo", json={"scenario": "mixed", "duration": 10})
    assert response.status_code == 200
    report = response.json()
    assert client.get(f"/api/v1/reports/{report['id']}").json() == report
    assert len(client.get("/api/v1/reports").json()) == 1
    assert client.get("/api/v1/reports/invalid").status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert not list(tmp_path.glob("*session*"))


@pytest.mark.parametrize(
    "path,payload",
    [
        ("demo", {"duration": 1000}),
        ("demo", {"seed": -1}),
        ("analyze", {"private-data": "must-not-echo"}),
    ],
)
def test_api_validation(tmp_path, path, payload):
    response = TestClient(create_app(tmp_path)).post(f"/api/v1/{path}", json=payload)
    assert response.status_code == 422
    assert "must-not-echo" not in response.text


def test_api_rejects_cross_origin_and_invalid_json(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert (
        client.post(
            "/api/v1/demo", json={}, headers={"origin": "https://untrusted.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/demo", content="not json").status_code == 422


def test_api_raw_session_and_restart_persistence(tmp_path):
    session, _ = generate(DemoConfig(duration=10, scenario="clean"))
    client = TestClient(create_app(tmp_path))
    response = client.post("/api/v1/analyze", json=session.model_dump(mode="json"))
    assert response.status_code == 200
    report = response.json()
    restarted = TestClient(create_app(tmp_path))
    assert restarted.get(f"/api/v1/reports/{report['id']}").json() == report
    assert report["correction_manifest"]["raw_data_modified"] is False


def test_api_host_and_body_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr("modalityops.api.MAX_BODY", 64)
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/v1/health", headers={"host": "evil.example"}).status_code == 400
    assert client.post("/api/v1/demo", content=" " * 65).status_code == 413


def test_api_serves_static_ui_without_shadowing_api(tmp_path):
    static = tmp_path / "web"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>ModalityOps</title>")
    client = TestClient(create_app(tmp_path / "runs", web_dir=static))
    assert "ModalityOps" in client.get("/").text
    assert client.get("/api/v1/health").json()["mode"] == "local"


@pytest.mark.parametrize(
    "dtype,raw,expected",
    [
        (np.uint8, [0, 128, 255], [-1, 0, 127 / 128]),
        (np.int16, [-32768, 0, 32767], [-1, 0, 32767 / 32768]),
        (np.float32, [-0.5, 0, 0.5], [-0.5, 0, 0.5]),
    ],
)
def test_wav_amplitude_and_channel_policy(tmp_path, dtype, raw, expected):
    wavfile.write(tmp_path / "test.wav", 8000, np.asarray([raw, raw], dtype=dtype).T)
    manifest = {
        "id": "wav-test",
        "title": "Test",
        "source": "synthetic",
        "reference_clock": "ref",
        "streams": [{"id": "audio", "modality": "audio", "clock": "mic", "path": "test.wav"}],
    }
    write_json(tmp_path / "manifest.json", manifest)
    session = load_manifest(tmp_path / "manifest.json")
    assert session.streams[0].channels == ["audio-0", "audio-1"]
    assert np.array(session.streams[0].values)[:, 0] == pytest.approx(expected)


def test_cli_roundtrip_and_safe_html(tmp_path):
    main(["demo", "--duration", "10", "--out", str(tmp_path)])
    report = json.loads((tmp_path / "report.json").read_text())
    main(["analyze", str(tmp_path / "session.json"), "--out", str(tmp_path / "second")])
    second = json.loads((tmp_path / "second" / "report.json").read_text())
    assert report == second
    report["title"] = "<script>alert(1)</script>"
    write_html(tmp_path / "safe.html", report)
    assert "<script>" not in (tmp_path / "safe.html").read_text()
