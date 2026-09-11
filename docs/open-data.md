# Open-data policy

Software openness and dataset access are separate. The source code and generated fixtures are available under the repository license. No external dataset is bundled, automatically downloaded or implied to permit redistribution.

## Default: deterministic synthetic fixtures

EEG-like oscillations, audio tones and video luminance pulses are generated mathematically. Shared markers have known clock mappings. Faults include offsets, drift, lost frames, flatlines, line interference and clipping. These signals are engineering fixtures, not realistic models of cognition, speech or human behavior.

The test suite also generates its own MP4 and MNE FIF files at runtime to verify actual reader behavior. It never requires participant data.

## Optional real-data validation

The existing EDF/BDF/FIF/CSV adapters can analyze lawfully obtained public recordings locally. Keep original dataset attribution, access agreements and permitted-use restrictions with your local manifest. Do not label separately acquired EEG and audiovisual files as a synchronized session without shared timing evidence.

[K-EmoCon](https://zenodo.org/records/3931963) is relevant because it includes EEG and audiovisual recordings, but its files require approved access. It is **not** a freely redistributable default demo. No K-EmoCon adapter or access request is claimed as completed in this release.

Before adding a dataset-specific example, document its exact version, source URL/DOI, file checksums, license, consent/access restrictions and whether derived reports may be published. Use user-initiated downloads only after those terms are resolved.
