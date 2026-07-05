"use client";

import { useState } from "react";

export default function AskClaudeTab({
  query,
  onQueryChange,
}: {
  query: string;
  onQueryChange: (q: string) => void;
}) {
  const [submitted, setSubmitted] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSubmitted(query.trim());
  }

  return (
    <div style={{ padding: "0 20px" }}>
      <form onSubmit={handleSubmit}>
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "flex-end",
            marginBottom: 16,
          }}
        >
          <textarea
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Ask about your health data…"
            rows={3}
            style={{
              flex: 1,
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: 10,
              padding: "12px 14px",
              fontSize: 14,
              color: "var(--text)",
              fontFamily: "'DM Sans', sans-serif",
              resize: "none",
              outline: "none",
            }}
          />
          <button
            type="submit"
            style={{
              background: "var(--sage)",
              border: "none",
              borderRadius: 10,
              width: 40,
              height: 40,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
            aria-label="Send"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#FAF7F2"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </form>

      {submitted && (
        <div
          className="card"
          style={{ borderLeft: "3px solid var(--sage)", marginBottom: 12 }}
        >
          <div className="stat-label" style={{ marginBottom: 8 }}>
            Query
          </div>
          <div style={{ fontSize: 14, color: "var(--text)", marginBottom: 12 }}>
            {submitted}
          </div>
          <div
            style={{
              fontSize: 13,
              color: "var(--text2)",
              padding: "10px 12px",
              background: "var(--bg)",
              borderRadius: 8,
              lineHeight: 1.55,
            }}
          >
            Claude AI integration coming soon. Connect the Claude API to get
            real responses grounded in your health data.
          </div>
        </div>
      )}

      {!submitted && (
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {[
            "What happened this week?",
            "How did my sleep trend this month?",
            "Compare this week to last week",
            "What's affecting my HRV?",
          ].map((s, i, arr) => (
            <button
              key={s}
              onClick={() => onQueryChange(s)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 0",
                borderBottom:
                  i < arr.length - 1 ? "1px solid var(--border)" : "none",
                background: "none",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <span style={{ fontSize: 13.5, color: "var(--text)" }}>{s}</span>
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
      )}
    </div>
  );
}
