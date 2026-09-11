# Validation

## Tests

The test suite exercises deterministic scenarios, empty/malformed data, units, shared marker matching, negative and positive drift, one mislabeled calibration event, independent held-out event recovery, silent/periodic audio ambiguity, missing samples, clock resets, source immutability, private API errors, report persistence and HTML escaping.

Media integration tests create an MP4 with nonuniform presentation timestamps and an MNE FIF with EEG/EOG channels. The tests verify that the gap survives decoding, EEG-only selection is respected, and values arrive in microvolts. No external datasets are downloaded.

The frontend tests validate every bundled report and reject malformed geometry and dangling stream references. TypeScript checks and both supported static build paths are separate gates. A real browser interaction test and visual accessibility audit are not included in these measurements.

## Noisy-marker benchmark

Run `python scripts/benchmark.py`. Results are saved in [`benchmark.json`](benchmark.json).

- 48 cases: 12 seeds × 4 offset/drift combinations.
- 25 shared events across 120 seconds, with 0.1 ms Gaussian timestamp noise.
- Even-indexed events calibrate the clock; odd-indexed events are held out.
- One calibration marker is deliberately shifted by 800 ms.
- Acceptance criteria: reject that marker in every case; maximum held-out timing error below 0.5 ms.

These are engineering acceptance tests on generated data. The noise model, event density and clock model are controlled. Real devices can have fixed trigger latencies, nonlinear drift, resets, incorrect event associations, missing markers or sampling quantization not represented here.

## Current release limits

- No multi-hour memory/runtime guarantee.
- No clinical accuracy or diagnostic claims.
- No public API security certification.
- No gaze, facial-action, speech-recognition or brain-to-brain synchrony validation.
- Synthetic clean-session success means no configured checks fired, not proof of data validity.

CI reports are the authority for whether a particular revision passed. Docker requires a container runtime; when one is unavailable locally, its CI job performs the build and health check.
