# Methods and scientific boundaries

## Clock estimation

Each stream has a clock identifier and optional events with stable IDs. A reference clock supplies timestamps for the same physical events. The mapping is:

`device_time = scale * reference_time + intercept_s`

`offset_ms = 1000 * intercept_s`

`drift_ppm = 1e6 * (scale - 1)`

Positive offset means the device timestamp is ahead of the reference at reference time zero. Positive drift means that clock advances faster. Correction is `(device_time - intercept_s) / scale`; this changes the time coordinate, not the signal samples.

The estimator enumerates bounded event pairs to find deterministic consensus within a 5 ms default tolerance, then refits a line on the consensus. It requires at least three matched events spanning at least one second, at least 70% consensus, and scale within 0.99–1.01. An inconsistent refit, implausible scale, missing evidence or timestamp reset prevents correction. The reported range is the inlier reference-event span. The UI omits corrected trace segments outside that span.

RMS residual and slope standard error describe the fit under the model. They are not calibrated probabilities of correct synchronization. A small residual cannot detect a consistently wrong event association, a fixed trigger latency or common-mode errors. Shared event IDs must represent the same real occurrence across devices. Nonlinear clock behavior needs a future piecewise model.

`estimate_audio_offset` separately supports bounded cross-correlation of the **same recorded audio signal**. It rejects silence and ambiguous periodic peaks. It is a library utility, not a general EEG/audio alignment method or the dashboard's clock estimator.

## Quality checks

| Check | Rule | Interpretation boundary |
|---|---|---|
| Timestamp order | Repeated or decreasing timestamps | May indicate a reset, bad extraction or repeated PTS |
| Gap | Adjacent interval > 1.6 × nominal sample period | Missing count is an estimate; VFR can produce legitimate gaps |
| Jitter | Interval standard deviation > 10% of nominal period, excluding large gaps | Not the same as absolute synchronization error |
| Missing values | Explicit null samples | Never silently imputed |
| Audio clipping | Absolute normalized amplitude ≥ 0.999 | Floating-point audio may exceed unity; inspect acquisition conventions |
| EEG saturation | Absolute amplitude ≥ 5000 µV | Configurable engineering threshold, not a universal sensor limit |
| Flatline | Equal consecutive values for ≥ 0.4 seconds, without bridging gaps | Silence or quantization may be legitimate; requires inspection |
| EEG line noise | Welch PSD power within ±1 Hz of 50/60 Hz exceeds 20% of 1–100 Hz power (bounded by Nyquist) | Skipped for invalid/irregular data; inspect spectrum and acquisition settings |

Video values are grayscale frame-mean luminance, not face, gaze or action-unit measurements. A dark or static scene is not automatically a broken camera. No clinical conclusions are generated.

## Display versus analysis

The engine works on full input samples. The report includes up to 360 min/max display buckets per channel, preserving extrema but not enough information for downstream spectral analysis. The dashboard breaks traces at documented gaps and missing intervals. Do not treat a display summary as raw data, especially after zooming.

## Reproducibility

Reports carry SHA-256 hashes of canonical session/configuration JSON, the engine version, thresholds, matched event evidence and a correction manifest. The content-addressed report ID includes the engine version. Raw input is not mutated. Atomic JSON writes avoid partial reports; HTML output escapes source text.

## References

- [PyAV frame timestamps](https://pyav.basswood.io/docs/stable/api/frame.html): presentation timestamp and time-base semantics.
- [MNE EDF reader](https://mne.tools/stable/generated/mne.io.read_raw_edf.html): format handling; EEG is converted from MNE's volts to microvolts at the adapter boundary.
- [SciPy Welch method](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html): power spectral density estimation.

These references describe library behavior, not external validation of ModalityOps.
