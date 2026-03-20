"""
Sync orchestration — fetches data from Oura + Garmin, normalizes it,
and writes to Google Sheets.

Partial-failure strategy:
  - Each Oura section is independent; one failure does not abort the others.
  - Garmin failure does not abort Oura sync.
  - The Daily row is always written (with None for unavailable fields).
  - All errors are collected and surfaced in the result dict.
"""

from datetime import datetime, timezone

import oura_client
import garmin_client
from sheets import SheetsManager, SCHEMAS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _h(seconds):
    """Seconds → hours, 3dp. Returns None if falsy."""
    return round(seconds / 3600, 3) if seconds else None


def _m(seconds):
    """Seconds → minutes, 1dp. Returns None if falsy."""
    return round(seconds / 60, 1) if seconds else None


def _best_sleep_session(sessions):
    """
    Return the primary sleep session for the night.
    Prefers 'long_sleep' type; falls back to session with max total duration.
    """
    if not sessions:
        return None
    long = [s for s in sessions if s.get("type") == "long_sleep"]
    pool = long if long else sessions
    return max(pool, key=lambda s: s.get("total_sleep_duration") or 0)


# ── Row builders ──────────────────────────────────────────────────────────────

def build_daily_row(d, oura_data, activities, now_utc):
    sessions,   _  = oura_data.get("sleep",            ([], None))
    ds_list,    _  = oura_data.get("daily_sleep",       ([], None))
    rd_list,    _  = oura_data.get("daily_readiness",   ([], None))
    act_list,   _  = oura_data.get("daily_activity",    ([], None))
    stress_list, _ = oura_data.get("daily_stress",      ([], None))
    res_list,   _  = oura_data.get("daily_resilience",  ([], None))
    spo2_list,  _  = oura_data.get("daily_spo2",        ([], None))

    ss    = _best_sleep_session(sessions) or {}
    ds    = ds_list[0]    if ds_list    else {}
    rd    = rd_list[0]    if rd_list    else {}
    act   = act_list[0]  if act_list   else {}
    stress = stress_list[0] if stress_list else {}
    res   = res_list[0]  if res_list   else {}
    spo2  = spo2_list[0] if spo2_list  else {}

    spo2_avg = (spo2.get("spo2_percentage") or {}).get("average") if spo2 else None

    # Garmin activity rollup
    g_count = len(activities)
    g_dist  = round(sum(a.get("distance_km") or 0 for a in activities), 2) or None
    g_dur   = round(sum(a.get("duration_min") or 0 for a in activities), 1) or None
    g_cal   = sum(a.get("calories") or 0 for a in activities) or None

    return [
        d,
        # Oura scores
        ds.get("score"),
        rd.get("score"),
        act.get("score"),
        # Sleep session detail
        _h(ss.get("total_sleep_duration")),
        _h(ss.get("deep_sleep_duration")),
        _h(ss.get("rem_sleep_duration")),
        _h(ss.get("light_sleep_duration")),
        _h(ss.get("awake_time")),
        _h(ss.get("time_in_bed")),
        ss.get("efficiency"),
        _m(ss.get("latency")),
        ss.get("average_hrv"),
        ss.get("lowest_heart_rate"),
        ss.get("average_heart_rate"),
        ss.get("temperature_delta") or ss.get("temperature_deviation"),
        spo2_avg,
        ss.get("average_breath"),
        # Activity
        act.get("steps"),
        act.get("active_calories"),
        act.get("total_calories"),
        _m(act.get("sedentary_time")),
        _m(act.get("medium_activity_time")),
        _m(act.get("high_activity_time")),
        # Stress
        _m(stress.get("stress_high")),
        _m(stress.get("recovery_high")),
        # Resilience
        res.get("level"),
        # Garmin rollup
        g_count or None,
        g_dist,
        g_dur,
        g_cal,
        now_utc,
    ]


def build_sleep_rows(sessions, ds_list, spo2_list, now_utc):
    score_by_day = {ds.get("day"): ds.get("score") for ds in (ds_list or [])}
    spo2 = spo2_list[0] if spo2_list else {}
    spo2_avg = (spo2.get("spo2_percentage") or {}).get("average") if spo2 else None

    rows = []
    for s in (sessions or []):
        rows.append([
            s.get("day"),
            s.get("id"),
            s.get("bedtime_start"),
            s.get("bedtime_end"),
            _h(s.get("total_sleep_duration")),
            _h(s.get("deep_sleep_duration")),
            _h(s.get("rem_sleep_duration")),
            _h(s.get("light_sleep_duration")),
            _h(s.get("awake_time")),
            _h(s.get("time_in_bed")),
            s.get("efficiency"),
            _m(s.get("latency")),
            s.get("average_hrv"),
            s.get("lowest_heart_rate"),
            s.get("average_heart_rate"),
            s.get("temperature_delta") or s.get("temperature_deviation"),
            s.get("average_breath"),
            spo2_avg,
            score_by_day.get(s.get("day")),
            s.get("type"),
            now_utc,
        ])
    return rows


def build_readiness_rows(rd_list, now_utc):
    rows = []
    for rd in (rd_list or []):
        c = rd.get("contributors") or {}
        rows.append([
            rd.get("day"),
            rd.get("score"),
            c.get("activity_balance"),
            c.get("body_temperature"),
            c.get("hrv_balance"),
            c.get("previous_day_activity"),
            c.get("previous_night"),
            c.get("recovery_index"),
            c.get("resting_heart_rate"),
            c.get("sleep_balance"),
            now_utc,
        ])
    return rows


def build_activity_rows(act_list, now_utc):
    rows = []
    for act in (act_list or []):
        rows.append([
            act.get("day"),
            act.get("score"),
            act.get("steps"),
            act.get("active_calories"),
            act.get("total_calories"),
            _m(act.get("low_activity_time")),
            _m(act.get("medium_activity_time")),
            _m(act.get("high_activity_time")),
            _m(act.get("sedentary_time")),
            act.get("equivalent_walking_distance"),
            now_utc,
        ])
    return rows


def build_stress_rows(stress_list, now_utc):
    rows = []
    for st in (stress_list or []):
        rows.append([
            st.get("day"),
            st.get("day_summary"),
            _m(st.get("stress_high")),
            _m(st.get("recovery_high")),
            now_utc,
        ])
    return rows


def build_resilience_rows(res_list, now_utc):
    rows = []
    for res in (res_list or []):
        c = res.get("contributors") or {}
        rows.append([
            res.get("day"),
            res.get("level"),
            c.get("daytime_recovery"),
            c.get("sleep_recovery"),
            c.get("hrv_recovery"),
            now_utc,
        ])
    return rows


def build_activity_rows_garmin(activities, now_utc):
    rows = []
    for a in activities:
        rows.append([
            a["activity_id"],
            a["date"],
            a["start_time"],
            a["timezone"],
            a["activity_name"],
            a["activity_type"],
            a["duration_min"],
            a["moving_duration_min"],
            a["distance_km"],
            a["avg_pace_min_per_km"],
            a["avg_speed_kph"],
            a["avg_hr_bpm"],
            a["max_hr_bpm"],
            a["calories"],
            a["elevation_gain_m"],
            a["source"],
            now_utc,
        ])
    return rows


# ── Main sync ─────────────────────────────────────────────────────────────────

def run(d: str, sheet_id: str) -> dict:
    """
    Run the full sync for date d (yesterday's YYYY-MM-DD).
    Returns a result dict describing what was written and any errors.
    """
    started_at = datetime.now(timezone.utc)
    now_utc    = started_at.isoformat()

    result = {
        "date":     d,
        "sections": {},
        "warnings": [],
        "errors":   [],
    }

    sh = SheetsManager(sheet_id)
    sh.init_all()  # ensure all tabs exist before any writes

    # ── Fetch Oura ────────────────────────────────────────────────────────────
    oura_data = oura_client.fetch_all(d)

    # Surface scope warnings
    for section, (_, err) in oura_data.items():
        if err and "SCOPE_MISSING" in err:
            result["warnings"].append(
                f"SpO2 / {section} data unavailable — "
                "click 'Re-authorize Oura' to grant the spo2 scope."
            )

    # ── Fetch Garmin ──────────────────────────────────────────────────────────
    garmin_acts, garmin_err = garmin_client.fetch_activities(d)
    if garmin_err:
        result["errors"].append(f"Garmin: {garmin_err}")

    # ── Write Daily (always attempted) ───────────────────────────────────────
    try:
        daily_row = build_daily_row(d, oura_data, garmin_acts, now_utc)
        updated   = sh.upsert("Daily", daily_row)
        result["sections"]["Daily"] = {
            "rows": 1,
            "action": "updated" if updated else "inserted",
            "error": None,
        }
    except Exception as e:
        result["sections"]["Daily"] = {"rows": 0, "action": None, "error": str(e)}
        result["errors"].append(f"Daily write: {e}")

    # ── Write Oura_Sleep ──────────────────────────────────────────────────────
    try:
        sessions,  serr = oura_data.get("sleep",       ([], None))
        ds_list,   _    = oura_data.get("daily_sleep", ([], None))
        spo2_list, _    = oura_data.get("daily_spo2",  ([], None))
        if serr:
            raise RuntimeError(serr)
        rows    = build_sleep_rows(sessions, ds_list, spo2_list, now_utc)
        counts  = sh.upsert_many("Oura_Sleep", rows)
        result["sections"]["Oura_Sleep"] = {
            "rows": len(rows), **counts, "error": None
        }
    except Exception as e:
        result["sections"]["Oura_Sleep"] = {"rows": 0, "error": str(e)}
        result["errors"].append(f"Oura_Sleep: {e}")

    # ── Write Oura_Readiness ──────────────────────────────────────────────────
    try:
        rd_list, rderr = oura_data.get("daily_readiness", ([], None))
        if rderr:
            raise RuntimeError(rderr)
        rows   = build_readiness_rows(rd_list, now_utc)
        counts = sh.upsert_many("Oura_Readiness", rows)
        result["sections"]["Oura_Readiness"] = {
            "rows": len(rows), **counts, "error": None
        }
    except Exception as e:
        result["sections"]["Oura_Readiness"] = {"rows": 0, "error": str(e)}
        result["errors"].append(f"Oura_Readiness: {e}")

    # ── Write Oura_Activity ───────────────────────────────────────────────────
    try:
        act_list, aerr = oura_data.get("daily_activity", ([], None))
        if aerr:
            raise RuntimeError(aerr)
        rows   = build_activity_rows(act_list, now_utc)
        counts = sh.upsert_many("Oura_Activity", rows)
        result["sections"]["Oura_Activity"] = {
            "rows": len(rows), **counts, "error": None
        }
    except Exception as e:
        result["sections"]["Oura_Activity"] = {"rows": 0, "error": str(e)}
        result["errors"].append(f"Oura_Activity: {e}")

    # ── Write Oura_Stress ─────────────────────────────────────────────────────
    try:
        st_list, sterr = oura_data.get("daily_stress", ([], None))
        if sterr:
            raise RuntimeError(sterr)
        rows   = build_stress_rows(st_list, now_utc)
        counts = sh.upsert_many("Oura_Stress", rows)
        result["sections"]["Oura_Stress"] = {
            "rows": len(rows), **counts, "error": None
        }
    except Exception as e:
        result["sections"]["Oura_Stress"] = {"rows": 0, "error": str(e)}
        result["errors"].append(f"Oura_Stress: {e}")

    # ── Write Oura_Resilience ─────────────────────────────────────────────────
    try:
        res_list, reserr = oura_data.get("daily_resilience", ([], None))
        if reserr:
            raise RuntimeError(reserr)
        rows   = build_resilience_rows(res_list, now_utc)
        counts = sh.upsert_many("Oura_Resilience", rows)
        result["sections"]["Oura_Resilience"] = {
            "rows": len(rows), **counts, "error": None
        }
    except Exception as e:
        result["sections"]["Oura_Resilience"] = {"rows": 0, "error": str(e)}
        result["errors"].append(f"Oura_Resilience: {e}")

    # ── Write Garmin_Activities ───────────────────────────────────────────────
    try:
        if garmin_err:
            raise RuntimeError(garmin_err)
        rows   = build_activity_rows_garmin(garmin_acts, now_utc)
        counts = sh.upsert_many("Garmin_Activities", rows)
        result["sections"]["Garmin_Activities"] = {
            "rows": len(rows), **counts, "error": None,
            "summary": {
                "count":    len(garmin_acts),
                "dist_km":  round(sum(a.get("distance_km") or 0 for a in garmin_acts), 2),
                "dur_min":  round(sum(a.get("duration_min") or 0 for a in garmin_acts), 1),
            },
        }
    except Exception as e:
        result["sections"]["Garmin_Activities"] = {"rows": 0, "error": str(e)}
        result["errors"].append(f"Garmin_Activities: {e}")

    # ── Write Sync_Log ────────────────────────────────────────────────────────
    finished_at = datetime.now(timezone.utc).isoformat()
    status      = "ok" if not result["errors"] else "partial" if result["sections"] else "error"

    def _rows(tab):
        return result["sections"].get(tab, {}).get("rows", 0)

    try:
        sh.upsert("Sync_Log", [
            now_utc, finished_at, status,
            _rows("Daily"), _rows("Oura_Sleep"), _rows("Oura_Readiness"),
            _rows("Oura_Activity"), _rows("Oura_Stress"), _rows("Oura_Resilience"),
            _rows("Garmin_Activities"),
            "; ".join(result["errors"]) or "",
        ])
    except Exception:
        pass  # log failure is non-fatal

    result["status"]      = status
    result["started_at"]  = now_utc
    result["finished_at"] = finished_at
    return result
