"""Transparent, threshold-based QC. Findings are engineering flags, not diagnoses."""

import numpy as np
from scipy.signal import welch

from .models import AnalysisConfig, Stream


def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(int))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))


def inspect_stream(stream: Stream, config: AnalysisConfig):
    t, values = np.asarray(stream.timestamps), np.asarray(stream.values, dtype=float)
    dt = np.diff(t)
    expected = 1 / stream.sample_rate
    issues, channels = [], []
    omitted = 0

    def add(code, severity, message, start, end, channel=None, evidence=None):
        nonlocal omitted
        if len(issues) >= 200:
            omitted += 1
            return
        issues.append(
            {
                "code": code,
                "severity": severity,
                "stream_id": stream.id,
                "channel": channel,
                "message": message,
                "start_s": float(start),
                "end_s": float(end),
                "evidence": evidence or {},
            }
        )

    for idx in np.flatnonzero(dt <= 0)[:100]:
        add(
            "TIMESTAMP_ORDER",
            "error",
            "Timestamp is repeated or moves backwards.",
            t[idx],
            t[idx + 1],
            evidence={"delta_s": float(dt[idx])},
        )
    gap_ids = np.flatnonzero(dt > config.gap_factor * expected)
    for idx in gap_ids[:100]:
        add(
            "SAMPLE_GAP",
            "warning",
            "Gap in the recorded timeline.",
            t[idx],
            t[idx + 1],
            evidence={
                "gap_ms": float(dt[idx] * 1000),
                "estimated_missing_samples": max(1, int(round(dt[idx] / expected)) - 1),
            },
        )
    positive = dt[dt > 0]
    jitter = (
        float(np.std(positive[positive < expected * config.gap_factor]) * 1000)
        if np.any((dt > 0) & (dt < expected * config.gap_factor))
        else None
    )
    if jitter is not None and jitter > expected * 1000 * 0.1:
        add(
            "TIMESTAMP_JITTER",
            "warning",
            "Frame/sample intervals vary substantially.",
            t.min(),
            t.max(),
            evidence={"interval_std_ms": jitter},
        )
    for c, name in enumerate(stream.channels):
        v = values[:, c]
        valid = np.isfinite(v)
        clean = v[valid]
        for start, end in runs(~valid):
            add(
                "MISSING_VALUES",
                "error",
                "Missing signal values.",
                t[start],
                t[end - 1],
                name,
                {"samples": int(end - start)},
            )
        threshold = (
            config.eeg_saturation_uv if stream.modality == "eeg" else config.audio_clip_level
        )
        clip = (
            (abs(v) >= threshold) & valid if stream.modality != "video" else np.zeros(v.size, bool)
        )
        if clip.any():
            indices = np.flatnonzero(clip)
            add(
                "EEG_SATURATION" if stream.modality == "eeg" else "AUDIO_CLIPPING",
                "warning",
                "Signal reaches the configured amplitude limit.",
                t[indices[0]],
                t[indices[-1]],
                name,
                {
                    "samples": int(clip.sum()),
                    "threshold": threshold,
                    "fraction": float(clip.mean()),
                },
            )
        # Consecutive equal samples, broken at missing values and timestamp gaps.
        flat = (
            (abs(np.diff(v)) < 1e-10)
            & valid[:-1]
            & valid[1:]
            & (dt > 0)
            & (dt < expected * config.gap_factor)
        )
        flat_seconds = 0.0
        if stream.modality != "video":
            for start, end in runs(flat):
                duration = t[end] - t[start]
                if duration >= config.flatline_seconds:
                    flat_seconds += float(duration)
                    add(
                        "FLATLINE",
                        "warning",
                        "Constant signal; inspect sensor contact or silence.",
                        t[start],
                        t[end],
                        name,
                        {"duration_s": float(duration)},
                    )
        line_ratio = None
        if (
            stream.modality == "eeg"
            and valid.all()
            and len(v) >= stream.sample_rate * 2
            and not len(gap_ids)
            and np.all(dt > 0)
            and jitter is not None
            and jitter < expected * 100
        ):
            f, p = welch(v, fs=stream.sample_rate, nperseg=min(len(v), int(stream.sample_rate * 2)))
            total = float(p[(f >= 1) & (f <= min(100, stream.sample_rate / 2))].sum())
            if total > 0 and stream.sample_rate / 2 > config.line_frequency + 1:
                line_ratio = float(p[abs(f - config.line_frequency) <= 1].sum() / total)
                if line_ratio > 0.2:
                    add(
                        "LINE_NOISE",
                        "warning",
                        "Elevated power around the configured mains frequency.",
                        t.min(),
                        t.max(),
                        name,
                        {"power_fraction": line_ratio, "frequency_hz": config.line_frequency},
                    )
        channels.append(
            {
                "name": name,
                "rms": float(np.sqrt(np.mean(clean**2))) if clean.size else None,
                "peak": float(abs(clean).max()) if clean.size else None,
                "missing_samples": int((~valid).sum()),
                "clipped_fraction": float(clip.mean()),
                "flatline_seconds": flat_seconds,
                "line_noise_fraction": line_ratio,
            }
        )
    if omitted:
        issues.append(
            {
                "code": "FINDINGS_TRUNCATED",
                "severity": "warning",
                "stream_id": stream.id,
                "channel": None,
                "message": "Detailed findings capped at 200 for this stream. Inspect a smaller window.",
                "start_s": float(t.min()),
                "end_s": float(t.max()),
                "evidence": {"omitted_findings": omitted},
            }
        )
    return {
        "samples": len(t),
        "duration_s": float(t.max() - t.min()),
        "gap_count": len(gap_ids),
        "order_error_count": int((dt <= 0).sum()),
        "interval_jitter_ms": jitter,
        "channels": channels,
    }, issues
