import { z } from "zod";
const finite = z.number().finite(),
  metric = finite.nullable(),
  text = z.string().max(500);
export const reportSchema = z
  .object({
    schema_version: z.literal("1.0"),
    engine_version: text,
    id: text,
    session_id: text,
    title: text,
    source: z.enum(["synthetic", "local", "open-data"]),
    reference_clock: text,
    summary: z.object({
      stream_count: z.number().int().min(1).max(12),
      issue_count: z.number().int().nonnegative(),
      error_count: z.number().int().nonnegative(),
      alignment_count: z.number().int().min(0).max(12),
    }),
    provenance: z.object({
      input_sha256: z.string().regex(/^[a-f0-9]{64}$/),
      config_sha256: z.string().regex(/^[a-f0-9]{64}$/),
      config: z.record(z.unknown()),
    }),
    streams: z
      .array(
        z.object({
          id: text,
          modality: z.enum(["eeg", "audio", "video"]),
          clock: text,
          unit: text,
          sample_rate: finite.positive(),
          qc: z.object({
            samples: z.number().int().positive(),
            duration_s: finite.nonnegative(),
            gap_count: z.number().int().nonnegative(),
            order_error_count: z.number().int().nonnegative(),
            interval_jitter_ms: metric,
            channels: z
              .array(
                z.object({
                  name: text,
                  rms: metric,
                  peak: metric,
                  missing_samples: z.number().int().nonnegative(),
                  clipped_fraction: finite.min(0).max(1),
                  flatline_seconds: finite.nonnegative(),
                  line_noise_fraction: metric,
                }),
              )
              .min(1)
              .max(64),
          }),
          sync: z.object({
            status: z.enum(["estimated", "unidentifiable"]),
            method: text,
            reason: text,
            matched_events: z.number().int().nonnegative(),
            offset_ms: metric,
            drift_ppm: metric,
            scale: finite.positive().nullable(),
            intercept_s: metric,
            residual_ms: metric,
            inliers: z.number().int().nonnegative(),
            valid_range_s: z.tuple([finite, finite]).nullable(),
            drift_standard_error_ppm: metric.optional(),
            anchors: z
              .array(
                z.object({
                  reference_s: finite,
                  observed_s: finite,
                  lag_ms: finite,
                  residual_ms: finite,
                  inlier: z.boolean(),
                }),
              )
              .max(128),
          }),
          preview: z
            .array(
              z.object({
                name: text,
                points: z.array(z.object({ t: finite, v: metric })).max(2000),
              }),
            )
            .min(1)
            .max(64),
        }),
      )
      .min(1)
      .max(12),
    issues: z
      .array(
        z.object({
          id: text,
          code: text,
          severity: z.enum(["warning", "error"]),
          stream_id: text,
          channel: text.nullable(),
          message: text,
          start_s: finite,
          end_s: finite,
          evidence: z.record(z.unknown()),
        }),
      )
      .max(5000),
    correction_manifest: z.object({
      schema_version: z.literal("1.0"),
      input_sha256: text,
      raw_data_modified: z.literal(false),
      corrections: z
        .array(
          z.object({
            stream_id: text,
            from_clock: text,
            to_clock: text,
            scale: finite.positive(),
            intercept_s: finite,
            valid_range_s: z.tuple([finite, finite]),
            formula: text,
          }),
        )
        .max(12),
    }),
    limitations: z.array(text).max(20),
    benchmark: z
      .object({
        description: text,
        ground_truth: z.record(
          z.object({
            offset_ms: finite,
            drift_ppm: finite,
            removed_samples: finite,
          }),
        ),
        max_offset_error_ms: finite,
        max_drift_error_ppm: finite,
      })
      .optional(),
  })
  .superRefine((r, c) => {
    const ids = new Set(r.streams.map((s) => s.id));
    if (
      ids.size !== r.streams.length ||
      r.summary.stream_count !== r.streams.length ||
      r.summary.issue_count !== r.issues.length
    )
      c.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Inconsistent report counts or identifiers",
      });
    for (const i of r.issues)
      if (!ids.has(i.stream_id))
        c.addIssue({ code: z.ZodIssueCode.custom, message: "Unknown stream" });
    for (const s of r.streams)
      if (
        s.sync.status === "estimated" &&
        (s.sync.scale === null ||
          s.sync.intercept_s === null ||
          s.sync.valid_range_s === null)
      )
        c.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Incomplete clock mapping",
        });
  });
export type Report = z.infer<typeof reportSchema>;
export type StreamReport = Report["streams"][number];
export type Issue = Report["issues"][number];
export const scenarios = [
  {
    id: "mixed",
    name: "Mixed acquisition faults",
    description: "Clock drift, signal corruption and lost video frames.",
    code: "SYN-005",
  },
  {
    id: "clock-drift",
    name: "Independent clock drift",
    description: "Three devices start apart and drift over time.",
    code: "SYN-002",
  },
  {
    id: "dropouts",
    name: "Video frame dropout",
    description: "A 400 ms interruption in the video timeline.",
    code: "SYN-003",
  },
  {
    id: "signal-quality",
    name: "Signal-quality faults",
    description: "EEG flatline, mains interference and audio clipping.",
    code: "SYN-004",
  },
  {
    id: "clean",
    name: "Clean reference session",
    description: "A control recording with no injected failures.",
    code: "SYN-001",
  },
] as const;
export function correctedTime(
  t: number,
  stream: StreamReport,
  corrected: boolean,
): number | null {
  if (!corrected) return t;
  const s = stream.sync;
  if (
    s.status !== "estimated" ||
    s.scale === null ||
    s.intercept_s === null ||
    !s.valid_range_s
  )
    return null;
  const time = (t - s.intercept_s) / s.scale;
  return time >= s.valid_range_s[0] && time <= s.valid_range_s[1] ? time : null;
}
export function downloadJSON(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function formatNumber(v: number | null | undefined, digits = 2) {
  return v == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      }).format(Math.abs(v) < 1e-8 ? 0 : v);
}
