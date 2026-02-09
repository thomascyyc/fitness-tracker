"""Fitness Competition Tracker — Phase 1: Core logging + head-to-head dashboard."""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta

import database as db
from scoring import calculate_points

# --- Page config ---
st.set_page_config(
    page_title="Fitness Tracker",
    page_icon="\U0001f4aa",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- Init DB ---
db.init_db()

# --- Constants ---
PROFILES = ["TC", "MS"]


# --- Helper functions ---

def get_current_week_range(ref_date=None):
    """Return (monday, sunday) for the week containing ref_date."""
    if ref_date is None:
        ref_date = date.today()
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_month_range(ref_date=None):
    """Return (first_day, last_day) of the month containing ref_date."""
    if ref_date is None:
        ref_date = date.today()
    first = ref_date.replace(day=1)
    if ref_date.month == 12:
        last = ref_date.replace(year=ref_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = ref_date.replace(month=ref_date.month + 1, day=1) - timedelta(days=1)
    return first, last


# --- Cached queries ---

@st.cache_data(ttl=3600)
def cached_week_points(profile, week_start, week_end):
    return db.get_week_points(profile, str(week_start), str(week_end))


@st.cache_data(ttl=3600)
def cached_daily_breakdown(week_start, week_end):
    return db.get_daily_breakdown(str(week_start), str(week_end))


@st.cache_data(ttl=3600)
def cached_week_wins_for_month(profile, month_start, month_end):
    return db.get_week_wins_for_month(profile, str(month_start), str(month_end))


@st.cache_data(ttl=3600)
def cached_month_wins_for_year(profile, year):
    return db.get_month_wins_for_year(profile, year)


@st.cache_data(ttl=3600)
def cached_all_time_week_wins(profile):
    return db.get_all_time_week_wins(profile)


def clear_caches():
    st.cache_data.clear()


# --- Session state init ---

if "editing_entry_id" not in st.session_state:
    st.session_state.editing_entry_id = None
if "confirm_delete_id" not in st.session_state:
    st.session_state.confirm_delete_id = None


# ============================================================
# SECTION 1: ACTIVITY LOG
# ============================================================

st.title("Fitness Competition Tracker")

st.header("Log Activity")

with st.form("log_entry", clear_on_submit=True):
    profile = st.selectbox("Profile", PROFILES)
    log_date = st.date_input(
        "Date",
        value=date.today(),
        max_value=date.today(),
        min_value=date.today() - timedelta(days=7),
    )
    cardio = st.number_input("Cardio (minutes)", min_value=0.0, value=0.0, step=1.0)
    light = st.number_input("Light Activity (minutes)", min_value=0.0, value=0.0, step=1.0)
    strength = st.number_input("Strength (reps)", min_value=0, value=0, step=1)
    flex = st.number_input("Flexibility/Mobility (minutes)", min_value=0.0, value=0.0, step=1.0)

    points_preview = calculate_points(cardio, light, strength, flex)
    st.markdown(f"**Points for this entry: {points_preview:.1f}**")

    submitted = st.form_submit_button("Log Entry", use_container_width=True)

if submitted:
    # Validate extreme values
    extreme = any(v > 500 for v in [cardio, light, strength, flex])
    if extreme:
        st.warning("One or more values exceed 500 — double-check for typos.")

    if log_date != date.today():
        st.info(f"Logging for {log_date.strftime('%A, %b %d')} (not today).")

    if points_preview == 0:
        st.error("Nothing to log — enter at least one activity.")
    else:
        db.add_entry(
            profile=profile,
            date=str(log_date),
            cardio_mins=cardio,
            light_mins=light,
            strength_reps=strength,
            flex_mins=flex,
            points=points_preview,
        )
        clear_caches()
        st.success(f"Logged {points_preview:.1f} pts for {profile} on {log_date.strftime('%b %d')}!")
        st.rerun()


# --- Today's entries for selected profile ---

st.subheader("Today's Entries")

# Use the profile from the form's last selection via a separate selector for viewing
view_profile = st.selectbox("View entries for", PROFILES, key="view_profile")
today_entries = db.get_entries_for_date(view_profile, str(date.today()))

if not today_entries:
    st.info("No entries yet today — start logging!")
else:
    for entry in today_entries:
        created = entry["created_at"][:16].replace("T", " ")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(
                f"**{created}** — "
                f"Cardio: {entry['cardio_mins']:.0f}m | "
                f"Light: {entry['light_mins']:.0f}m | "
                f"Strength: {entry['strength_reps']}r | "
                f"Flex: {entry['flex_mins']:.0f}m | "
                f"**{entry['points']:.1f} pts**"
            )
        with col2:
            if st.button("Edit", key=f"edit_{entry['id']}", use_container_width=True):
                st.session_state.editing_entry_id = entry["id"]
                st.rerun()
            if st.session_state.confirm_delete_id == entry["id"]:
                st.warning("Confirm delete?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Yes", key=f"yes_del_{entry['id']}", use_container_width=True):
                        db.delete_entry(entry["id"])
                        st.session_state.confirm_delete_id = None
                        clear_caches()
                        st.rerun()
                with c2:
                    if st.button("No", key=f"no_del_{entry['id']}", use_container_width=True):
                        st.session_state.confirm_delete_id = None
                        st.rerun()
            else:
                if st.button("Delete", key=f"del_{entry['id']}", use_container_width=True):
                    st.session_state.confirm_delete_id = entry["id"]
                    st.rerun()

    # Edit form
    if st.session_state.editing_entry_id is not None:
        edit_entry = None
        for e in today_entries:
            if e["id"] == st.session_state.editing_entry_id:
                edit_entry = e
                break
        if edit_entry:
            st.markdown("---")
            st.subheader("Edit Entry")
            with st.form("edit_form"):
                e_cardio = st.number_input("Cardio (min)", min_value=0.0, value=float(edit_entry["cardio_mins"]), step=1.0)
                e_light = st.number_input("Light (min)", min_value=0.0, value=float(edit_entry["light_mins"]), step=1.0)
                e_strength = st.number_input("Strength (reps)", min_value=0, value=int(edit_entry["strength_reps"]), step=1)
                e_flex = st.number_input("Flex (min)", min_value=0.0, value=float(edit_entry["flex_mins"]), step=1.0)
                e_points = calculate_points(e_cardio, e_light, e_strength, e_flex)
                st.markdown(f"**Updated points: {e_points:.1f}**")
                col_save, col_cancel = st.columns(2)
                with col_save:
                    save_edit = st.form_submit_button("Save", use_container_width=True)
                with col_cancel:
                    cancel_edit = st.form_submit_button("Cancel", use_container_width=True)
            if save_edit:
                db.update_entry(edit_entry["id"], e_cardio, e_light, e_strength, e_flex, e_points)
                st.session_state.editing_entry_id = None
                clear_caches()
                st.success("Entry updated!")
                st.rerun()
            if cancel_edit:
                st.session_state.editing_entry_id = None
                st.rerun()


# ============================================================
# SECTION 2: CURRENT WEEK STANDINGS
# ============================================================

st.markdown("---")
st.header("Current Week Standings")

week_start, week_end = get_current_week_range()
st.markdown(f"**Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}**")

tc_pts = cached_week_points("TC", str(week_start), str(week_end))
ms_pts = cached_week_points("MS", str(week_start), str(week_end))
max_pts = max(tc_pts, ms_pts, 1)  # avoid division by zero

# TC progress
tc_ratio = tc_pts / max_pts
ms_ratio = ms_pts / max_pts

tc_color = "#4CAF50" if tc_pts >= ms_pts else "#666666"
ms_color = "#4CAF50" if ms_pts >= tc_pts else "#666666"

st.markdown(f"**TC**")
st.progress(min(tc_ratio, 1.0))
st.markdown(f"<p style='text-align:right; color:{tc_color}; font-size:1.2em; margin-top:-15px;'><b>{tc_pts:.1f} pts</b></p>", unsafe_allow_html=True)

st.markdown(f"**MS**")
st.progress(min(ms_ratio, 1.0))
st.markdown(f"<p style='text-align:right; color:{ms_color}; font-size:1.2em; margin-top:-15px;'><b>{ms_pts:.1f} pts</b></p>", unsafe_allow_html=True)

# Lead indicator
diff = tc_pts - ms_pts
if diff > 0:
    st.markdown(f"### TC leads by +{diff:.1f} pts!")
elif diff < 0:
    st.markdown(f"### MS leads by +{abs(diff):.1f} pts!")
else:
    st.markdown("### Tied!")


# ============================================================
# SECTION 3: DAILY BREAKDOWN
# ============================================================

with st.expander("Daily Breakdown (this week)"):
    breakdown = cached_daily_breakdown(str(week_start), str(week_end))
    if not breakdown:
        st.info("No entries this week yet.")
    else:
        days = []
        current = week_start
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i in range(7):
            d = week_start + timedelta(days=i)
            d_str = str(d)
            tc_day = breakdown.get(d_str, {}).get("TC", 0)
            ms_day = breakdown.get(d_str, {}).get("MS", 0)
            is_today = d == date.today()
            label = f"**{day_names[i]}**" if is_today else day_names[i]
            days.append({
                "Day": f"{'> ' if is_today else ''}{day_names[i]} {d.strftime('%m/%d')}",
                "TC": f"{tc_day:.1f}",
                "MS": f"{ms_day:.1f}",
            })
        df = pd.DataFrame(days)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# SECTION 4: CHAMPIONSHIP TRACKER
# ============================================================

st.markdown("---")
st.header("Championships")

month_start, month_end = get_month_range()
current_year = str(date.today().year)
current_month = date.today().strftime("%Y-%m")

# This Month
st.subheader(f"This Month ({date.today().strftime('%B %Y')})")
tc_month_wins = cached_week_wins_for_month("TC", str(month_start), str(month_end))
ms_month_wins = cached_week_wins_for_month("MS", str(month_start), str(month_end))
col1, col2 = st.columns(2)
with col1:
    st.metric("TC Week Wins", tc_month_wins)
with col2:
    st.metric("MS Week Wins", ms_month_wins)

# This Year
st.subheader(f"This Year ({current_year})")
tc_year_wins = cached_month_wins_for_year("TC", current_year)
ms_year_wins = cached_month_wins_for_year("MS", current_year)
col1, col2 = st.columns(2)
with col1:
    st.metric("TC Month Wins", tc_year_wins)
with col2:
    st.metric("MS Month Wins", ms_year_wins)

# All-Time
st.subheader("All-Time")
tc_alltime = cached_all_time_week_wins("TC")
ms_alltime = cached_all_time_week_wins("MS")
col1, col2 = st.columns(2)
with col1:
    st.metric("TC Total Week Wins", tc_alltime)
with col2:
    st.metric("MS Total Week Wins", ms_alltime)


# ============================================================
# SECTION 5: ADMIN CONTROLS
# ============================================================

st.markdown("---")
with st.expander("Admin Controls"):
    st.markdown("### End Week & Declare Winner")

    already_ended = db.week_already_ended(str(week_start))
    if already_ended:
        st.warning(f"Week of {week_start.strftime('%b %d')} has already been finalized.")
    else:
        st.markdown(f"Finalize week of **{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}**")
        st.markdown(f"- TC: **{tc_pts:.1f}** pts")
        st.markdown(f"- MS: **{ms_pts:.1f}** pts")

        if st.button("End Week & Declare Winner", use_container_width=True, type="primary"):
            if tc_pts == 0 and ms_pts == 0:
                st.error("No entries this week — nothing to finalize.")
            else:
                if tc_pts > ms_pts:
                    db.add_week_win("TC", str(week_start), tc_pts, 1)
                    db.add_week_win("MS", str(week_start), ms_pts, 0)
                    winner_msg = f"TC wins with {tc_pts:.1f} pts!"
                elif ms_pts > tc_pts:
                    db.add_week_win("TC", str(week_start), tc_pts, 0)
                    db.add_week_win("MS", str(week_start), ms_pts, 1)
                    winner_msg = f"MS wins with {ms_pts:.1f} pts!"
                else:
                    # Tie: both get won=-1, counted as 0.5 wins in queries
                    db.add_week_win("TC", str(week_start), tc_pts, -1)
                    db.add_week_win("MS", str(week_start), ms_pts, -1)
                    winner_msg = f"It's a tie at {tc_pts:.1f} pts! Both get 0.5 week wins."

                clear_caches()
                st.success(f"Week ended! {winner_msg}")
                st.rerun()
