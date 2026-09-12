"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  AudioLines,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileJson,
  FlaskConical,
  GitBranch as Github,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  Play,
  Radio,
  RotateCcw,
  ScanLine,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
  Upload,
  Video,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  correctedTime,
  downloadJSON,
  formatNumber as fmt,
  reportSchema,
  scenarios,
  type Report,
  type StreamReport,
  type Issue,
} from "@/lib/report";
import initial from "@/public/demo/mixed.json";

const colors = { eeg: "#68d6e8", audio: "#b6dc86", video: "#d9a6ff" };
const icons = { eeg: Activity, audio: AudioLines, video: Video };
const base = process.env.NEXT_PUBLIC_BASE_PATH || "";
const initialReport = reportSchema.parse(initial);

function Waveform({
  stream,
  channel,
  corrected,
  window,
  cursor,
  setCursor,
  issues,
}: {
  stream: StreamReport;
  channel: number;
  corrected: boolean;
  window: [number, number];
  cursor: number;
  setCursor: (t: number) => void;
  issues: Issue[];
}) {
  const points = stream.preview[channel]?.points || [],
    [start, end] = window,
    width = 900,
    height = 90;
  const project = (t: number) => ((t - start) / (end - start)) * width;
  const amplitude = Math.max(0.0001, ...points.map((p) => Math.abs(p.v || 0)));
  let pen = false,
    lastTime: number | null = null;
  const gaps = issues.filter((i) =>
    ["SAMPLE_GAP", "TIMESTAMP_ORDER", "MISSING_VALUES"].includes(i.code),
  );
  const path = points
    .map((p) => {
      const t = correctedTime(p.t, stream, corrected);
      const crosses =
        lastTime !== null &&
        gaps.some((g) => lastTime! <= g.start_s && p.t >= g.end_s);
      lastTime = p.t;
      if (t === null || p.v === null || t < start || t > end) {
        pen = false;
        return "";
      }
      const command = pen && !crosses ? "L" : "M";
      pen = true;
      return `${command}${project(t).toFixed(2)},${(height / 2 - (p.v / amplitude) * 34).toFixed(2)}`;
    })
    .join(" ");
  const Icon = icons[stream.modality];
  return (
    <div className="signal-row">
      <div className="signal-label">
        <span
          className="signal-icon"
          style={{ color: colors[stream.modality] }}
        >
          <Icon size={17} />
        </span>
        <div>
          <strong>{stream.preview[channel]?.name}</strong>
          <span>
            {stream.modality.toUpperCase()} · {stream.unit}
          </span>
        </div>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="wave-svg"
        role="img"
        aria-label={`${stream.id} ${stream.preview[channel]?.name} signal from ${start.toFixed(1)} to ${end.toFixed(1)} seconds`}
        onPointerDown={(e) => {
          const b = e.currentTarget.getBoundingClientRect();
          setCursor(start + ((e.clientX - b.left) / b.width) * (end - start));
        }}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((x) => (
          <line
            key={x}
            x1={x * width}
            x2={x * width}
            y1={0}
            y2={height}
            stroke="#26323f"
            strokeDasharray="3 5"
          />
        ))}
        <line
          x1={0}
          x2={width}
          y1={height / 2}
          y2={height / 2}
          stroke="#26323f"
        />
        {issues
          .filter(
            (i) =>
              ["FLATLINE", "AUDIO_CLIPPING", "SAMPLE_GAP"].includes(i.code) &&
              (!i.channel || i.channel === stream.preview[channel]?.name),
          )
          .map((i) => {
            const a = correctedTime(i.start_s, stream, corrected),
              b = correctedTime(i.end_s, stream, corrected);
            return a !== null && b !== null ? (
              <rect
                key={i.id}
                x={Math.max(0, project(a))}
                y={0}
                width={Math.max(
                  0,
                  Math.min(width, project(b)) - Math.max(0, project(a)),
                )}
                height={height}
                fill="#f5b654"
                opacity={0.09}
              />
            ) : null;
          })}
        <path
          d={path}
          fill="none"
          stroke={colors[stream.modality]}
          strokeWidth={1.15}
          vectorEffect="non-scaling-stroke"
          opacity={0.9}
        />
        {cursor >= start && cursor <= end && (
          <line
            x1={project(cursor)}
            x2={project(cursor)}
            y1={0}
            y2={height}
            stroke="#edf4fa"
            opacity={0.65}
            strokeDasharray="4 3"
          />
        )}
      </svg>
      <span className="amplitude mono">
        ±{fmt(amplitude, stream.modality === "eeg" ? 0 : 2)}
      </span>
    </div>
  );
}
function ClockPlot({
  stream,
  corrected,
}: {
  stream: StreamReport;
  corrected: boolean;
}) {
  const anchors = stream.sync.anchors;
  if (!anchors.length)
    return <div className="empty-small">{stream.sync.reason}</div>;
  const times = anchors.map((a) => a.reference_s),
    values = anchors.map((a) => (corrected ? a.residual_ms : a.lag_ms)),
    minT = Math.min(...times),
    spanT = Math.max(1, Math.max(...times) - minT),
    minY = Math.min(...values, 0),
    spanY = Math.max(1, Math.max(...values, 0) - minY);
  const x = (t: number) => 55 + ((t - minT) / spanT) * 620,
    y = (v: number) => 125 - ((v - minY) / spanY) * 95;
  return (
    <svg
      viewBox="0 0 720 170"
      className="clock-plot"
      role="img"
      aria-label={`${stream.id} ${corrected ? "fit residual" : "clock offset"} in milliseconds at shared events`}
    >
      {[0, 0.5, 1].map((k) => (
        <g key={k}>
          <line
            x1={55}
            x2={675}
            y1={125 - k * 95}
            y2={125 - k * 95}
            stroke="#293542"
            strokeDasharray="3 5"
          />
          <text x={45} y={129 - k * 95} textAnchor="end">
            {fmt(minY + k * spanY, 1)}
          </text>
        </g>
      ))}
      <line x1={55} x2={675} y1={y(0)} y2={y(0)} stroke="#6b7b8e" />
      {anchors.map((a, i) => (
        <circle
          key={i}
          cx={x(a.reference_s)}
          cy={y(values[i])}
          r={4}
          fill={a.inlier ? colors[stream.modality] : "#f7b955"}
        >
          <title>
            {fmt(a.reference_s)} s: {fmt(values[i], 4)} ms ·{" "}
            {a.inlier ? "inlier" : "rejected"}
          </title>
        </circle>
      ))}
      {[0, 0.5, 1].map((k) => (
        <text key={k} x={55 + k * 620} y={150} textAnchor="middle">
          {fmt(minT + k * spanT, 1)} s
        </text>
      ))}
      <text x={12} y={18}>
        ms
      </text>
    </svg>
  );
}

export default function Workbench() {
  const [report, setReport] = useState<Report>(initialReport),
    [scenario, setScenario] = useState<string>("mixed"),
    [tab, setTab] = useState("timeline"),
    [corrected, setCorrected] = useState(false),
    [cursor, setCursor] = useState(15),
    [zoom, setZoom] = useState("full");
  const [mode, setMode] = useState<"demo" | "local">("demo"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("Ready · synthetic benchmark loaded"),
    [filter, setFilter] = useState("all"),
    [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [seed, setSeed] = useState(42),
    [offset, setOffset] = useState(180),
    [drift, setDrift] = useState(120),
    [history, setHistory] = useState<{ id: string; title: string }[]>([]),
    [expanded, setExpanded] = useState(false);
  const importRef = useRef<HTMLInputElement>(null),
    sessionRef = useRef<HTMLInputElement>(null),
    requestRef = useRef(0);
  const config = scenarios.find((s) => s.id === scenario) || scenarios[0];
  const times = useMemo(
    () =>
      report.streams.flatMap((s) => s.preview[0]?.points.map((p) => p.t) || []),
    [report],
  );
  const minTime = times.length ? Math.min(...times) : 0,
    maxTime = Math.max(minTime + 0.001, ...(times.length ? times : [1])),
    half =
      zoom === "full"
        ? (maxTime - minTime) / 2
        : Math.min(Number(zoom), maxTime - minTime) / 2;
  const middle =
    zoom === "full"
      ? (minTime + maxTime) / 2
      : Math.max(minTime + half, Math.min(maxTime - half, cursor));
  const window: [number, number] = [
    Math.max(minTime, middle - half),
    Math.min(maxTime, middle + half),
  ];
  const knownDrifts = report.streams.flatMap((s) =>
    s.sync.drift_ppm == null ? [] : [Math.abs(s.sync.drift_ppm)],
  );
  const maxDrift = knownDrifts.length ? Math.max(...knownDrifts) : null,
    findings = report.issues.filter(
      (i) => filter === "all" || i.stream_id === filter,
    );
  const accept = useCallback((data: unknown, message: string) => {
    const r = reportSchema.parse(data);
    setReport(r);
    setCorrected(false);
    setSelectedIssue(null);
    setFilter("all");
    setZoom("full");
    const points = r.streams.flatMap(
      (s) => s.preview[0]?.points.map((p) => p.t) || [],
    );
    setCursor(
      points.length ? (Math.min(...points) + Math.max(...points)) / 2 : 0,
    );
    setNotice(message);
    return r;
  }, []);
  useEffect(() => {
    let alive = true;
    fetch(`${base}/api/v1/health`, { signal: AbortSignal.timeout(2500) })
      .then((r) => (r.ok ? r.json() : null))
      .then((value) => {
        const data = value as { mode?: string; status?: string } | null;
        if (alive && data?.mode === "local" && data?.status === "ok")
          setMode("local");
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  const refreshHistory = useCallback(async () => {
    try {
      const r = await fetch(`${base}/api/v1/reports`);
      if (r.ok) {
        const items = await r.json();
        if (Array.isArray(items)) setHistory(items);
      }
    } catch {}
  }, []);
  useEffect(() => {
    if (mode === "local") void refreshHistory();
  }, [mode, refreshHistory]);
  const loadScenario = useCallback(
    async (id: string) => {
      if (!scenarios.some((s) => s.id === id))
        throw new Error("Unknown scenario");
      const request = ++requestRef.current;
      setBusy(true);
      setError("");
      try {
        const response = await fetch(
          mode === "local" ? `${base}/api/v1/demo` : `${base}/demo/${id}.json`,
          mode === "local"
            ? {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  scenario: id,
                  seed,
                  offset_ms: offset,
                  drift_ppm: drift,
                }),
                signal: AbortSignal.timeout(60000),
              }
            : {},
        );
        if (!response.ok)
          throw new Error(`Analysis could not be loaded (${response.status}).`);
        const data = await response.json();
        if (request !== requestRef.current) return null;
        const r = accept(
          data,
          mode === "local"
            ? "Analysis complete · saved locally"
            : "Scenario loaded · precomputed with the Python engine",
        );
        setScenario(id);
        if (mode === "local") void refreshHistory();
        return r;
      } catch (e) {
        if (request === requestRef.current)
          setError(e instanceof Error ? e.message : "Unable to load report");
        return null;
      } finally {
        if (request === requestRef.current) setBusy(false);
      }
    },
    [mode, seed, offset, drift, accept, refreshHistory],
  );
  const loadRef = useRef(loadScenario);
  loadRef.current = loadScenario;
  const reportRef = useRef(report);
  reportRef.current = report;
  useEffect(() => {
    const context = (
      document as Document & {
        modelContext?: {
          registerTool: (
            tool: unknown,
            options: { signal: AbortSignal },
          ) => void | Promise<void>;
        };
      }
    ).modelContext;
    if (!context) return;
    const lifecycle = new AbortController();
    const register = (tool: unknown) => {
      try {
        void Promise.resolve(
          context.registerTool(tool, { signal: lifecycle.signal }),
        ).catch(() => {});
      } catch {}
    };
    register({
      name: "load_synthetic_scenario",
      description:
        "Load a synthetic scenario into the visible workbench; runs the local engine when connected.",
      inputSchema: {
        type: "object",
        properties: {
          scenario: { type: "string", enum: scenarios.map((s) => s.id) },
        },
        required: ["scenario"],
        additionalProperties: false,
      },
      annotations: { readOnlyHint: false },
      async execute(input: unknown) {
        const v = input as { scenario?: unknown };
        if (
          !v ||
          typeof v.scenario !== "string" ||
          !scenarios.some((s) => s.id === v.scenario)
        )
          throw new Error("Invalid scenario");
        const r = await loadRef.current(v.scenario);
        if (!r) throw new Error("Scenario unavailable");
        return { id: r.id, summary: r.summary };
      },
    });
    register({
      name: "read_analysis_summary",
      description: "Read the report currently displayed.",
      inputSchema: {
        type: "object",
        properties: {},
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true },
      execute() {
        return {
          id: reportRef.current.id,
          source: reportRef.current.source,
          summary: reportRef.current.summary,
        };
      },
    });
    return () => lifecycle.abort();
  }, []);
  async function importFile(file: File | undefined, raw = false) {
    if (!file) return;
    setError("");
    if (file.size > (raw ? 32 : 8) * 1024 * 1024) {
      setError(`File exceeds the ${raw ? 32 : 8} MiB limit.`);
      return;
    }
    setBusy(true);
    try {
      const text = await file.text();
      let data: unknown = JSON.parse(text);
      if (raw) {
        if (mode !== "local")
          throw new Error("Session analysis requires the local backend.");
        const r = await fetch(`${base}/api/v1/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: text,
          signal: AbortSignal.timeout(60000),
        });
        if (!r.ok)
          throw new Error(
            `Session rejected (${r.status}). Check the Session schema.`,
          );
        data = await r.json();
        void refreshHistory();
      }
      accept(
        data,
        raw
          ? "Session analyzed locally · raw data not persisted"
          : "Report opened in this browser · no file uploaded",
      );
    } catch (e) {
      setError(
        e instanceof Error && !e.message.startsWith("[")
          ? e.message
          : "Invalid report: expected a ModalityOps 1.0 report.",
      );
    } finally {
      setBusy(false);
      if (importRef.current) importRef.current.value = "";
      if (sessionRef.current) sessionRef.current.value = "";
    }
  }
  function focusIssue(i: Issue) {
    setSelectedIssue(i);
    setCorrected(false);
    setCursor((i.start_s + i.end_s) / 2);
    setZoom("5");
    setTab("timeline");
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#workbench">
        Skip to workbench
      </a>
      <header className="masthead">
        <a className="brand" href={`${base}/`} aria-label="ModalityOps home">
          <span className="brand-mark">
            <Activity size={23} />
          </span>
          modality<span>ops</span>
          <small>v0.1</small>
        </a>
        <div className="masthead-right">
          <span className="mode-chip">
            <LockKeyhole size={13} />
            {mode === "local"
              ? "Local engine connected"
              : "Private-data safe demo"}
          </span>
          <Dialog>
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label="How ModalityOps works"
              >
                <CircleHelp size={18} />
              </Button>
            </DialogTrigger>
            <DialogContent className="help-dialog">
              <DialogHeader>
                <DialogTitle>
                  One timeline. Evidence you can inspect.
                </DialogTitle>
                <DialogDescription>
                  Check acquisition quality before you trust a multimodal
                  analysis.
                </DialogDescription>
              </DialogHeader>
              <ol className="help-steps">
                <li>
                  <strong>Choose a recording.</strong> Explore a synthetic
                  scenario, open an exported report, or analyze a Session JSON
                  with the local engine.
                </li>
                <li>
                  <strong>Investigate findings.</strong> Click a finding to
                  inspect its interval. Switch between raw device clocks and
                  estimated reference time.
                </li>
                <li>
                  <strong>Inspect clock evidence.</strong> Shared event IDs
                  anchor a robust affine fit. Unrelated EEG and audio are never
                  correlated to invent alignment.
                </li>
                <li>
                  <strong>Export, without rewriting.</strong> Download the
                  report and correction manifest. Raw recordings remain
                  unchanged.
                </li>
              </ol>
              <p className="muted">
                Research infrastructure, not a diagnostic system. The demo
                contains no human recordings.
              </p>
            </DialogContent>
          </Dialog>
          <a
            className="github-link"
            href="https://github.com/abrar0205/modalityops"
            target="_blank"
            rel="noreferrer"
          >
            <Github size={17} />
            <span>Source</span>
          </a>
        </div>
      </header>
      <main id="workbench">
        <div className="page-heading">
          <div>
            <div className="eyebrow">
              <span>WORKSPACE</span>
              <ChevronRight size={12} />
              ACQUISITION QA
            </div>
            <h1>
              Session diagnostics<span className="heading-dot">.</span>
            </h1>
            <p>Find the faults between recording and discovery.</p>
          </div>
          <div className="heading-actions">
            <input
              ref={importRef}
              className="sr-only"
              type="file"
              accept=".json,application/json"
              onChange={(e) => void importFile(e.target.files?.[0])}
            />
            <input
              ref={sessionRef}
              className="sr-only"
              type="file"
              accept=".json,application/json"
              onChange={(e) => void importFile(e.target.files?.[0], true)}
            />
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => importRef.current?.click()}
            >
              <Upload size={15} />
              Open report
            </Button>
            <Button
              disabled={busy}
              onClick={() => downloadJSON(report, `${report.id}-report.json`)}
            >
              <ArrowDownToLine size={15} />
              Export report
            </Button>
          </div>
        </div>
        {error && (
          <div className="error-banner" role="alert">
            <TriangleAlert size={18} />
            {error}
            <button onClick={() => setError("")}>Dismiss</button>
          </div>
        )}
        <div className="workbench-grid">
          <aside className="lab-panel panel">
            <div className="panel-title">
              <FlaskConical size={17} />
              <h2>Fault laboratory</h2>
              <span className="tiny-tag">SYNTHETIC</span>
            </div>
            <div className="lab-content">
              <label className="field-label" id="scenario-label">
                Test scenario
              </label>
              <Select value={scenario} onValueChange={setScenario}>
                <SelectTrigger
                  className="scenario-select"
                  aria-labelledby="scenario-label"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {scenarios.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="scenario-description">{config.description}</p>
              <div className="fault-preview">
                <div>
                  <span className="mini-label">EXPERIMENT</span>
                  <strong className="mono">{config.code}</strong>
                </div>
                <FlaskConical size={34} strokeWidth={1} />
                <span className="fault-caption">
                  Known faults.
                  <br />
                  Measurable recovery.
                </span>
              </div>
              <div className="parameters">
                <div className="field-row">
                  <label htmlFor="seed">Random seed</label>
                  <input
                    id="seed"
                    type="number"
                    min={0}
                    max={2147483647}
                    value={seed}
                    disabled={mode === "demo" || busy}
                    onChange={(e) => setSeed(Number(e.target.value))}
                  />
                </div>
                <div className="field-row">
                  <label htmlFor="offset">
                    EEG offset <small>ms</small>
                  </label>
                  <input
                    id="offset"
                    type="number"
                    min={-2000}
                    max={2000}
                    value={offset}
                    disabled={mode === "demo" || busy}
                    onChange={(e) => setOffset(Number(e.target.value))}
                  />
                </div>
                <div className="field-row">
                  <label htmlFor="drift">
                    EEG drift <small>ppm</small>
                  </label>
                  <input
                    id="drift"
                    type="number"
                    min={-2000}
                    max={2000}
                    value={drift}
                    disabled={mode === "demo" || busy}
                    onChange={(e) => setDrift(Number(e.target.value))}
                  />
                </div>
              </div>
              <Button
                className="run-button"
                disabled={busy}
                onClick={() => void loadScenario(scenario)}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <Play size={15} fill="currentColor" />
                )}
                {busy
                  ? "Working…"
                  : mode === "local"
                    ? "Run analysis"
                    : "Load scenario"}
              </Button>
              <p className="local-note">
                {mode === "demo"
                  ? "Five reproducible reports, computed by the Python engine. Run locally to change fault parameters."
                  : "Computed on this machine. Reports are saved locally; raw sessions are not stored."}
              </p>
              <div className="lab-divider" />
              <h3 className="mini-label">CONNECTED MODALITIES</h3>
              <div className="modality-list">
                {report.streams.map((s) => {
                  const Icon = icons[s.modality];
                  return (
                    <div key={s.id}>
                      <span style={{ color: colors[s.modality] }}>
                        <Icon size={17} />
                        {s.modality.toUpperCase()}
                      </span>
                      <span className="mono">
                        {s.sample_rate.toLocaleString()}{" "}
                        {s.modality === "video" ? "fps" : "Hz"}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="privacy-note">
                <ShieldCheck size={20} />
                <div>
                  <strong>Local by design</strong>
                  <p>
                    No participant data in this demo. Opened reports stay in
                    your browser.
                  </p>
                </div>
              </div>
              {mode === "local" && (
                <>
                  <Button
                    variant="outline"
                    className="w-full"
                    disabled={busy}
                    onClick={() => sessionRef.current?.click()}
                  >
                    <FileJson size={15} />
                    Analyze session JSON
                  </Button>
                  {history.length > 0 && (
                    <div className="history">
                      <h3 className="mini-label">LOCAL RUN HISTORY</h3>
                      {history.slice(0, 5).map((h) => (
                        <button
                          key={h.id}
                          onClick={async () => {
                            try {
                              const r = await fetch(
                                `${base}/api/v1/reports/${encodeURIComponent(h.id)}`,
                              );
                              if (!r.ok) throw new Error();
                              accept(
                                await r.json(),
                                "Saved local report opened",
                              );
                            } catch {
                              setError("Could not open saved report.");
                            }
                          }}
                        >
                          <Clock3 size={13} />
                          {h.title}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
              <a
                className="docs-link"
                href="https://github.com/abrar0205/modalityops#quick-start"
                target="_blank"
                rel="noreferrer"
              >
                <BookOpen size={15} />
                Run on your own data
                <ChevronRight size={14} />
              </a>
            </div>
          </aside>
          <section className="results-column" aria-busy={busy}>
            <div className="metric-grid">
              <div className="metric">
                <span>
                  Recording streams
                  <Layers3 size={15} />
                </span>
                <strong>
                  {report.summary.stream_count}
                  <small>streams</small>
                </strong>
                <p>
                  {report.streams.reduce((n, s) => n + s.preview.length, 0)}{" "}
                  channels inspected
                </p>
              </div>
              <div className="metric">
                <span>
                  Recording span
                  <Clock3 size={15} />
                </span>
                <strong>
                  {fmt(
                    Math.max(...report.streams.map((s) => s.qc.duration_s)),
                    1,
                  )}
                  <small>sec</small>
                </strong>
                <p>Independent device clocks</p>
              </div>
              <div
                className={`metric ${report.issues.length ? "metric-warning" : ""}`}
              >
                <span>
                  Quality findings
                  <TriangleAlert size={15} />
                </span>
                <strong>
                  {report.summary.issue_count}
                  <small>
                    {report.summary.error_count
                      ? `${report.summary.error_count} errors`
                      : report.issues.length
                        ? "to inspect"
                        : "clear"}
                  </small>
                </strong>
                <p>
                  {report.issues.length
                    ? "Evidence-linked flags"
                    : "No flags at these thresholds"}
                </p>
              </div>
              <div className="metric">
                <span>
                  Maximum clock drift
                  <Radio size={15} />
                </span>
                <strong>
                  {fmt(maxDrift, 1)}
                  <small>ppm</small>
                </strong>
                <p>
                  {report.summary.alignment_count}/{report.summary.stream_count}{" "}
                  clocks estimable
                </p>
              </div>
            </div>
            <section className="analysis-panel panel">
              <div className="recording-header">
                <div>
                  <div className="recording-title">
                    <span className="recording-icon">
                      <ScanLine size={17} />
                    </span>
                    <h2>{report.title}</h2>
                    <span className="source-badge">{report.source}</span>
                  </div>
                  <p className="mono">
                    {report.id}
                    <span>•</span>engine {report.engine_version}
                  </p>
                </div>
                <span className="evidence-badge">
                  <Check size={13} />
                  Hashed provenance
                </span>
              </div>
              <Tabs value={tab} onValueChange={setTab}>
                <TabsList variant="line" className="workspace-tabs">
                  <TabsTrigger value="timeline">
                    <Activity size={15} />
                    Timeline
                  </TabsTrigger>
                  <TabsTrigger value="clocks">
                    <Clock3 size={15} />
                    Clock evidence
                  </TabsTrigger>
                  <TabsTrigger value="quality">
                    <SlidersHorizontal size={15} />
                    Channel quality
                  </TabsTrigger>
                  <TabsTrigger value="details">
                    <FileJson size={15} />
                    Run details
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="timeline" className="tab-body">
                  <div className="timeline-toolbar">
                    <div className="toggle-label">
                      <Switch
                        id="corrected"
                        checked={corrected}
                        onCheckedChange={setCorrected}
                      />
                      <label htmlFor="corrected">
                        {corrected ? "Reference time" : "Raw device time"}
                      </label>
                    </div>
                    <div className="timeline-tools">
                      <span className="mono cursor-readout">
                        {fmt(cursor, 3)} s
                      </span>
                      <Select value={zoom} onValueChange={setZoom}>
                        <SelectTrigger
                          aria-label="Timeline zoom"
                          className="zoom-select"
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="full">Full recording</SelectItem>
                          <SelectItem value="5">5 s window</SelectItem>
                          <SelectItem value="1">1 s window</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Reset timeline"
                        onClick={() => {
                          setZoom("full");
                          setCursor((minTime + maxTime) / 2);
                        }}
                      >
                        <RotateCcw size={14} />
                      </Button>
                    </div>
                  </div>
                  <div className="time-axis">
                    <span>CHANNEL / UNIT</span>
                    <div>
                      {[0, 0.25, 0.5, 0.75, 1].map((x) => (
                        <span key={x}>
                          {fmt(window[0] + (window[1] - window[0]) * x, 1)} s
                        </span>
                      ))}
                    </div>
                    <span />
                  </div>
                  <div className="waveforms">
                    {report.streams.map((s) => (
                      <div className="stream-group" key={s.id}>
                        {s.preview.slice(0, expanded ? 64 : 2).map((ch, i) => (
                          <Waveform
                            key={ch.name}
                            stream={s}
                            channel={i}
                            corrected={corrected}
                            window={window}
                            cursor={cursor}
                            setCursor={setCursor}
                            issues={report.issues.filter(
                              (issue) => issue.stream_id === s.id,
                            )}
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                  <div className="scrubber">
                    <span className="mono">{fmt(minTime, 1)}</span>
                    <Slider
                      min={minTime}
                      max={maxTime}
                      step={0.01}
                      value={[cursor]}
                      onValueChange={(v) => setCursor(v[0])}
                      aria-label="Shared timeline cursor"
                    />
                    <span className="mono">{fmt(maxTime, 1)} s</span>
                  </div>
                  <div className="timeline-footer">
                    <span>
                      <span className="legend-box" />
                      Flagged interval
                      <span className="legend-line" />
                      Shared cursor
                    </span>
                    <button onClick={() => setExpanded((v) => !v)}>
                      {expanded ? "Show fewer channels" : "Show all channels"}
                    </button>
                  </div>
                  <p className="trace-note">
                    {corrected
                      ? "Correction preview is restricted to the shared-event span; regions outside it are not inferred."
                      : "Each trace uses recorded device timestamps. Select a finding to inspect its interval."}{" "}
                    Min/max traces are display summaries.
                  </p>
                </TabsContent>
                <TabsContent value="clocks" className="tab-body">
                  <div className="section-intro">
                    <div>
                      <h3>Clock fits, not guesses</h3>
                      <p>
                        Device time = scale × reference time + offset. Only
                        shared events establish alignment.
                      </p>
                    </div>
                    <div className="toggle-label">
                      <Switch
                        id="residuals"
                        checked={corrected}
                        onCheckedChange={setCorrected}
                      />
                      <label htmlFor="residuals">Show residuals</label>
                    </div>
                  </div>
                  {report.streams.map((s) => (
                    <div className="clock-card" key={s.id}>
                      <div className="clock-card-title">
                        <strong style={{ color: colors[s.modality] }}>
                          {s.id.toUpperCase()}
                        </strong>
                        <span
                          className={
                            s.sync.status === "estimated"
                              ? "status-ok"
                              : "status-warning"
                          }
                        >
                          {s.sync.status === "estimated"
                            ? `${s.sync.inliers}/${s.sync.matched_events} inlier events`
                            : "Insufficient evidence"}
                        </span>
                      </div>
                      <div className="clock-stats">
                        <div>
                          <span>Offset</span>
                          <strong>
                            {fmt(s.sync.offset_ms, 3)}
                            <small> ms</small>
                          </strong>
                        </div>
                        <div>
                          <span>Drift</span>
                          <strong>
                            {fmt(s.sync.drift_ppm, 2)}
                            <small> ppm</small>
                          </strong>
                        </div>
                        <div>
                          <span>Fit residual RMS</span>
                          <strong>
                            {fmt(s.sync.residual_ms, 4)}
                            <small> ms</small>
                          </strong>
                        </div>
                      </div>
                      <ClockPlot stream={s} corrected={corrected} />
                      <p className="clock-foot">
                        {s.sync.valid_range_s
                          ? `Event span: ${fmt(s.sync.valid_range_s[0])}–${fmt(s.sync.valid_range_s[1])} s · Drift standard error: ${fmt(s.sync.drift_standard_error_ppm, 4)} ppm`
                          : s.sync.reason}
                      </p>
                    </div>
                  ))}
                  <p className="trace-note">
                    Exact synthetic markers produce near-zero fit residuals.
                    This is a software recovery test, not real-device accuracy
                    or physiological synchrony.
                  </p>
                </TabsContent>
                <TabsContent value="quality" className="tab-body">
                  <div className="section-intro">
                    <div>
                      <h3>Every channel, inspectable</h3>
                      <p>
                        Amplitude metrics retain native units. A dash means the
                        metric was not computed.
                      </p>
                    </div>
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Channel</TableHead>
                        <TableHead>RMS</TableHead>
                        <TableHead>Peak</TableHead>
                        <TableHead>Clipped</TableHead>
                        <TableHead>Flatline</TableHead>
                        <TableHead>Line noise</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {report.streams.flatMap((s) =>
                        s.qc.channels.map((c) => (
                          <TableRow key={`${s.id}-${c.name}`}>
                            <TableCell>
                              <strong style={{ color: colors[s.modality] }}>
                                {c.name}
                              </strong>
                              <small className="table-sub">
                                {s.id} · {s.unit}
                              </small>
                            </TableCell>
                            <TableCell className="mono">{fmt(c.rms)}</TableCell>
                            <TableCell className="mono">
                              {fmt(c.peak)}
                            </TableCell>
                            <TableCell
                              className={
                                c.clipped_fraction > 0
                                  ? "warning-text mono"
                                  : "mono"
                              }
                            >
                              {fmt(c.clipped_fraction * 100, 1)}%
                            </TableCell>
                            <TableCell
                              className={
                                c.flatline_seconds > 0
                                  ? "warning-text mono"
                                  : "mono"
                              }
                            >
                              {fmt(c.flatline_seconds, 1)} s
                            </TableCell>
                            <TableCell
                              className={
                                (c.line_noise_fraction || 0) > 0.2
                                  ? "warning-text mono"
                                  : "mono"
                              }
                            >
                              {c.line_noise_fraction === null
                                ? "—"
                                : `${fmt(c.line_noise_fraction * 100, 1)}%`}
                            </TableCell>
                          </TableRow>
                        )),
                      )}
                    </TableBody>
                  </Table>
                  <div className="quality-explainer">
                    <ShieldCheck size={21} />
                    <p>
                      Flags identify acquisition conditions, not medical
                      findings. Flatlines may reflect silence or sensor failure.
                      Line-noise fractions are skipped when gaps or invalid
                      values make the spectral estimate unreliable.
                    </p>
                  </div>
                </TabsContent>
                <TabsContent value="details" className="tab-body">
                  <div className="section-intro">
                    <div>
                      <h3>Reproduce this result</h3>
                      <p>
                        Fingerprints, thresholds and corrections travel with
                        every report.
                      </p>
                    </div>
                  </div>
                  <dl className="provenance">
                    <dt>Input SHA-256</dt>
                    <dd className="mono">{report.provenance.input_sha256}</dd>
                    <dt>Config SHA-256</dt>
                    <dd className="mono">{report.provenance.config_sha256}</dd>
                    <dt>Reference clock</dt>
                    <dd>{report.reference_clock}</dd>
                    <dt>Raw data modified</dt>
                    <dd className="status-ok">No — correction manifest only</dd>
                  </dl>
                  <h4 className="mini-label">ANALYSIS CONFIGURATION</h4>
                  <pre>{JSON.stringify(report.provenance.config, null, 2)}</pre>
                  <Button
                    variant="outline"
                    onClick={() =>
                      downloadJSON(
                        report.correction_manifest,
                        `${report.id}-correction.json`,
                      )
                    }
                  >
                    <ArrowDownToLine size={16} />
                    Download correction manifest
                  </Button>
                  <ul className="limitations">
                    {report.limitations.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                  {report.benchmark && (
                    <div className="benchmark-result">
                      <FlaskConical size={20} />
                      <div>
                        <strong>Synthetic ground-truth recovery</strong>
                        <p>
                          Maximum offset error:{" "}
                          {fmt(report.benchmark.max_offset_error_ms, 6)} ms ·
                          Maximum drift error:{" "}
                          {fmt(report.benchmark.max_drift_error_ppm, 6)} ppm
                        </p>
                        <small>{report.benchmark.description}</small>
                      </div>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </section>
            <section className="findings-panel panel">
              <div className="findings-heading">
                <div>
                  <TriangleAlert size={17} />
                  <h2>Acquisition findings</h2>
                  <span className="count-badge">{report.issues.length}</span>
                </div>
                <Select value={filter} onValueChange={setFilter}>
                  <SelectTrigger
                    className="filter-select"
                    aria-label="Filter findings by stream"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All streams</SelectItem>
                    {report.streams.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.id.toUpperCase()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {findings.length === 0 ? (
                <div className="empty-findings">
                  <ShieldCheck size={30} />
                  <strong>No findings for this selection</strong>
                  <p>
                    Nothing exceeded these thresholds. This is not a guarantee
                    of scientific validity.
                  </p>
                </div>
              ) : (
                <div className="finding-list">
                  {findings.map((i) => (
                    <button
                      key={i.id}
                      className={`finding ${selectedIssue?.id === i.id ? "selected" : ""}`}
                      onClick={() => focusIssue(i)}
                    >
                      <span className={`severity ${i.severity}`}>
                        <TriangleAlert size={15} />
                      </span>
                      <div className="finding-copy">
                        <strong>
                          {i.code.replaceAll("_", " ").toLowerCase()}
                        </strong>
                        <p>{i.message}</p>
                      </div>
                      <span
                        className="finding-stream"
                        style={{
                          color:
                            colors[
                              report.streams.find((s) => s.id === i.stream_id)!
                                .modality
                            ],
                        }}
                      >
                        {i.stream_id}
                        {i.channel ? ` / ${i.channel}` : ""}
                      </span>
                      <span className="finding-time mono">
                        {fmt(i.start_s, 2)}–{fmt(i.end_s, 2)} s
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  ))}
                </div>
              )}
              {selectedIssue && (
                <div className="evidence-detail">
                  <strong>Evidence · {selectedIssue.code}</strong>
                  <div>
                    {Object.entries(selectedIssue.evidence).map(([k, v]) => (
                      <span key={k}>
                        {k.replaceAll("_", " ")}:{" "}
                        <b className="mono">
                          {typeof v === "number" ? fmt(v, 4) : String(v)}
                        </b>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </section>
            <div className="status-bar" role="status">
              <span>
                <Check size={13} />
                {notice}
              </span>
              <span>Read-only analysis · No clinical interpretation</span>
            </div>
          </section>
        </div>
        <footer className="page-footer">
          <span>
            MODALITYOPS <span>/</span> OBSERVE. ALIGN. VERIFY.
          </span>
          <a
            href="https://github.com/abrar0205/modalityops/blob/main/docs/methods.md"
            target="_blank"
            rel="noreferrer"
          >
            Methods & limitations
            <ChevronRight size={12} />
          </a>
        </footer>
      </main>
    </div>
  );
}
