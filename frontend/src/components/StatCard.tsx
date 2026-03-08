"use client";

import { type ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string | number | null | undefined;
  unit?: string;
  icon: ReactNode;
  trend?: "up" | "down" | "neutral";
  color?: string;
}

export default function StatCard({
  label,
  value,
  unit,
  icon,
  trend,
  color = "var(--accent-light)",
}: StatCardProps) {
  const trendColor =
    trend === "up"
      ? "var(--green)"
      : trend === "down"
        ? "var(--red)"
        : "var(--text-muted)";

  return (
    <div className="card flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="stat-label">{label}</span>
        <span style={{ color }}>{icon}</span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="stat-value" style={{ color }}>
          {value ?? "—"}
        </span>
        {unit && (
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}
