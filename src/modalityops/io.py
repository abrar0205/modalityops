"""Explicit local import adapters. No downloads or uploads, no hidden clock assumptions."""

import csv
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from .models import Session, Stream


def load_manifest(path: Path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    streams = []
    for entry in manifest.pop("streams"):
        entry = dict(entry)
        source = (path.parent / entry.pop("path")).resolve()
        suffix = source.suffix.lower()
        if suffix == ".csv":
            with source.open(encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
                if len(header) < 2 or header[0] != "timestamp":
                    raise ValueError("CSV first column must be timestamp (seconds)")
                rows = []
                for row in reader:
                    if len(row) != len(header):
                        raise ValueError("CSV sample width does not match its header")
                    if len(rows) >= 1_000_000:
                        raise ValueError("CSV exceeds sample limit; import a smaller window")
                    rows.append([float(x) if x else None for x in row])
            entry.update(
                timestamps=[r[0] for r in rows], values=[r[1:] for r in rows], channels=header[1:]
            )
        elif suffix == ".wav":
            if source.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("WAV exceeds 32 MiB; import a smaller window")
            try:
                rate, values = wavfile.read(source, mmap=True)
            except ValueError as exc:
                if "mmap" not in str(exc).lower():
                    raise
                rate, values = wavfile.read(source, mmap=False)  # Packed 24-bit PCM.
            if len(values) > 1_000_000:
                raise ValueError("WAV exceeds 1 million samples; import a smaller window")
            if values.ndim == 1:
                values = values[:, None]
            if values.dtype.kind == "u":
                midpoint = (np.iinfo(values.dtype).max + 1) / 2
                values = (values.astype(float) - midpoint) / midpoint
            elif values.dtype.kind == "i":
                values = values.astype(float) / float(2 ** (values.dtype.itemsize * 8 - 1))
            entry.update(
                sample_rate=float(rate),
                unit="normalized",
                channels=[f"audio-{i}" for i in range(values.shape[1])],
                timestamps=(np.arange(len(values)) / rate).tolist(),
                values=values.tolist(),
            )
        elif suffix in (".mp4", ".mkv", ".mov"):
            try:
                import av
            except ImportError as exc:
                raise ValueError("Install modalityops[media] for video imports") from exc
            t, v = [], []
            with av.open(str(source)) as container:
                if not container.streams.video:
                    raise ValueError("Container has no video stream")
                video = container.streams.video[0]
                rate = float(entry.get("sample_rate") or video.average_rate or 0)
                if rate <= 0:
                    raise ValueError(
                        "Video has no nominal frame rate; supply sample_rate in the manifest"
                    )
                for frame in container.decode(video):
                    if frame.pts is None or frame.time_base is None:
                        raise ValueError(
                            "Frame has no presentation timestamp; cannot infer its clock"
                        )
                    if len(t) >= 100_000:
                        raise ValueError("Video exceeds frame limit")
                    t.append(float(frame.pts * frame.time_base))
                    v.append([float(frame.to_ndarray(format="gray").mean() / 255)])
            entry.update(
                sample_rate=rate,
                unit="luminance",
                channels=["frame-luminance"],
                timestamps=t,
                values=v,
            )
        elif suffix in (".edf", ".bdf", ".fif", ".vhdr"):
            try:
                import mne
            except ImportError as exc:
                raise ValueError("Install modalityops[media] for EEG imports") from exc
            readers = {
                ".edf": mne.io.read_raw_edf,
                ".bdf": mne.io.read_raw_bdf,
                ".fif": mne.io.read_raw_fif,
                ".vhdr": mne.io.read_raw_brainvision,
            }
            raw = readers[suffix](source, preload=False, verbose="ERROR")
            try:
                raw.pick("eeg")
                if raw.n_times * len(raw.ch_names) > 2_000_000:
                    raise ValueError("EEG exceeds value limit; export a smaller window")
                values = raw.get_data().T * 1e6  # MNE represents EEG in volts.
                entry.update(
                    sample_rate=float(raw.info["sfreq"]),
                    unit="uV",
                    channels=raw.ch_names,
                    timestamps=raw.times.tolist(),
                    values=values.tolist(),
                )
            finally:
                raw.close()
        else:
            raise ValueError(f"Unsupported source format: {suffix}")
        streams.append(Stream.model_validate(entry))
    return Session.model_validate({**manifest, "streams": streams})
