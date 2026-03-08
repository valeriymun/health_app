"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface SleepData {
  date: string;
  deep_minutes?: number | null;
  rem_minutes?: number | null;
  light_minutes?: number | null;
  awake_minutes?: number | null;
  total_minutes?: number | null;
}

export default function SleepChart({ data }: { data: SleepData[] }) {
  const chartData = data
    .map((d) => ({
      date: d.date.slice(5), // MM-DD
      Deep: d.deep_minutes ? +(d.deep_minutes / 60).toFixed(1) : 0,
      REM: d.rem_minutes ? +(d.rem_minutes / 60).toFixed(1) : 0,
      Light: d.light_minutes ? +(d.light_minutes / 60).toFixed(1) : 0,
      Awake: d.awake_minutes ? +(d.awake_minutes / 60).toFixed(1) : 0,
    }))
    .reverse();

  return (
    <div className="card">
      <h3
        className="text-sm font-medium mb-4"
        style={{ color: "var(--text-muted)" }}
      >
        SLEEP BREAKDOWN (hours)
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={12} />
          <YAxis stroke="var(--text-muted)" fontSize={12} />
          <Tooltip
            contentStyle={{
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              color: "var(--text)",
            }}
          />
          <Legend />
          <Bar dataKey="Deep" stackId="sleep" fill="var(--blue)" radius={[0, 0, 0, 0]} />
          <Bar dataKey="REM" stackId="sleep" fill="var(--purple)" />
          <Bar dataKey="Light" stackId="sleep" fill="var(--cyan)" />
          <Bar dataKey="Awake" stackId="sleep" fill="var(--red)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
