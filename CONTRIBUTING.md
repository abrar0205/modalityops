# Contributing

Start with a small issue describing the acquisition problem and a synthetic reproduction. Every new detector should document units, thresholds, expected false positives, missing-data behavior and a negative control.

Run the tests and formatters listed in the README. Add shared-event or timestamp edge cases when changing synchronization. Never use participant recordings in fixtures. Use normal descriptive commits, e.g. `Handle repeated frame timestamps`.

For new dataset adapters, document access conditions and licensing separately from the software license. Adapters must not automatically download or redistribute restricted datasets.
