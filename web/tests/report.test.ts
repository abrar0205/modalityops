import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { reportSchema, correctedTime, scenarios } from "../lib/report.ts";

for (const scenario of scenarios)
  test(`validates ${scenario.id} engine report`, () => {
    const report = reportSchema.parse(
      JSON.parse(
        readFileSync(
          new URL(`../public/demo/${scenario.id}.json`, import.meta.url),
          "utf8",
        ),
      ),
    );
    assert.equal(report.source, "synthetic");
    assert.equal(report.summary.stream_count, 3);
    for (const s of report.streams) {
      assert.equal(correctedTime(-10, s, true), null);
      const a = s.sync.anchors[3];
      assert.ok(
        Math.abs(correctedTime(a.observed_s, s, true)! - a.reference_s) < 1e-8,
      );
      assert.equal(correctedTime(a.observed_s, s, false), a.observed_s);
    }
  });
test("rejects malformed report instead of rendering unsafe geometry", () => {
  const r = JSON.parse(
    readFileSync(new URL("../public/demo/mixed.json", import.meta.url), "utf8"),
  );
  r.streams[0].preview[0].points[0].t = Infinity;
  assert.equal(reportSchema.safeParse(r).success, false);
});
test("rejects broken stream references", () => {
  const r = JSON.parse(
    readFileSync(new URL("../public/demo/mixed.json", import.meta.url), "utf8"),
  );
  r.issues[0].stream_id = "not-a-stream";
  assert.equal(reportSchema.safeParse(r).success, false);
});
