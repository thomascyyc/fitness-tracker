"""SQLite database operations for fitness competition tracker."""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "fitness_tracker.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile TEXT NOT NULL,
            date TEXT NOT NULL,
            cardio_mins REAL DEFAULT 0,
            light_mins REAL DEFAULT 0,
            strength_reps INTEGER DEFAULT 0,
            flex_mins REAL DEFAULT 0,
            points REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS week_wins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile TEXT NOT NULL,
            week_start_date TEXT NOT NULL,
            points_earned REAL DEFAULT 0,
            won INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS month_wins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile TEXT NOT NULL,
            month TEXT NOT NULL,
            weeks_won REAL DEFAULT 0,
            won INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# --- Entry CRUD ---

def add_entry(profile, date, cardio_mins, light_mins, strength_reps, flex_mins, points):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO entries (profile, date, cardio_mins, light_mins, strength_reps, flex_mins, points, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (profile, date, cardio_mins, light_mins, strength_reps, flex_mins, points,
         datetime.now().isoformat()),
    )
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def get_entries_for_date(profile, date):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM entries WHERE profile = ? AND date = ? ORDER BY created_at DESC",
        (profile, date),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_entries_for_range(start_date, end_date, profile=None):
    conn = get_connection()
    if profile:
        rows = conn.execute(
            "SELECT * FROM entries WHERE profile = ? AND date >= ? AND date <= ? ORDER BY date, created_at",
            (profile, start_date, end_date),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM entries WHERE date >= ? AND date <= ? ORDER BY date, created_at",
            (start_date, end_date),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_entry(entry_id, cardio_mins, light_mins, strength_reps, flex_mins, points):
    conn = get_connection()
    conn.execute(
        """UPDATE entries SET cardio_mins = ?, light_mins = ?, strength_reps = ?, flex_mins = ?, points = ?
           WHERE id = ?""",
        (cardio_mins, light_mins, strength_reps, flex_mins, points, entry_id),
    )
    conn.commit()
    conn.close()


def delete_entry(entry_id):
    conn = get_connection()
    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


# --- Aggregation queries ---

def get_week_points(profile, week_start, week_end):
    conn = get_connection()
    result = conn.execute(
        "SELECT COALESCE(SUM(points), 0) as total FROM entries WHERE profile = ? AND date >= ? AND date <= ?",
        (profile, week_start, week_end),
    ).fetchone()
    conn.close()
    return result["total"]


def get_daily_breakdown(week_start, week_end):
    conn = get_connection()
    rows = conn.execute(
        """SELECT date, profile, COALESCE(SUM(points), 0) as total
           FROM entries WHERE date >= ? AND date <= ?
           GROUP BY date, profile ORDER BY date""",
        (week_start, week_end),
    ).fetchall()
    conn.close()
    breakdown = {}
    for r in rows:
        date = r["date"]
        if date not in breakdown:
            breakdown[date] = {"TC": 0, "MS": 0}
        breakdown[date][r["profile"]] = r["total"]
    return breakdown


# --- Week wins ---

def add_week_win(profile, week_start, points_earned, won):
    conn = get_connection()
    conn.execute(
        "INSERT INTO week_wins (profile, week_start_date, points_earned, won) VALUES (?, ?, ?, ?)",
        (profile, week_start, points_earned, won),
    )
    conn.commit()
    conn.close()


def get_week_wins_for_month(profile, month_start, month_end):
    """Count week wins for a profile within a date range. won=1 counts as 1, won=-1 (tie) counts as 0.5."""
    conn = get_connection()
    result = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN won = 1 THEN 1.0 WHEN won = -1 THEN 0.5 ELSE 0.0 END), 0) as wins
           FROM week_wins WHERE profile = ? AND week_start_date >= ? AND week_start_date <= ?""",
        (profile, month_start, month_end),
    ).fetchone()
    conn.close()
    return result["wins"]


def get_all_time_week_wins(profile):
    conn = get_connection()
    result = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN won = 1 THEN 1.0 WHEN won = -1 THEN 0.5 ELSE 0.0 END), 0) as wins FROM week_wins WHERE profile = ?",
        (profile,),
    ).fetchone()
    conn.close()
    return result["wins"]


def week_already_ended(week_start):
    conn = get_connection()
    result = conn.execute(
        "SELECT COUNT(*) as cnt FROM week_wins WHERE week_start_date = ?",
        (week_start,),
    ).fetchone()
    conn.close()
    return result["cnt"] > 0


# --- Month wins ---

def add_month_win(profile, month, weeks_won, won):
    conn = get_connection()
    conn.execute(
        "INSERT INTO month_wins (profile, month, weeks_won, won) VALUES (?, ?, ?, ?)",
        (profile, month, weeks_won, won),
    )
    conn.commit()
    conn.close()


def get_month_wins_for_year(profile, year):
    conn = get_connection()
    result = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN won = 1 THEN 1.0 WHEN won = -1 THEN 0.5 ELSE 0.0 END), 0) as wins FROM month_wins WHERE profile = ? AND month LIKE ?",
        (profile, f"{year}%"),
    ).fetchone()
    conn.close()
    return result["wins"]


def get_all_time_month_wins(profile):
    conn = get_connection()
    result = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN won = 1 THEN 1.0 WHEN won = -1 THEN 0.5 ELSE 0.0 END), 0) as wins FROM month_wins WHERE profile = ?",
        (profile,),
    ).fetchone()
    conn.close()
    return result["wins"]
