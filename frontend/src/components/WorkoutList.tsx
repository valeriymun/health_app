"use client";

import { Dumbbell } from "lucide-react";

interface WorkoutItem {
  type: string;
  start?: string;
  date?: string;
  duration_minutes?: number;
  calories?: number;
  distance_km?: number;
  avg_hr?: number;
  source?: string;
}

export default function WorkoutList({ workouts }: { workouts: WorkoutItem[] }) {
  return (
    <div className="card">
      <h3
        className="text-sm font-medium mb-4"
        style={{ color: "var(--text-muted)" }}
      >
        RECENT WORKOUTS
      </h3>
      <div className="flex flex-col gap-3">
        {workouts.length === 0 && (
          <p style={{ color: "var(--text-muted)" }}>No workouts yet</p>
        )}
        {workouts.slice(0, 10).map((w, i) => {
          const dateStr = w.start || w.date || "";
          const displayDate = dateStr ? new Date(dateStr).toLocaleDateString() : "";
          return (
            <div
              key={i}
              className="flex items-center gap-3 p-3 rounded-lg"
              style={{ background: "var(--bg)" }}
            >
              <div
                className="flex items-center justify-center w-10 h-10 rounded-lg"
                style={{ background: "var(--bg-card-hover)" }}
              >
                <Dumbbell size={18} color="var(--accent-light)" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm capitalize">
                    {w.type?.replace(/_/g, " ")}
                  </span>
                  {w.source && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{
                        background: "var(--bg-card-hover)",
                        color: "var(--text-muted)",
                      }}
                    >
                      {w.source}
                    </span>
                  )}
                </div>
                <div
                  className="text-xs flex gap-3 mt-0.5"
                  style={{ color: "var(--text-muted)" }}
                >
                  <span>{displayDate}</span>
                  {w.duration_minutes && (
                    <span>{Math.round(w.duration_minutes)} min</span>
                  )}
                  {w.calories && <span>{Math.round(w.calories)} cal</span>}
                  {w.distance_km && <span>{w.distance_km.toFixed(1)} km</span>}
                  {w.avg_hr && <span>{Math.round(w.avg_hr)} bpm</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
