const API_BASE = "/api";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getOverview() {
  return fetchApi<{
    daily: Array<Record<string, any>>;
    sleep: Array<Record<string, any>>;
    workouts: Array<Record<string, any>>;
    stats: {
      total_metrics: number;
      total_sleep_sessions: number;
      total_workouts: number;
      total_days_tracked: number;
    };
  }>("/dashboard/overview");
}

export async function getMetricTrend(
  metricType: string,
  days = 30,
  aggregation = "daily_avg"
) {
  return fetchApi<{
    metric: string;
    data: Array<{ date: string; value: number; sample_count?: number }>;
  }>(`/dashboard/trends/${metricType}?days=${days}&aggregation=${aggregation}`);
}

export async function getSleepTrends(days = 30) {
  return fetchApi<{
    data: Array<Record<string, any>>;
  }>(`/dashboard/sleep/trends?days=${days}`);
}

export async function getWorkoutSummary(days = 30) {
  return fetchApi<{
    total_workouts: number;
    total_minutes: number;
    total_calories: number;
    by_type: Record<string, any>;
    recent: Array<Record<string, any>>;
  }>(`/dashboard/workouts/summary?days=${days}`);
}

export async function downloadReport(days = 30, format = "markdown") {
  const res = await fetch(
    `${API_BASE}/reports/health-summary?days=${days}&format=${format}`
  );
  if (format === "markdown") {
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `health_report_${new Date().toISOString().split("T")[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
  } else {
    return res.json();
  }
}

export async function syncSource(source: "oura" | "garmin", fullHistory = false) {
  return fetchApi(`/ingest/${source}/sync`, {
    method: "POST",
    body: JSON.stringify({ full_history: fullHistory }),
  });
}

export async function uploadAppleHealthExport(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/ingest/apple-health/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}
