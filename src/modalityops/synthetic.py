"""Deterministic non-human fixtures. Ground truth is separate from analysis input."""

import numpy as np

from .models import DemoConfig, Event, Session, Stream


def generate(config: DemoConfig):
    rng = np.random.default_rng(config.seed)
    anchors = np.linspace(1, config.duration - 1, 9)
    events = [Event(id=f"trigger-{i}", timestamp=float(t)) for i, t in enumerate(anchors)]
    streams, truth = [], {}
    for modality, rate, channels, unit in [
        ("eeg", 250, ["C3", "C4", "Pz", "Oz"], "uV"),
        ("audio", 2000, ["microphone"], "normalized"),
        ("video", 30, ["frame-luminance"], "luminance"),
    ]:
        t = np.arange(int(config.duration * rate)) / rate
        pulse = sum(np.exp(-(((t - a) / 0.035) ** 2)) for a in anchors)
        if modality == "eeg":
            v = np.stack(
                [
                    15 * np.sin(2 * np.pi * (9 + i) * t) + 4 * rng.normal(size=len(t)) + 30 * pulse
                    for i in range(4)
                ],
                axis=1,
            )
        elif modality == "audio":
            envelope = 0.15 + 0.1 * np.sin(2 * np.pi * 0.4 * t)
            v = (
                envelope * np.sin(2 * np.pi * 173 * t)
                + 0.25 * pulse
                + 0.005 * rng.normal(size=len(t))
            )[:, None]
        else:
            v = np.clip(0.35 + 0.1 * np.sin(t * 0.6) + 0.5 * pulse, 0, 1)[:, None]
        clock_fault = config.scenario in ("clock-drift", "mixed")
        offset = (
            config.offset_ms
            / 1000
            * (1 if modality == "eeg" else -0.5 if modality == "video" else 0)
            if clock_fault
            else 0
        )
        ppm = (
            config.drift_ppm * (1 if modality == "eeg" else -0.6 if modality == "video" else 0)
            if clock_fault
            else 0
        )
        scale = 1 + ppm / 1e6
        if config.scenario in ("signal-quality", "mixed"):
            window = (t > config.duration * 0.45) & (t < config.duration * 0.55)
            if modality == "eeg":
                v[window, 0] = 0
                v[:, 1] += 30 * np.sin(2 * np.pi * 50 * t)
            elif modality == "audio":
                v[window, 0] = np.clip(v[window, 0] * 12, -1, 1)
        keep = np.ones(t.size, dtype=bool)
        if config.scenario in ("dropouts", "mixed") and modality == "video":
            keep[(t >= config.duration * 0.65) & (t < config.duration * 0.65 + 0.4)] = False
        observed = [Event(id=e.id, timestamp=e.timestamp * scale + offset) for e in events]
        streams.append(
            Stream(
                id=modality,
                modality=modality,
                clock=f"{modality}-clock",
                sample_rate=rate,
                unit=unit,
                channels=channels,
                timestamps=(t[keep] * scale + offset).tolist(),
                values=v[keep].tolist(),
                events=observed,
            )
        )
        truth[modality] = {
            "offset_ms": offset * 1000,
            "drift_ppm": ppm,
            "removed_samples": int((~keep).sum()),
        }
    session = Session(
        id=f"synthetic-{config.scenario}-{config.seed}",
        title=f"{config.scenario.replace('-', ' ').title()} / synthetic session",
        source="synthetic",
        reference_clock="simulation-clock",
        reference_events=events,
        streams=streams,
    )
    return session, truth
