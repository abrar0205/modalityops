# Importing recordings

The canonical Session schema is published in [`session.schema.json`](session.schema.json). Times are seconds, values are sample-major arrays, missing values are JSON `null`, and units are explicit. EEG uses `uV`; audio uses normalized amplitude; video uses luminance in the display adapter.

## Local-file manifest

```json
{
  "id": "local-session",
  "title": "Local acquisition window",
  "source": "local",
  "reference_clock": "trigger-clock",
  "reference_events": [
    {"id": "sync-1", "timestamp": 1.0},
    {"id": "sync-2", "timestamp": 3.0},
    {"id": "sync-3", "timestamp": 5.0}
  ],
  "streams": [
    {
      "id": "microphone",
      "modality": "audio",
      "clock": "recorder",
      "path": "audio.wav",
      "events": [
        {"id": "sync-1", "timestamp": 1.12},
        {"id": "sync-2", "timestamp": 3.12},
        {"id": "sync-3", "timestamp": 5.12}
      ]
    }
  ]
}
```

Paths are relative to the manifest. Run `modalityops analyze manifest.json --manifest`. This example illustrates the contract; replace the markers with measured event times. Never invent events to force an alignment.

| Format | Adapter behavior |
|---|---|
| CSV | First column `timestamp`, remaining column names are channels; declare `sample_rate` and `unit`. Empty values become null. |
| WAV | Retains channels; normalizes unsigned/integer PCM correctly; timestamps start at sample zero. No wall-clock identity is inferred. |
| MP4/MKV/MOV | Optional PyAV; uses actual `PTS × time_base`, not frame index divided by FPS. Reduces frames to mean luminance. Supply a nominal `sample_rate` when metadata cannot define the intended cadence. |
| EDF/BDF/FIF/BrainVision | Optional MNE; selects EEG channels, converts volts to µV, uses recording-relative time. Event associations are supplied explicitly. BrainVision sidecar files must be present. |

Install optional readers with `python -m pip install -e '.[media]'`. The Docker runtime intentionally includes the core and API only; import optional media using a Python environment, then analyze the resulting canonical Session JSON.

## Limits in v0.1

- Up to 12 streams, 64 channels per stream, 128 events per clock.
- Up to 1 million samples per stream, 2 million scalar values per stream and 3 million per session.
- WAV files are capped at 32 MiB; video import is capped at 100,000 decoded frames.
- HTTP request limit: 32 MiB; browser report import limit: 8 MiB.
- These are windowed in-memory analyses. Export a smaller window for larger experiments; disk-backed streaming is not implemented.

Report summaries retain potentially sensitive identifiers and derived traces. Keep real-session exports private even if no raw recording is stored.
