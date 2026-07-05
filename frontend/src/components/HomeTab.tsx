"use client";

import { useEffect, useState } from "react";
import { getOverview } from "@/lib/api";

const T = {
  sage: "#7A8B6F",
  sageLight: "#A8B89E",
  amber: "#C4956A",
  terra: "#B5725E",
};

function getMode() {
  const h = new Date().getHours();
  if (h >= 6 && h < 11) return "morning";
  if (h >= 11 && h < 19) return "day";
  return "evening";
}

function formatSleep(minutes: number | null | undefined) {
  if (!minutes) return null;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function sleepColor(minutes: number | null | undefined) {
  if (!minutes) return T.sageLight;
  const h = minutes / 60;
  if (h >= 7) return T.sage;
  if (h >= 6) return T.amber;
  return T.terra;
}

function ScoreRing({
  value,
  max = 100,
  color,
  size = 52,
}: {
  value: number | null;
  max?: number;
  color: string;
  size?: number;
}) {
  if (!value) return null;
  const r = 20;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(1, value / max);
  const dash = pct * circ;
  return (
    <svg width={size} height={size} viewBox="0 0 52 52">
      <circle
        cx="26"
        cy="26"
        r={r}
        fill="none"
        stroke="var(--border)"
        strokeWidth="3"
      />
      <circle
        cx="26"
        cy="26"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 26 26)"
      />
      <text
        x="26"
        y="30"
        textAnchor="middle"
        fontSize="12"
        fontWeight="500"
        fill="var(--text)"
        fontFamily="'DM Sans', sans-serif"
      >
        {value}
      </text>
    </svg>
  );
}

function SleepCard({ sleep }: { sleep: Record<string, any> }) {
  const minutes = sleep.total_minutes;
  const score = sleep.sleep_score;
  const hrv = sleep.avg_hrv;
  const rhr = sleep.lowest_heart_rate;
  const dur = formatSleep(minutes);
  const col = sleepColor(minutes);

  return (
    <div
      className="card"
      style={{ borderLeft: `3px solid ${col}`, marginBottom: 12 }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <div className="stat-label" style={{ marginBottom: 6 }}>
            Last night
          </div>
          <div
            style={{
              fontSize: 28,
              fontWeight: 500,
              color: col,
              lineHeight: 1,
            }}
          >
            {dur || "—"}
          </div>
          {hrv && (
            <div
              style={{
                fontSize: 12,
                color: "var(--text2)",
                marginTop: 6,
                display: "flex",
                gap: 12,
              }}
            >
              <span>HRV {Math.round(hrv)}ms</span>
              {rhr && <span>RHR {Math.round(rhr)}</span>}
            </div>
          )}
        </div>
        {score && (
          <div style={{ textAlign: "center" }}>
            <ScoreRing
              value={Math.round(score)}
              color={score >= 80 ? T.sage : score >= 60 ? T.amber : T.terra}
            />
            <div style={{ fontSize: 10, color: "var(--text3)", marginTop: 2 }}>
              score
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricRow({
  label,
  value,
  unit,
  color,
}: {
  label: string;
  value: string | number | null;
  unit?: string;
  color: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "11px 0",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <span style={{ fontSize: 14, color: "var(--text2)" }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 500, color }}>
        {value ?? "—"}
        {value && unit && (
          <span style={{ fontSize: 12, color: "var(--text3)", marginLeft: 3 }}>
            {unit}
          </span>
        )}
      </span>
    </div>
  );
}

export default function HomeTab({
  onAskClaude,
}: {
  onAskClaude: (q: string) => void;
}) {
  const [overview, setOverview] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const mode = getMode();

  useEffect(() => {
    getOverview()
      .then(setOverview)
      .finally(() => setLoading(false));
  }, []);

  const latestDaily = overview?.daily?.[0] || {};
  const latestSleep = overview?.sleep?.[0] || {};

  const suggestions =
    mode === "morning"
      ? ["How did I sleep this week?", "What should I focus on today?"]
      : mode === "day"
      ? ["How is my HRV trending?", "When should I train today?"]
      : ["How did today compare to yesterday?", "What's affecting my sleep?"];

  return (
    <div style={{ padding: "20px 20px 0" }}>
      {loading && (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            padding: "40px 0",
          }}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--text3)"
            strokeWidth="2"
            className="animate-spin"
          >
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        </div>
      )}

      {!loading && overview && (
        <>
          {/* Sleep card — primary insight */}
          {latestSleep.total_minutes && (
            <SleepCard sleep={latestSleep} />
          )}

          {/* Today's metrics */}
          <div className="card" style={{ marginBottom: 12 }}>
            <div className="stat-label" style={{ marginBottom: 4 }}>
              Today
            </div>
            <MetricRow
              label="Readiness"
              value={latestDaily.readiness_score
                ? Math.round(latestDaily.readiness_score)
                : null}
              color={
                latestDaily.readiness_score >= 80
                  ? T.sage
                  : latestDaily.readiness_score >= 60
                  ? T.amber
                  : T.terra
              }
            />
            <MetricRow
              label="HRV"
              value={latestDaily.avg_hrv
                ? Math.round(latestDaily.avg_hrv)
                : null}
              unit="ms"
              color="var(--text)"
            />
            <MetricRow
              label="Steps"
              value={
                latestDaily.steps
                  ? Number(latestDaily.steps).toLocaleString()
                  : null
              }
              color="var(--text)"
            />
            <MetricRow
              label="Resting HR"
              value={latestDaily.resting_heart_rate
                ? Math.round(latestDaily.resting_heart_rate)
                : null}
              unit="bpm"
              color="var(--text)"
            />
          </div>

          {/* Ask suggestions */}
          <div style={{ marginBottom: 16 }}>
            <div
              className="stat-label"
              style={{ marginBottom: 8, paddingLeft: 2 }}
            >
              Ask about your data
            </div>
            <div
              className="card"
              style={{ display: "flex", flexDirection: "column", gap: 1, padding: "2px 16px" }}
            >
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => onAskClaude(s)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "13px 0",
                    borderBottom:
                      i < suggestions.length - 1
                        ? "1px solid var(--border)"
                        : "none",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    textAlign: "left",
                    width: "100%",
                  }}
                >
                  <span style={{ fontSize: 13.5, color: "var(--text)" }}>
                    {s}
                  </span>
                  <svg
                    width="7"
                    height="12"
                    viewBox="0 0 8 14"
                    fill="none"
                    style={{ flexShrink: 0, marginLeft: 12 }}
                  >
                    <path
                      d="M1 1l6 6-6 6"
                      stroke="var(--text3)"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      {!loading && !overview && (
        <div
          style={{
            padding: "40px 0",
            textAlign: "center",
            color: "var(--text2)",
            fontSize: 14,
          }}
        >
          No data yet. Sync a source to get started.
        </div>
      )}
    </div>
  );
}
