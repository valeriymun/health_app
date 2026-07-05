const API_BASE = "/api";

async function fetchInsight<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function getRegimeShift(metric = "hrv", windowDays = 14, baselineDays = 60) {
  return fetchInsight<{
    shift_detected: boolean;
    metric: string;
    metric_label: string;
    unit: string;
    cohens_d: number;
    recent_median: number;
    baseline_median: number;
  }>(`/insights/regime-shift?metric=${metric}&window_days=${windowDays}&baseline_days=${baselineDays}`);
}

export async function getYearOverYear(days = 28) {
  return fetchInsight<{
    rows: Array<{
      label: string;
      metric: string;
      now: string;
      last_year: string;
      direction: "better" | "same" | "worse";
    }>;
  }>(`/insights/year-over-year?days=${days}`);
}

export async function getConsistency(days = 28) {
  return fetchInsight<{
    percentile: number;
    std_dev: number;
    historical_std: number;
    range_min: number;
    range_max: number;
  }>(`/insights/consistency?days=${days}`);
}

export async function getAttribution(days = 14) {
  return fetchInsight<{
    items: Array<{
      metric: string;
      delta: number;
      unit: string;
      note: string;
    }>;
  }>(`/insights/attribution?days=${days}`);
}

export async function getSmartSuggestions() {
  return fetchInsight<{
    suggestions: string[];
  }>("/insights/smart-suggestions");
}

export async function getBacBudget() {
  return fetchInsight<{
    drinks_this_week: number;
    weekly_budget: number;
    current_bac: number;
    clears_at: string | null;
  }>("/insights/bac-budget");
}

export async function postBacReading(units: number, timestamp?: string) {
  const res = await fetch(`${API_BASE}/insights/bac-reading`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ units, timestamp: timestamp ?? new Date().toISOString() }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
