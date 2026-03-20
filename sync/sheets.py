"""
Google Sheets management — schema, worksheet creation, formatting, upsert logic.

All worksheets are created automatically on first use with:
  - Row 1 headers (bold, light-blue background)
  - Frozen header row
  - Auto-resized columns
"""

import os

import gspread
from google.oauth2.service_account import Credentials

SERVICE_ACCOUNT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "service-account.json"
)

# ── Schema ────────────────────────────────────────────────────────────────────
# key_cols: 0-indexed column indices that form the upsert key.
# None means append-only (Sync_Log).

SCHEMAS = {
    "Daily": {
        "headers": [
            "date",
            "oura_sleep_score", "oura_readiness_score", "oura_activity_score",
            "oura_total_sleep_hours", "oura_deep_sleep_hours", "oura_rem_sleep_hours",
            "oura_light_sleep_hours", "oura_awake_hours", "oura_time_in_bed_hours",
            "oura_sleep_efficiency_pct", "oura_sleep_latency_min",
            "oura_avg_hrv_ms", "oura_lowest_resting_hr_bpm", "oura_avg_sleep_hr_bpm",
            "oura_temperature_deviation", "oura_spo2_avg", "oura_avg_breath_rate",
            "oura_steps", "oura_active_calories", "oura_total_calories",
            "oura_sedentary_time_min", "oura_medium_activity_time_min", "oura_high_activity_time_min",
            "oura_stress_high_time_min", "oura_restorative_time_min", "oura_resilience_level",
            "garmin_activity_count", "garmin_total_distance_km",
            "garmin_total_duration_min", "garmin_total_calories",
            "synced_at_utc",
        ],
        "key_cols": [0],  # keyed by date
    },
    "Oura_Sleep": {
        "headers": [
            "date", "sleep_session_id",
            "bedtime_start", "bedtime_end",
            "total_sleep_hours", "deep_sleep_hours", "rem_sleep_hours",
            "light_sleep_hours", "awake_hours", "time_in_bed_hours",
            "efficiency_pct", "latency_min",
            "average_hrv_ms", "lowest_hr_bpm", "average_hr_bpm",
            "temperature_deviation", "avg_breath_rate", "blood_oxygen_avg",
            "sleep_score", "sleep_type",
            "synced_at_utc",
        ],
        "key_cols": [0, 1],  # keyed by date + session_id
    },
    "Oura_Readiness": {
        "headers": [
            "date", "readiness_score",
            "activity_balance", "body_temperature", "hrv_balance",
            "previous_day_activity", "previous_night", "recovery_index",
            "resting_hr", "sleep_balance",
            "synced_at_utc",
        ],
        "key_cols": [0],
    },
    "Oura_Activity": {
        "headers": [
            "date", "activity_score",
            "steps", "active_calories", "total_calories",
            "low_activity_time_min", "medium_activity_time_min",
            "high_activity_time_min", "sedentary_time_min",
            "equivalent_walking_distance_m",
            "synced_at_utc",
        ],
        "key_cols": [0],
    },
    "Oura_Stress": {
        "headers": [
            "date", "day_summary",
            "stress_high_time_min", "recovery_high_time_min",
            "synced_at_utc",
        ],
        "key_cols": [0],
    },
    "Oura_Resilience": {
        "headers": [
            "date", "resilience_level",
            "daytime_recovery", "sleep_recovery", "hrv_recovery",
            "synced_at_utc",
        ],
        "key_cols": [0],
    },
    "Garmin_Activities": {
        "headers": [
            "garmin_activity_id", "date", "start_time", "timezone",
            "activity_name", "activity_type",
            "duration_min", "moving_duration_min", "distance_km",
            "avg_pace_min_per_km", "avg_speed_kph",
            "avg_hr_bpm", "max_hr_bpm", "calories", "elevation_gain_m",
            "source", "synced_at_utc",
        ],
        "key_cols": [0],  # keyed by garmin_activity_id
    },
    "Sync_Log": {
        "headers": [
            "sync_started_at_utc", "sync_finished_at_utc", "status",
            "oura_daily_rows", "oura_sleep_rows", "oura_readiness_rows",
            "oura_activity_rows", "oura_stress_rows", "oura_resilience_rows",
            "garmin_activity_rows", "notes_or_errors",
        ],
        "key_cols": None,  # append-only
    },
}

# Desired tab order for a clean sheet
TAB_ORDER = [
    "Daily", "Oura_Sleep", "Oura_Readiness", "Oura_Activity",
    "Oura_Stress", "Oura_Resilience", "Garmin_Activities", "Sync_Log",
]


# ── Manager ───────────────────────────────────────────────────────────────────

class SheetsManager:
    def __init__(self, sheet_id: str):
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._gc  = gspread.authorize(creds)
        self._sh  = self._gc.open_by_key(sheet_id)
        self._ws  = {}  # name → Worksheet cache

    # ── Worksheet access ──────────────────────────────────────────────────────

    def get_ws(self, name: str) -> gspread.Worksheet:
        if name in self._ws:
            return self._ws[name]

        schema  = SCHEMAS[name]
        headers = schema["headers"]

        try:
            ws = self._sh.worksheet(name)
            # Ensure headers are present if sheet was somehow created empty
            if not ws.row_values(1):
                ws.append_row(headers)
        except gspread.WorksheetNotFound:
            ws = self._sh.add_worksheet(name, rows=2000, cols=len(headers) + 2)
            ws.append_row(headers)
            self._format_header(ws, len(headers))

        self._ws[name] = ws
        return ws

    def init_all(self):
        """Pre-create all worksheets in the desired order."""
        for name in TAB_ORDER:
            self.get_ws(name)

    # ── Formatting ────────────────────────────────────────────────────────────

    def _format_header(self, ws: gspread.Worksheet, ncols: int):
        """Freeze row 1, bold + light-blue header, auto-resize columns."""
        try:
            ws.freeze(rows=1)
            sid = ws.id
            self._sh.batch_update({"requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sid,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {"bold": True},
                                "backgroundColor": {
                                    "red": 0.82, "green": 0.88, "blue": 0.97
                                },
                            }
                        },
                        "fields": "userEnteredFormat(textFormat,backgroundColor)",
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": sid,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": ncols,
                        }
                    }
                },
            ]})
        except Exception:
            pass  # formatting is best-effort

    # ── Upsert ────────────────────────────────────────────────────────────────

    def upsert(self, tab: str, row: list) -> bool:
        """
        Write row to tab, updating an existing row if the key already exists.
        For append-only tabs (key_cols=None), always appends.
        Returns True if an existing row was updated, False if a new row was appended.
        """
        schema   = SCHEMAS[tab]
        key_cols = schema["key_cols"]
        ws       = self.get_ws(tab)

        if key_cols is None:
            ws.append_row(row, value_input_option="USER_ENTERED")
            return False

        all_rows = ws.get_all_values()
        if len(all_rows) <= 1:
            ws.append_row(row, value_input_option="USER_ENTERED")
            return False

        key = tuple(str(row[i]) for i in key_cols)

        for i, existing in enumerate(all_rows[1:], start=2):  # row 2+ (1-indexed)
            ekey = tuple(
                str(existing[j]) if j < len(existing) else ""
                for j in key_cols
            )
            if ekey == key:
                ws.update([row], f"A{i}", value_input_option="USER_ENTERED")
                return True

        ws.append_row(row, value_input_option="USER_ENTERED")
        return False

    def upsert_many(self, tab: str, rows: list) -> dict:
        """Upsert multiple rows. Returns {"inserted": n, "updated": n}."""
        counts = {"inserted": 0, "updated": 0}
        for row in rows:
            updated = self.upsert(tab, row)
            if updated:
                counts["updated"] += 1
            else:
                counts["inserted"] += 1
        return counts
