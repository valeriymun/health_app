"use client";

import TrendsTab from "./TrendsTab";
import IntakeTab from "./IntakeTab";
import AskClaudeTab from "./AskClaudeTab";

type SubTab = "trends" | "intake" | "ask";

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "trends", label: "Trends" },
  { key: "intake", label: "Intake" },
  { key: "ask", label: "Ask Claude" },
];

export default function HistoryTab({
  subTab,
  onSubTabChange,
  askQuery,
  onAskQueryChange,
}: {
  subTab: SubTab;
  onSubTabChange: (t: SubTab) => void;
  askQuery: string;
  onAskQueryChange: (q: string) => void;
}) {
  return (
    <div style={{ paddingTop: 20 }}>
      {/* Sub-tab pills */}
      <div
        style={{
          display: "flex",
          gap: 8,
          padding: "0 20px 16px",
          overflowX: "auto",
        }}
      >
        {SUB_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => onSubTabChange(key)}
            style={{
              padding: "6px 16px",
              borderRadius: 999,
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 0.15s",
              whiteSpace: "nowrap",
              fontFamily: "'DM Sans', sans-serif",
              background: subTab === key ? "var(--sage)" : "var(--bg-card)",
              color: subTab === key ? "#FAF7F2" : "var(--text2)",
              border: subTab === key
                ? "1px solid var(--sage)"
                : "1px solid var(--border)",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {subTab === "trends" && <TrendsTab />}
      {subTab === "intake" && <IntakeTab />}
      {subTab === "ask" && (
        <AskClaudeTab query={askQuery} onQueryChange={onAskQueryChange} />
      )}
    </div>
  );
}
