"use client";

import { useEffect, useState } from "react";
import {
  getRegimeShift,
  getYearOverYear,
  getConsistency,
  getAttribution,
  getSmartSuggestions,
  getBacBudget,
} from "@/lib/insights";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10.5,
        fontWeight: 500,
        letterSpacing: "0.07em",
        textTransform: "uppercase" as const,
        color: "var(--text3)",
        marginBottom: 6,
      }}
    >
      {children}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div
      style={{
        height: 96,
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        marginBottom: 12,
        opacity: 0.6,
      }}
    />
  );
}

function ErrorCard({ label, error }: { label: string; error: string }) {
  return (
    <div
      className="card"
      style={{
        borderLeft: "3px solid var(--terra)",
        marginBottom: 12,
        fontSize: 13,
        color: "var(--text2)",
      }}
    >
      <span style={{ color: "var(--terra)", fontWeight: 500 }}>{label}: </span>
      {error}
    </div>
  );
}

function RegimeShiftCard({ data }: { data: any }) {
  if (!data?.shift_detected) {
    return (
      <div className="card" style={{ marginBottom: 12 }}>
        <SectionLabel>Regime · is this real?</SectionLabel>
        <div style={{ fontSize: 15, color: "var(--text)" }}>
          No significant shifts detected
        </div>
        <div
          style={{
            fontSize: 13,
            color: "var(--text2)",
            marginTop: 4,
            lineHeight: 1.45,
          }}
        >
          Metrics within normal range — that's good news.
        </div>
      </div>
    );
  }

  const d = data.cohens_d ?? 0;
  const dir = d > 0 ? "↑ upward" : "↓ downward";

  return (
    <div
      className="card"
      style={{ borderLeft: "3px solid var(--sage)", marginBottom: 12 }}
    >
      <SectionLabel>Regime shift · is this real?</SectionLabel>
      <div style={{ fontSize: 17, fontWeight: 500, color: "var(--text)" }}>
        {data.metric_label} has shifted {dir}
      </div>
      <div
        style={{
          fontSize: 13,
          color: "var(--text2)",
          marginTop: 5,
          lineHeight: 1.45,
        }}
      >
        Your recent median is statistically distinct from your 60-day baseline
        (d = {Math.abs(d).toFixed(2)}).
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: 18,
          marginTop: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: "var(--text3)" }}>NOW</div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 500,
              color: "var(--sage)",
              lineHeight: 1,
            }}
          >
            {data.recent_median?.toFixed(1)}
            <span style={{ fontSize: 12, color: "var(--text3)" }}>
              {" "}
              {data.unit}
            </span>
          </div>
        </div>
        <div style={{ color: "var(--text3)", fontSize: 16, paddingBottom: 4 }}>
          →
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--text3)" }}>BASELINE</div>
          <div
            style={{
              fontSize: 22,
              fontWeight: 500,
              color: "var(--text2)",
              lineHeight: 1,
            }}
          >
            {data.baseline_median?.toFixed(1)}
            <span style={{ fontSize: 12, color: "var(--text3)" }}>
              {" "}
              {data.unit}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function YoYCard({ data }: { data: any }) {
  if (!data?.rows?.length) return null;
  const dirColor = (d: string) =>
    d === "better" ? "var(--sage)" : d === "worse" ? "var(--terra)" : "var(--text2)";
  const dirLabel = (d: string) =>
    d === "better" ? "↑ Better" : d === "worse" ? "↓ Worse" : "→ Same";

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <SectionLabel>Same time last year · seasonal check</SectionLabel>
      <div
        style={{
          display: "flex",
          fontSize: 10,
          color: "var(--text3)",
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          paddingBottom: 8,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <span style={{ flex: 1 }}>Metric</span>
        <span style={{ width: 56, textAlign: "right" }}>Now</span>
        <span style={{ width: 50, textAlign: "right" }}>Year ago</span>
        <span style={{ width: 66, textAlign: "right" }}>Verdict</span>
      </div>
      {data.rows.map((r: any, i: number) => (
        <div
          key={r.label}
          style={{
            display: "flex",
            alignItems: "center",
            padding: "8px 0",
            borderBottom:
              i < data.rows.length - 1 ? "1px solid var(--border)" : "none",
          }}
        >
          <span style={{ flex: 1, fontSize: 13, color: "var(--text)" }}>
            {r.label}
          </span>
          <span style={{ width: 56, textAlign: "right", fontSize: 13, color: "var(--text)" }}>
            {r.now}
          </span>
          <span style={{ width: 50, textAlign: "right", fontSize: 13, color: "var(--text3)" }}>
            {r.last_year}
          </span>
          <span
            style={{
              width: 66,
              textAlign: "right",
              fontSize: 12,
              color: dirColor(r.direction),
            }}
          >
            {dirLabel(r.direction)}
          </span>
        </div>
      ))}
    </div>
  );
}

function ConsistencyCard({ data }: { data: any }) {
  if (!data) return null;
  const isHigh = data.percentile >= 80;

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 8,
        }}
      >
        <SectionLabel>Sleep consistency</SectionLabel>
        {isHigh && (
          <span
            style={{
              fontSize: 11,
              color: "var(--sage)",
              background: "#E8ECE2",
              borderRadius: 999,
              padding: "3px 10px",
            }}
          >
            Tighter than {data.percentile}% of history
          </span>
        )}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 8,
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: "var(--text3)" }}>RANGE</div>
          <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>
            {data.range_min?.toFixed(1)}–{data.range_max?.toFixed(1)}h
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--text3)" }}>SD</div>
          <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text)" }}>
            {data.std_dev?.toFixed(1)}h
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--text3)" }}>HIST SD</div>
          <div style={{ fontSize: 15, fontWeight: 500, color: "var(--text3)" }}>
            {data.historical_std?.toFixed(1)}h
          </div>
        </div>
      </div>
      <div
        style={{ fontSize: 13, color: "var(--text2)", lineHeight: 1.45 }}
      >
        {isHigh
          ? "Your floor came up and ceiling came down — stronger routine."
          : "Spread is about average for your history."}
      </div>
    </div>
  );
}

function AttributionCard({ data }: { data: any }) {
  if (!data?.items?.length) return null;

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <SectionLabel>What changed this fortnight</SectionLabel>
      {data.items.map((item: any, i: number) => (
        <div
          key={i}
          style={{
            fontSize: 13.5,
            color: "var(--text2)",
            lineHeight: 1.5,
            paddingTop: i > 0 ? 10 : 4,
            borderTop: i > 0 ? "1px solid var(--border)" : "none",
          }}
        >
          <span style={{ color: "var(--text)", fontWeight: 500 }}>
            {item.metric}
          </span>{" "}
          changed by{" "}
          <span
            style={{ color: item.delta > 0 ? "var(--sage)" : "var(--terra)" }}
          >
            {item.delta > 0 ? "+" : ""}
            {item.delta?.toFixed(1)} {item.unit}
          </span>
          .{item.note && ` ${item.note}`}
        </div>
      ))}
    </div>
  );
}

function BacBudgetCard({ data }: { data: any }) {
  if (!data) return null;
  const used = data.drinks_this_week ?? 0;
  const budget = data.weekly_budget ?? 14;
  const pct = Math.min(1, used / budget);
  const barColor =
    pct >= 0.9 ? "var(--terra)" : pct >= 0.7 ? "var(--amber)" : "var(--sage)";

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 10,
        }}
      >
        <SectionLabel>Drink budget</SectionLabel>
        <span style={{ fontSize: 12, color: "var(--text2)" }}>
          {budget - used > 0 ? `${(budget - used).toFixed(1)} remaining` : "Budget hit"}
        </span>
      </div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 500,
          color: barColor,
          lineHeight: 1,
          marginBottom: 10,
        }}
      >
        {used.toFixed(1)}
        <span style={{ fontSize: 13, color: "var(--text3)", marginLeft: 4 }}>
          / {budget} units this week
        </span>
      </div>
      <div
        style={{
          height: 4,
          borderRadius: 4,
          background: "var(--border)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct * 100}%`,
            height: "100%",
            background: barColor,
            borderRadius: 4,
          }}
        />
      </div>
      {data.current_bac !== undefined && data.current_bac > 0 && (
        <div
          style={{
            marginTop: 10,
            fontSize: 13,
            color: "var(--text2)",
            lineHeight: 1.45,
          }}
        >
          Current BAC ~{(data.current_bac * 100).toFixed(2)}% · clears at{" "}
          {data.clears_at || "—"}
        </div>
      )}
    </div>
  );
}

function SuggestionsCard({ data }: { data: any }) {
  if (!data?.suggestions?.length) return null;

  return (
    <div style={{ marginBottom: 12 }}>
      <SectionLabel>Smart suggestions</SectionLabel>
      <div className="card" style={{ padding: "2px 16px" }}>
        {data.suggestions.map((s: string, i: number, arr: string[]) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: "13px 0",
              borderBottom:
                i < arr.length - 1 ? "1px solid var(--border)" : "none",
            }}
          >
            <span style={{ fontSize: 13.5, color: "var(--text)", lineHeight: 1.4 }}>
              {s}
            </span>
            <svg
              width="7"
              height="12"
              viewBox="0 0 8 14"
              fill="none"
              style={{ flexShrink: 0 }}
            >
              <path
                d="M1 1l6 6-6 6"
                stroke="var(--text3)"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TrendsTab() {
  const [regime, setRegime] = useState<any>(null);
  const [yoy, setYoy] = useState<any>(null);
  const [consistency, setConsistency] = useState<any>(null);
  const [attribution, setAttribution] = useState<any>(null);
  const [suggestions, setSuggestions] = useState<any>(null);
  const [bacBudget, setBacBudget] = useState<any>(null);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loadingSet, setLoadingSet] = useState(new Set(["regime", "yoy", "consistency", "attribution", "suggestions", "bac"]));

  function doneLoading(key: string) {
    setLoadingSet((s) => {
      const next = new Set(s);
      next.delete(key);
      return next;
    });
  }

  useEffect(() => {
    getRegimeShift()
      .then(setRegime)
      .catch((e) => setErrors((prev) => ({ ...prev, regime: e.message })))
      .finally(() => doneLoading("regime"));

    getYearOverYear()
      .then(setYoy)
      .catch((e) => setErrors((prev) => ({ ...prev, yoy: e.message })))
      .finally(() => doneLoading("yoy"));

    getConsistency()
      .then(setConsistency)
      .catch((e) => setErrors((prev) => ({ ...prev, consistency: e.message })))
      .finally(() => doneLoading("consistency"));

    getAttribution()
      .then(setAttribution)
      .catch((e) => setErrors((prev) => ({ ...prev, attribution: e.message })))
      .finally(() => doneLoading("attribution"));

    getSmartSuggestions()
      .then(setSuggestions)
      .catch((e) => setErrors((prev) => ({ ...prev, suggestions: e.message })))
      .finally(() => doneLoading("suggestions"));

    getBacBudget()
      .then(setBacBudget)
      .catch((e) => setErrors((prev) => ({ ...prev, bac: e.message })))
      .finally(() => doneLoading("bac"));
  }, []);

  return (
    <div style={{ padding: "0 20px" }}>
      {/* Header row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <div style={{ fontSize: 20, fontWeight: 500, color: "var(--text)" }}>
          History
        </div>
        <span
          style={{
            fontSize: 12,
            color: "var(--text2)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "5px 12px",
          }}
        >
          Last 4 weeks ∨
        </span>
      </div>

      {/* BAC budget */}
      {loadingSet.has("bac") ? (
        <LoadingSkeleton />
      ) : errors.bac ? (
        <ErrorCard label="Drink budget" error={errors.bac} />
      ) : (
        <BacBudgetCard data={bacBudget} />
      )}

      {/* Regime shift */}
      {loadingSet.has("regime") ? (
        <LoadingSkeleton />
      ) : errors.regime ? (
        <ErrorCard label="Regime shift" error={errors.regime} />
      ) : (
        <RegimeShiftCard data={regime} />
      )}

      {/* Year-over-year */}
      {loadingSet.has("yoy") ? (
        <LoadingSkeleton />
      ) : errors.yoy ? (
        <ErrorCard label="Year over year" error={errors.yoy} />
      ) : (
        <YoYCard data={yoy} />
      )}

      {/* Consistency */}
      {loadingSet.has("consistency") ? (
        <LoadingSkeleton />
      ) : errors.consistency ? (
        <ErrorCard label="Consistency" error={errors.consistency} />
      ) : (
        <ConsistencyCard data={consistency} />
      )}

      {/* Attribution */}
      {loadingSet.has("attribution") ? (
        <LoadingSkeleton />
      ) : errors.attribution ? (
        <ErrorCard label="Attribution" error={errors.attribution} />
      ) : (
        <AttributionCard data={attribution} />
      )}

      {/* Smart suggestions */}
      {loadingSet.has("suggestions") ? (
        <LoadingSkeleton />
      ) : errors.suggestions ? (
        <ErrorCard label="Suggestions" error={errors.suggestions} />
      ) : (
        <SuggestionsCard data={suggestions} />
      )}
    </div>
  );
}
