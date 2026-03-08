"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Heart,
  Moon,
  Footprints,
  Activity,
  Flame,
  Wind,
  Download,
  RefreshCw,
  Settings,
  TrendingUp,
  Zap,
} from "lucide-react";
import StatCard from "@/components/StatCard";
import SleepChart from "@/components/SleepChart";
import TrendChart from "@/components/TrendChart";
import WorkoutList from "@/components/WorkoutList";
import {
  getOverview,
  getMetricTrend,
  getSleepTrends,
  downloadReport,
} from "@/lib/api";

type Tab = "overview" | "sleep" | "activity" | "trends";

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [overview, setOverview] = useState<any>(null);
  const [sleepTrends, setSleepTrends] = useState<any>(null);
  const [rhrTrend, setRhrTrend] = useState<any>(null);
  const [hrvTrend, setHrvTrend] = useState<any>(null);
  const [stepsTrend, setStepsTrend] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, sleep, rhr, hrv, steps] = await Promise.all([
        getOverview(),
        getSleepTrends(days),
        getMetricTrend("resting_heart_rate", days),
        getMetricTrend("hrv", days),
        getMetricTrend("steps", days),
      ]);
      setOverview(ov);
      setSleepTrends(sleep);
      setRhrTrend(rhr);
      setHrvTrend(hrv);
      setStepsTrend(steps);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const latestDaily = overview?.daily?.[0] || {};
  const latestSleep = overview?.sleep?.[0] || {};

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Activity size={28} color="var(--accent-light)" />
            Health Dashboard
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Apple Health + Oura Ring + Garmin
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="btn btn-outline"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>7 days</option>
            <option value={14}>14 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
            <option value={180}>6 months</option>
            <option value={365}>1 year</option>
          </select>
          <button className="btn btn-outline" onClick={fetchData} title="Refresh">
            <RefreshCw size={16} />
          </button>
          <button
            className="btn btn-primary flex items-center gap-1.5"
            onClick={() => downloadReport(days, "markdown")}
          >
            <Download size={16} />
            Report
          </button>
          <a href="/settings" className="btn btn-outline" title="Settings">
            <Settings size={16} />
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div
        className="flex gap-6 mb-6 border-b pb-2"
        style={{ borderColor: "var(--border)" }}
      >
        {(
          [
            ["overview", "Overview"],
            ["sleep", "Sleep"],
            ["activity", "Activity"],
            ["trends", "Trends"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`pb-2 text-sm font-medium transition-colors ${
              tab === key ? "tab-active" : ""
            }`}
            style={{ color: tab === key ? "var(--accent-light)" : "var(--text-muted)" }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <div
          className="card mb-6 text-sm"
          style={{ borderColor: "var(--red)", color: "var(--red)" }}
        >
          Failed to load data: {error}. Make sure the backend is running on port
          8000.
        </div>
      )}

      {loading && !overview && (
        <div className="flex items-center justify-center py-20">
          <RefreshCw
            size={24}
            className="animate-spin"
            color="var(--accent-light)"
          />
        </div>
      )}

      {/* Overview Tab */}
      {tab === "overview" && overview && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
            <StatCard
              label="Resting HR"
              value={latestDaily.resting_heart_rate}
              unit="bpm"
              icon={<Heart size={18} />}
              color="var(--red)"
            />
            <StatCard
              label="HRV"
              value={latestDaily.avg_hrv}
              unit="ms"
              icon={<TrendingUp size={18} />}
              color="var(--green)"
            />
            <StatCard
              label="Steps"
              value={
                latestDaily.steps
                  ? Number(latestDaily.steps).toLocaleString()
                  : null
              }
              icon={<Footprints size={18} />}
              color="var(--blue)"
            />
            <StatCard
              label="Sleep"
              value={
                latestSleep.total_minutes
                  ? `${(latestSleep.total_minutes / 60).toFixed(1)}`
                  : null
              }
              unit="hrs"
              icon={<Moon size={18} />}
              color="var(--purple)"
            />
            <StatCard
              label="Active Cal"
              value={
                latestDaily.calories_active
                  ? Math.round(latestDaily.calories_active)
                  : null
              }
              unit="kcal"
              icon={<Flame size={18} />}
              color="var(--yellow)"
            />
            <StatCard
              label="Readiness"
              value={latestDaily.readiness_score}
              icon={<Zap size={18} />}
              color="var(--cyan)"
            />
          </div>

          {/* Charts */}
          <div className="grid md:grid-cols-2 gap-4 mb-6">
            {sleepTrends?.data?.length > 0 && (
              <SleepChart data={sleepTrends.data} />
            )}
            <WorkoutList workouts={overview.workouts || []} />
          </div>

          <div className="grid md:grid-cols-3 gap-4 mb-6">
            {rhrTrend?.data?.length > 0 && (
              <TrendChart
                title="Resting Heart Rate"
                data={rhrTrend.data}
                color="var(--red)"
                unit="bpm"
              />
            )}
            {hrvTrend?.data?.length > 0 && (
              <TrendChart
                title="HRV"
                data={hrvTrend.data}
                color="var(--green)"
                unit="ms"
              />
            )}
            {stepsTrend?.data?.length > 0 && (
              <TrendChart
                title="Daily Steps"
                data={stepsTrend.data}
                color="var(--blue)"
                unit="steps"
              />
            )}
          </div>

          {/* Data stats */}
          <div className="card">
            <h3
              className="text-sm font-medium mb-3"
              style={{ color: "var(--text-muted)" }}
            >
              DATA SUMMARY
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span style={{ color: "var(--text-muted)" }}>Metrics: </span>
                <span className="font-medium">
                  {overview.stats.total_metrics.toLocaleString()}
                </span>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Sleep Sessions: </span>
                <span className="font-medium">
                  {overview.stats.total_sleep_sessions}
                </span>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Workouts: </span>
                <span className="font-medium">
                  {overview.stats.total_workouts}
                </span>
              </div>
              <div>
                <span style={{ color: "var(--text-muted)" }}>Days Tracked: </span>
                <span className="font-medium">
                  {overview.stats.total_days_tracked}
                </span>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Sleep Tab */}
      {tab === "sleep" && sleepTrends && (
        <div className="space-y-4">
          <SleepChart data={sleepTrends.data || []} />
          {hrvTrend?.data?.length > 0 && (
            <TrendChart
              title="Sleep HRV Trend"
              data={hrvTrend.data}
              color="var(--green)"
              unit="ms"
            />
          )}
        </div>
      )}

      {/* Activity Tab */}
      {tab === "activity" && overview && (
        <div className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            {stepsTrend?.data?.length > 0 && (
              <TrendChart
                title="Daily Steps"
                data={stepsTrend.data}
                color="var(--blue)"
                unit="steps"
              />
            )}
            <WorkoutList workouts={overview.workouts || []} />
          </div>
        </div>
      )}

      {/* Trends Tab */}
      {tab === "trends" && (
        <div className="grid md:grid-cols-2 gap-4">
          {rhrTrend?.data?.length > 0 && (
            <TrendChart
              title="Resting Heart Rate"
              data={rhrTrend.data}
              color="var(--red)"
              unit="bpm"
            />
          )}
          {hrvTrend?.data?.length > 0 && (
            <TrendChart
              title="HRV"
              data={hrvTrend.data}
              color="var(--green)"
              unit="ms"
            />
          )}
          {stepsTrend?.data?.length > 0 && (
            <TrendChart
              title="Daily Steps"
              data={stepsTrend.data}
              color="var(--blue)"
              unit="steps"
            />
          )}
        </div>
      )}
    </div>
  );
}
