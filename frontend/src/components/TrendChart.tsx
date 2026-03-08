"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface TrendData {
  date: string;
  value: number;
}

interface TrendChartProps {
  title: string;
  data: TrendData[];
  color?: string;
  unit?: string;
}

export default function TrendChart({
  title,
  data,
  color = "var(--accent)",
  unit = "",
}: TrendChartProps) {
  const chartData = data.map((d) => ({
    date: d.date.slice(5),
    value: d.value,
  }));

  return (
    <div className="card">
      <h3
        className="text-sm font-medium mb-4"
        style={{ color: "var(--text-muted)" }}
      >
        {title.toUpperCase()}
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id={`grad-${title}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
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
            formatter={(value: number) => [`${value} ${unit}`, title]}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill={`url(#grad-${title})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
