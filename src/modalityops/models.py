"""Versioned, bounded contracts. All times are seconds in an explicit clock domain."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BoundedNumber = Annotated[float, Field(ge=-1e12, le=1e12)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Event(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    timestamp: BoundedNumber


class Stream(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    modality: Literal["eeg", "audio", "video"]
    clock: str = Field(min_length=1, max_length=80)
    sample_rate: float = Field(gt=0, le=192000)
    unit: Literal["uV", "normalized", "luminance"]
    channels: list[str] = Field(min_length=1, max_length=64)
    timestamps: list[BoundedNumber] = Field(min_length=2, max_length=1_000_000)
    values: list[list[BoundedNumber | None]] = Field(min_length=2, max_length=1_000_000)
    events: list[Event] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def validate_shape(self):
        if len(self.timestamps) != len(self.values):
            raise ValueError("timestamps and values must have equal lengths")
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("channel names must be unique")
        if len(self.timestamps) * len(self.channels) > 2_000_000:
            raise ValueError("stream exceeds 2 million scalar values; use a shorter window")
        if any(len(row) != len(self.channels) for row in self.values):
            raise ValueError("each sample must contain one value per channel")
        expected = {"eeg": "uV", "audio": "normalized", "video": "luminance"}
        if self.unit != expected[self.modality]:
            raise ValueError(f"{self.modality} requires unit {expected[self.modality]}")
        if len({e.id for e in self.events}) != len(self.events):
            raise ValueError("event IDs must be unique per stream")
        return self


class Session(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    title: str = Field(min_length=1, max_length=160)
    source: Literal["synthetic", "local", "open-data"] = "local"
    reference_clock: str = Field(min_length=1, max_length=80)
    reference_events: list[Event] = Field(default_factory=list, max_length=128)
    streams: list[Stream] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({s.id for s in self.streams}) != len(self.streams):
            raise ValueError("stream IDs must be unique")
        if len({e.id for e in self.reference_events}) != len(self.reference_events):
            raise ValueError("reference event IDs must be unique")
        if sum(len(s.values) * len(s.channels) for s in self.streams) > 3_000_000:
            raise ValueError("session exceeds 3 million scalar values")
        return self


class AnalysisConfig(StrictModel):
    gap_factor: float = Field(default=1.6, ge=1.1, le=10)
    flatline_seconds: float = Field(default=0.4, ge=0.05, le=10)
    audio_clip_level: float = Field(default=0.999, ge=0.5, le=1)
    eeg_saturation_uv: float = Field(default=5000, gt=0)
    line_frequency: Literal[50, 60] = 50
    anchor_tolerance_ms: float = Field(default=5, gt=0, le=100)


class DemoConfig(StrictModel):
    scenario: Literal["clean", "clock-drift", "dropouts", "signal-quality", "mixed"] = "mixed"
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    duration: float = Field(default=30, ge=10, le=60)
    offset_ms: float = Field(default=180, ge=-2000, le=2000)
    drift_ppm: float = Field(default=120, ge=-2000, le=2000)
