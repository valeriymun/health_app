"use client";

import { useState } from "react";
import HomeTab from "@/components/HomeTab";
import HistoryTab from "@/components/HistoryTab";

type MainTab = "home" | "history";
type HistorySubTab = "trends" | "intake" | "ask";

export default function Dashboard() {
  const [tab, setTab] = useState<MainTab>("home");
  const [historySub, setHistorySub] = useState<HistorySubTab>("trends");
  const [askClaudeQuery, setAskClaudeQuery] = useState<string>("");

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  const hour = now.getHours();
  const greeting =
    hour < 11 ? "Good morning" : hour < 19 ? "Good afternoon" : "Good evening";

  function openAsk(query: string) {
    setAskClaudeQuery(query);
    setHistorySub("ask");
    setTab("history");
  }

  return (
    <div
      style={{
        minHeight: "100dvh",
        maxWidth: 430,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        background: "var(--bg)",
        position: "relative",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "52px 20px 0",
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
        }}
      >
        <div>
          <div
            style={{
              fontSize: 13,
              color: "var(--text2)",
              marginBottom: 2,
              fontWeight: 500,
            }}
          >
            {dateStr}
          </div>
          <div style={{ fontSize: 22, fontWeight: 500, color: "var(--text)" }}>
            {greeting}
          </div>
        </div>
        <button
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            border: "1px solid var(--border)",
            background: "var(--bg-card)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            marginTop: 2,
          }}
          aria-label="Settings"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--text2)"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: "auto", paddingBottom: 80 }}>
        {tab === "home" && <HomeTab onAskClaude={openAsk} />}
        {tab === "history" && (
          <HistoryTab
            subTab={historySub}
            onSubTabChange={setHistorySub}
            askQuery={askClaudeQuery}
            onAskQueryChange={setAskClaudeQuery}
          />
        )}
      </div>

      {/* Bottom tab bar */}
      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: "50%",
          transform: "translateX(-50%)",
          width: "100%",
          maxWidth: 430,
          borderTop: "1px solid var(--border)",
          background: "var(--bg-card)",
          display: "flex",
          padding: "10px 0 26px",
          zIndex: 100,
        }}
      >
        {(
          [
            {
              key: "home" as MainTab,
              label: "Home",
              icon: (
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                  <polyline points="9 22 9 12 15 12 15 22" />
                </svg>
              ),
            },
            {
              key: "history" as MainTab,
              label: "History",
              icon: (
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              ),
            },
          ] as { key: MainTab; label: string; icon: React.ReactNode }[]
        ).map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 4,
              background: "none",
              border: "none",
              cursor: "pointer",
              color: tab === key ? "var(--sage)" : "var(--text3)",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 11,
              fontWeight: 500,
              transition: "color 0.15s",
            }}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
