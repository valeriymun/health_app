"""
Garmin Connect client — activities only.

Session is cached in ~/.garth_health_sync so re-auth is infrequent.
"""

import os

from garminconnect import Garmin

GARMIN_HOME = os.path.expanduser("~/.garth_health_sync")


def _client():
    c = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
    try:
        c.login(GARMIN_HOME)
    except Exception:
        c.login()
        c.garth.dump(GARMIN_HOME)
    return c


def fetch_activities(d: str):
    """
    Fetch and normalize Garmin activities for date d (YYYY-MM-DD).
    Returns (activities_list, error_str_or_None).
    """
    try:
        c   = _client()
        raw = c.get_activities_by_date(d, d) or []
    except Exception as e:
        return [], str(e)

    activities = []
    for a in raw:
        dist_m = a.get("distance")       or 0
        dur_s  = a.get("duration")       or 0
        mov_s  = a.get("movingDuration") or 0
        elev   = a.get("elevationGain")
        cal    = a.get("calories")

        dist_km  = round(dist_m / 1000, 3) if dist_m   else None
        dur_min  = round(dur_s  / 60,   1) if dur_s    else None
        mov_min  = round(mov_s  / 60,   1) if mov_s    else None

        # Pace (min/km) — only meaningful for foot-based activities
        pace_mpk = None
        if dist_km and dist_km > 0 and dur_s:
            pace_mpk = round((dur_s / 60) / dist_km, 2)

        # Speed (km/h)
        spd_kph = None
        if dist_m and dur_s and dur_s > 0:
            spd_kph = round((dist_m / dur_s) * 3.6, 2)

        start_local = a.get("startTimeLocal") or a.get("startTimeGMT") or ""
        tz          = a.get("timeZoneId") or ""
        date_str    = start_local[:10] if len(start_local) >= 10 else d

        activities.append({
            "activity_id":         str(a.get("activityId", "")),
            "date":                date_str,
            "start_time":          start_local,
            "timezone":            str(tz),
            "activity_name":       a.get("activityName", ""),
            "activity_type":       a.get("activityType", {}).get("typeKey", ""),
            "duration_min":        dur_min,
            "moving_duration_min": mov_min or dur_min,
            "distance_km":         dist_km,
            "avg_pace_min_per_km": pace_mpk,
            "avg_speed_kph":       spd_kph,
            "avg_hr_bpm":          a.get("averageHR"),
            "max_hr_bpm":          a.get("maxHR"),
            "calories":            int(cal) if cal else None,
            "elevation_gain_m":    round(elev, 1) if elev else None,
            "source":              "garmin",
        })

    return activities, None
