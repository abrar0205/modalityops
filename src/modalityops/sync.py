"""Robust event-anchored clock mapping; never correlate EEG with speech to infer time."""

import numpy as np
from scipy.signal import correlate, correlation_lags

from .models import Event


def estimate_clock(reference: list[Event], observed: list[Event], tolerance_ms: float = 5):
    refs = {event.id: event.timestamp for event in reference}
    pairs = sorted((refs[e.id], e.timestamp) for e in observed if e.id in refs)
    base = {
        "status": "unidentifiable",
        "method": "shared-event robust affine fit",
        "matched_events": len(pairs),
        "offset_ms": None,
        "drift_ppm": None,
        "scale": None,
        "intercept_s": None,
        "residual_ms": None,
        "inliers": 0,
        "anchors": [],
        "valid_range_s": None,
        "drift_standard_error_ppm": None,
    }
    if len(pairs) < 3:
        return {**base, "reason": "At least three matched shared events are required."}
    x, y = np.array(pairs, dtype=float).T
    if np.ptp(x) < 1 or len(np.unique(x)) < 3:
        return {**base, "reason": "Distinct reference events must span at least one second."}
    # Deterministic consensus across bounded pairs; resistant to mislabeled anchors.
    tolerance = tolerance_ms / 1000
    best = np.zeros(len(x), dtype=bool)
    best_error = float("inf")
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            if x[j] - x[i] < 0.5:
                continue
            slope = (y[j] - y[i]) / (x[j] - x[i])
            residual = abs(y - (slope * x + y[i] - slope * x[i]))
            mask = residual <= tolerance
            error = float(np.median(residual[mask])) if mask.any() else float("inf")
            if mask.sum() > best.sum() or (mask.sum() == best.sum() and error < best_error):
                best, best_error = mask, error
    if best.sum() < 3 or best.mean() < 0.7:
        return {**base, "reason": "Shared events do not support a consistent affine clock."}
    slope, intercept = np.polyfit(x[best], y[best], 1)
    residual = (y - (slope * x + intercept)) * 1000
    if np.max(abs(residual[best])) > tolerance_ms:
        return {**base, "reason": "Refitted clock exceeds the configured anchor tolerance."}
    if not 0.99 <= slope <= 1.01 or np.ptp(x[best]) < 1:
        return {**base, "reason": "Clock scale is implausible or anchor span is insufficient."}
    residual_variance = np.sum((residual[best] / 1000) ** 2) / (best.sum() - 2)
    slope_se = np.sqrt(residual_variance / np.sum((x[best] - x[best].mean()) ** 2))
    return {
        **base,
        "status": "estimated",
        "reason": "Estimated within the shared-event span only.",
        "offset_ms": round(float(intercept * 1000), 6),
        "drift_ppm": round(float((slope - 1) * 1e6), 6),
        "scale": float(slope),
        "intercept_s": float(intercept),
        "residual_ms": float(np.sqrt(np.mean(residual[best] ** 2))),
        "drift_standard_error_ppm": float(slope_se * 1e6),
        "inliers": int(best.sum()),
        "valid_range_s": [float(x[best].min()), float(x[best].max())],
        "anchors": [
            {
                "reference_s": float(a),
                "observed_s": float(b),
                "lag_ms": float((b - a) * 1000),
                "residual_ms": float(r),
                "inlier": bool(m),
            }
            for a, b, r, m in zip(x, y, residual, best)
        ],
    }


def estimate_audio_offset(reference, observed, sample_rate: float, max_lag_seconds: float = 2):
    """Bounded same-signal audio alignment. Positive lag means observed arrives later.

    This helper does not claim an EEG or video clock mapping. Ambiguous peaks and silence
    are explicitly rejected. Use envelopes/downsampled windows for long recordings.
    """
    a, b = np.asarray(reference, dtype=float), np.asarray(observed, dtype=float)
    if a.ndim != 1 or b.ndim != 1 or not 3 <= min(a.size, b.size):
        raise ValueError("provide two one-dimensional signals of at least three samples")
    if max(a.size, b.size) > 500_000 or sample_rate <= 0 or max_lag_seconds <= 0:
        raise ValueError("invalid rate, lag bound or oversized correlation window")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("signals must be finite")
    a, b = a - a.mean(), b - b.mean()
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm < 1e-12:
        return {"status": "unidentifiable", "reason": "Signal is silent or constant."}
    c = correlate(b, a, mode="full", method="fft") / norm
    lags = correlation_lags(b.size, a.size)
    keep = abs(lags) <= max_lag_seconds * sample_rate
    c, lags = c[keep], lags[keep]
    peak = int(np.argmax(c))
    competitors = c[abs(lags - lags[peak]) > max(2, sample_rate * 0.01)]
    second = float(competitors.max()) if competitors.size else 0
    if c[peak] < 0.3 or c[peak] - second < 0.05:
        return {"status": "unidentifiable", "reason": "Weak or ambiguous correlation peak."}
    return {
        "status": "estimated",
        "offset_ms": float(lags[peak] / sample_rate * 1000),
        "peak_correlation": float(c[peak]),
        "peak_margin": float(c[peak] - second),
    }
