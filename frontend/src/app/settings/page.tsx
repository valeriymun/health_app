"use client";

import { useState } from "react";
import {
  ArrowLeft,
  Upload,
  RefreshCw,
  CheckCircle,
  XCircle,
  Smartphone,
} from "lucide-react";
import { syncSource, uploadAppleHealthExport } from "@/lib/api";

export default function SettingsPage() {
  const [syncing, setSyncing] = useState<string | null>(null);
  const [result, setResult] = useState<{ source: string; ok: boolean; msg: string } | null>(null);
  const [uploading, setUploading] = useState(false);

  const handleSync = async (source: "oura" | "garmin", fullHistory: boolean) => {
    setSyncing(source);
    setResult(null);
    try {
      await syncSource(source, fullHistory);
      setResult({ source, ok: true, msg: `${source} sync complete!` });
    } catch (e: any) {
      setResult({ source, ok: false, msg: e.message });
    } finally {
      setSyncing(null);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const res = await uploadAppleHealthExport(file);
      setResult({
        source: "apple",
        ok: true,
        msg: `Imported: ${res.imported?.metrics || 0} metrics, ${res.imported?.workouts || 0} workouts`,
      });
    } catch (e: any) {
      setResult({ source: "apple", ok: false, msg: e.message });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <a href="/" className="btn btn-outline p-2">
          <ArrowLeft size={16} />
        </a>
        <h1 className="text-2xl font-bold">Data Sources</h1>
      </div>

      {result && (
        <div
          className="card mb-6 flex items-center gap-2"
          style={{
            borderColor: result.ok ? "var(--green)" : "var(--red)",
          }}
        >
          {result.ok ? (
            <CheckCircle size={18} color="var(--green)" />
          ) : (
            <XCircle size={18} color="var(--red)" />
          )}
          <span className="text-sm">{result.msg}</span>
        </div>
      )}

      {/* Apple Health */}
      <div className="card mb-4">
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: "var(--bg)" }}
          >
            <Smartphone size={20} color="var(--red)" />
          </div>
          <div>
            <h2 className="font-medium">Apple Health</h2>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Upload XML export or configure Shortcuts auto-sync
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <label className="btn btn-outline inline-flex items-center gap-2 cursor-pointer">
              <Upload size={16} />
              {uploading ? "Uploading..." : "Upload Export (ZIP/XML)"}
              <input
                type="file"
                accept=".zip,.xml"
                className="hidden"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </div>

          <div
            className="p-3 rounded-lg text-sm"
            style={{ background: "var(--bg)" }}
          >
            <p className="font-medium mb-2">Shortcuts Auto-Sync Setup:</p>
            <ol
              className="list-decimal list-inside space-y-1"
              style={{ color: "var(--text-muted)" }}
            >
              <li>Open the Shortcuts app on your iPhone</li>
              <li>Create a new shortcut with &quot;Find Health Samples&quot; action</li>
              <li>Add &quot;Get Contents of URL&quot; action pointing to your server</li>
              <li>
                POST to{" "}
                <code style={{ color: "var(--accent-light)" }}>
                  http://YOUR_SERVER:8000/api/ingest/apple-health/shortcuts
                </code>
              </li>
              <li>Set header X-API-Key to your configured key</li>
              <li>Set up automation to run daily</li>
            </ol>
          </div>
        </div>
      </div>

      {/* Oura Ring */}
      <div className="card mb-4">
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: "var(--bg)" }}
          >
            <span style={{ color: "var(--cyan)", fontSize: "1.25rem" }}>O</span>
          </div>
          <div>
            <h2 className="font-medium">Oura Ring</h2>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Sync via Oura API (configure token in .env)
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            className="btn btn-primary flex items-center gap-1.5"
            onClick={() => handleSync("oura", false)}
            disabled={syncing === "oura"}
          >
            <RefreshCw size={14} className={syncing === "oura" ? "animate-spin" : ""} />
            Sync Last 30 Days
          </button>
          <button
            className="btn btn-outline"
            onClick={() => handleSync("oura", true)}
            disabled={syncing === "oura"}
          >
            Full History
          </button>
        </div>
      </div>

      {/* Garmin */}
      <div className="card mb-4">
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: "var(--bg)" }}
          >
            <span style={{ color: "var(--green)", fontSize: "1.25rem" }}>G</span>
          </div>
          <div>
            <h2 className="font-medium">Garmin Connect</h2>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Sync via Garmin Connect (configure credentials in .env)
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            className="btn btn-primary flex items-center gap-1.5"
            onClick={() => handleSync("garmin", false)}
            disabled={syncing === "garmin"}
          >
            <RefreshCw size={14} className={syncing === "garmin" ? "animate-spin" : ""} />
            Sync Last 30 Days
          </button>
          <button
            className="btn btn-outline"
            onClick={() => handleSync("garmin", true)}
            disabled={syncing === "garmin"}
          >
            Full History
          </button>
        </div>
      </div>

      {/* Report Download */}
      <div className="card">
        <h2 className="font-medium mb-2">Health Reports</h2>
        <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>
          Download a comprehensive health report in Markdown format, then upload
          it to Claude for personalized AI health insights.
        </p>
        <div className="flex gap-2 flex-wrap">
          {[7, 30, 90, 365].map((d) => (
            <a
              key={d}
              href={`/api/reports/health-summary?days=${d}&format=markdown`}
              className="btn btn-outline"
              download
            >
              Last {d} days
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
