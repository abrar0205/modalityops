"""Integration fixtures generated at test time. No external recordings."""

import csv
from fractions import Fraction

import numpy as np
import pytest

from modalityops.engine import analyze
from modalityops.io import load_manifest
from modalityops.report import write_json


def manifest(tmp_path, streams):
    path = tmp_path / "manifest.json"
    write_json(
        path,
        {
            "id": "import-test",
            "title": "Generated media",
            "source": "synthetic",
            "reference_clock": "ref",
            "streams": streams,
        },
    )
    return path


def test_csv_missing_values_and_actual_timestamps(tmp_path):
    with (tmp_path / "eeg.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows([["timestamp", "C3"], [0, 1], [0.01, ""], [0.03, 2]])
    path = manifest(
        tmp_path,
        [
            {
                "id": "eeg",
                "modality": "eeg",
                "unit": "uV",
                "clock": "eeg",
                "sample_rate": 100,
                "path": "eeg.csv",
            }
        ],
    )
    session = load_manifest(path)
    assert session.streams[0].timestamps == [0, 0.01, 0.03]
    assert session.streams[0].values[1] == [None]
    assert {"MISSING_VALUES", "SAMPLE_GAP", "SYNC_UNIDENTIFIABLE"} <= {
        i["code"] for i in analyze(session)["issues"]
    }


def test_empty_csv_is_a_useful_error(tmp_path):
    (tmp_path / "empty.csv").touch()
    path = manifest(tmp_path, [{"path": "empty.csv"}])
    with pytest.raises(ValueError, match="CSV first column"):
        load_manifest(path)


def test_real_mp4_pts_round_trip(tmp_path):
    av = pytest.importorskip("av")
    with av.open(str(tmp_path / "generated.mp4"), "w") as output:
        stream = output.add_stream("mpeg4", rate=30)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for index in [0, 1, 2, 3, 6, 7, 8, 9]:
            frame = av.VideoFrame.from_ndarray(
                np.full((48, 64, 3), 20 * index, dtype=np.uint8), format="rgb24"
            )
            frame.pts, frame.time_base = index, Fraction(1, 30)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    path = manifest(
        tmp_path,
        [
            {
                "id": "video",
                "modality": "video",
                "clock": "camera",
                "sample_rate": 30,
                "path": "generated.mp4",
            }
        ],
    )
    session = load_manifest(path)
    assert session.streams[0].timestamps == pytest.approx(np.array([0, 1, 2, 3, 6, 7, 8, 9]) / 30)
    assert analyze(session)["streams"][0]["qc"]["gap_count"] == 1


def test_mne_fif_units_and_eeg_only(tmp_path):
    mne = pytest.importorskip("mne")
    raw = mne.io.RawArray(
        np.array([[1e-6] * 100, [2e-6] * 100, [0] * 100]),
        mne.create_info(["C3", "C4", "EOG"], 100, ["eeg", "eeg", "eog"]),
        verbose="ERROR",
    )
    raw.save(tmp_path / "generated_raw.fif", overwrite=True, verbose="ERROR")
    path = manifest(
        tmp_path,
        [{"id": "eeg", "modality": "eeg", "clock": "amplifier", "path": "generated_raw.fif"}],
    )
    session = load_manifest(path)
    assert session.streams[0].channels == ["C3", "C4"]
    assert session.streams[0].values[0] == pytest.approx([1, 2])


def test_unsupported_format(tmp_path):
    with pytest.raises(ValueError, match="Unsupported source format"):
        load_manifest(manifest(tmp_path, [{"path": "test.exe"}]))
