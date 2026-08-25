import datetime
import math
import pandas as pd
import requests
import streamlit as st

# ------------------------------------------------------------------------------
# PAGE CONFIGURATION
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="FPL Master Executive Analytics",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------------------
# UNIVERSAL LIGHT THEME UI/UX ENGINE
# ------------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Force high-contrast Light Theme global canvas */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f8fafc !important;
        color: #0f172a !important;
    }
    
    /* Universal Typography & Label Contrast */
    h1, h2, h3, h4, h5, h6, 
    label, 
    div[data-testid="stMetricLabel"] p, 
    .stCaption p, 
    div[data-testid="stMarkdownContainer"] p {
        color: #0f172a !important;
        font-weight: 700 !important;
        opacity: 1 !important;
    }

    /* Sleek Modern Header Banner */
    .executive-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #047857 100%);
        padding: 26px 36px;
        border-radius: 16px;
        margin-bottom: 25px;
        box-shadow: 0 10px 20px -5px rgba(15, 23, 42, 0.25);
    }
    .executive-header h1 {
        color: #ffffff !important;
        font-weight: 800 !important;
        margin: 0;
        font-size: 2.2rem;
    }
    .executive-header .header-subtitle {
        color: #ffffff !important;
        display: block;
        margin-top: 6px;
        margin-bottom: 0;
        font-size: 1.05rem;
        font-weight: 500 !important;
        opacity: 1 !important;
    }

    /* Metric Values (Large Numbers) */
    div[data-testid="stMetricValue"] {
        color: #0284c7 !important;
        font-weight: 800 !important;
        font-size: 2.2rem !important;
    }

    /* Input Fields & Dropdowns */
    div[data-baseweb="input"], input {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1.5px solid #cbd5e1 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #0284c7 !important;
        box-shadow: 0 0 0 1px #0284c7 !important;
    }

    /* Tab Navigation Bar */
    button[data-baseweb="tab"] p {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        color: #64748b !important;
    }
    button[aria-selected="true"][data-baseweb="tab"] p {
        color: #047857 !important;
    }
    button[aria-selected="true"][data-baseweb="tab"] {
        border-bottom-color: #047857 !important;
    }

    /* Custom Strategic Cards (Alerts & Summaries) */
    .rec-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 5px solid #059669;
        padding: 18px 22px;
        border-radius: 12px;
        margin-bottom: 15px;
        color: #0f172a;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .rec-card-danger {
        background: #fef2f2;
        border-color: #fca5a5;
        border-left-color: #dc2626;
        color: #991b1b;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header Banner Display
st.markdown(
    """
    <div class="executive-header">
        <h1>⚽ FPL Master Executive Intelligence</h1>
        <span class="header-subtitle">Advanced Real-Time Market Analytics, Rival Mini-League Spy & Performance AI</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------
# GLOBAL CONSTANTS & API HELPERS
# ------------------------------------------------------------------------------
HEADERS = {"User-Agent": "Mozilla/5.0"}
DEFAULT_LEAGUE_ID = "1304670"
MY_TEAM_ID = "4224092"

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
ALL_CHIPS = ["WILDCARD", "FREEHIT", "BBOOST", "3XC"]


@st.cache_data(ttl=300)
def fetch_fpl_data():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    res = requests.get(url, headers=HEADERS)
    return res.json()


@st.cache_data(ttl=300)
def fetch_fixtures_data():
    url = "https://fantasy.premierleague.com/api/fixtures/"
    res = requests.get(url, headers=HEADERS)
    return res.json() if res.status_code == 200 else []


def fetch_league_data(league_id):
    """Fetches ALL managers in a classic mini-league across all API pages."""
    all_results = []
    page = 1
    league_name = "Mini-League"

    while True:
        url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/?page_standings={page}"
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200:
            break

        data = res.json()
        league_name = data.get("league", {}).get("name", league_name)
        results = data.get("standings", {}).get("results", [])

        if not results:
            break

        all_results.extend(results)

        if not data.get("standings", {}).get("has_next", False):
            break
        page += 1

    return {
        "league": {"name": league_name},
        "standings": {"results": all_results},
    }


def get_current_gw(events):
    for e in events:
        if e.get("is_current"):
            return e["id"]
    return 1


def get_next_gw_fixtures(fixtures, next_gw):
    next_fixtures = {}
    for f in fixtures:
        if f.get("event") == next_gw:
            h_team, a_team = f["team_h"], f["team_a"]
            next_fixtures[h_team] = {
                "opp": a_team,
                "fdr": f["team_h_difficulty"],
                "is_home": True,
            }
            next_fixtures[a_team] = {
                "opp": h_team,
                "fdr": f["team_a_difficulty"],
                "is_home": False,
            }
    return next_fixtures


def calculate_saved_fts_and_history(entry_id, target_gw):
    hist_url = (
        f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
    )
    res = requests.get(hist_url, headers=HEADERS)
    if res.status_code != 200:
        return {
            "Chips Used": "None",
            "Chips Remaining": ", ".join(ALL_CHIPS),
            "Hits Cost": 0,
            "Saved FTs": 1,
        }

    data = res.json()
    used_chips_raw = [c["name"].upper() for c in data.get("chips", [])]
    chips_used_str = ", ".join(used_chips_raw) if used_chips_raw else "None"

    remaining_chips = [c for c in ALL_CHIPS if c not in used_chips_raw]
    chips_rem_str = (
        ", ".join(remaining_chips) if remaining_chips else "All Used"
    )

    chip_gws = {c["event"]: c["name"].lower() for c in data.get("chips", [])}
    current_history = data.get("current", [])

    history_up_to_gw = [
        gw for gw in current_history if gw.get("event", 0) <= target_gw
    ]
    total_hits = sum(
        gw.get("event_transfers_cost", 0) for gw in history_up_to_gw
    )

    if target_gw <= 1 or not history_up_to_gw:
        return {
            "Chips Used": chips_used_str,
            "Chips Remaining": chips_rem_str,
            "Hits Cost": total_hits,
            "Saved FTs": 1,
        }

    fts_available = 1
    for gw_info in history_up_to_gw:
        transfers_made = gw_info.get("event_transfers", 0)
        chip_played = chip_gws.get(gw_info["event"], None)
        if chip_played in ["wildcard", "freehit"]:
            fts_available = min(5, fts_available + 1)
        else:
            fts_remaining = max(0, fts_available - transfers_made)
            fts_available = min(5, fts_remaining + 1)

    return {
        "Chips Used": chips_used_str,
        "Chips Remaining": chips_rem_str,
        "Hits Cost": total_hits,
        "Saved FTs": fts_available,
    }


def fetch_manager_picks(entry_id, target_gw, player_dict):
    picks_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{target_gw}/picks/"
    res = requests.get(picks_url, headers=HEADERS)
    if res.status_code != 200:
        return {
            "Bank": 0.0,
            "Captain": "Unknown",
            "VC": "Unknown",
            "Bench Pts": 0,
            "Squad": [],
            "Cap_ID": None,
            "Starting": [],
            "GW_Pts": 0,
            "GW_Rank": "-",
        }

    p_data = res.json()
    entry_hist = p_data.get("entry_history", {})
    bank = entry_hist.get("bank", 0) / 10
    bench_pts = entry_hist.get("points_on_bench", 0)
    gw_pts = entry_hist.get("points", 0)
    gw_rank = entry_hist.get("rank", "-")

    captain, vc, cap_id = "Unknown", "Unknown", None
    squad_ids, starting_ids = [], []

    for pick in p_data.get("picks", []):
        pid = pick["element"]
        squad_ids.append(pid)
        if pick.get("position", 12) <= 11:
            starting_ids.append(pid)
        if pick.get("is_captain"):
            captain = player_dict.get(pid, "Unknown")
            cap_id = pid
        if pick.get("is_vice_captain"):
            vc = player_dict.get(pid, "Unknown")

    return {
        "Bank": bank,
        "Captain": captain,
        "VC": vc,
        "Bench Pts": bench_pts,
        "Squad": squad_ids,
        "Cap_ID": cap_id,
        "Starting": starting_ids,
        "GW_Pts": gw_pts,
        "GW_Rank": gw_rank,
    }


# Load Core Dataset
data = fetch_fpl_data()
fixtures = fetch_fixtures_data()

elements = data["elements"]
teams = {t["id"]: t["name"] for t in data["teams"]}
events = data["events"]
current_gw = get_current_gw(events)
next_gw = current_gw + 1

next_fixtures_map = get_next_gw_fixtures(fixtures, next_gw)
player_dict = {p["id"]: p["web_name"] for p in elements}
player_obj_dict = {p["id"]: p for p in elements}

tab1, tab2, tab3 = st.tabs(
    ["📊 Market & Price Dynamics", "🕵️ Mini-League Spy", "🤖 AI Squad Advisor"]
)

# ------------------------------------------------------------------------------
# TAB 1: MARKET TRACKER
# ------------------------------------------------------------------------------
with tab1:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    next_price_update = now_utc.replace(
        hour=1, minute=30, second=0, microsecond=0
    )
    if now_utc >= next_price_update:
        next_price_update += datetime.timedelta(days=1)
    time_to_price_change = next_price_update - now_utc

    next_event = next((e for e in events if e.get("is_next")), None)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        hours_p, remainder_p = divmod(
            int(time_to_price_change.total_seconds()), 3600
        )
        mins_p, _ = divmod(remainder_p, 60)
        st.metric("⏳ Price Change Window", f"{hours_p}h {mins_p}m")
        st.caption("FPL algorithm updates player pricing daily at 01:30 UTC")

    with col_t2:
        if next_event and next_event.get("deadline_time"):
            deadline_dt = datetime.datetime.fromisoformat(
                next_event["deadline_time"].replace("Z", "+00:00")
            )
            time_to_deadline = deadline_dt - now_utc
            days_d = time_to_deadline.days
            hours_d, remainder_d = divmod(time_to_deadline.seconds, 3600)
            mins_d, _ = divmod(remainder_d, 60)
            st.metric(
                "🚨 GW Deadline Countdown", f"{days_d}d {hours_d}h {mins_d}m"
            )
            st.caption(
                f"Gameweek Deadline: {next_event['name']} ({deadline_dt.strftime('%d %b %H:%M UTC')})"
            )
        else:
            st.metric("🚨 GW Deadline Countdown", "TBD")

    st.markdown("---")

    top_n = st.slider(
        "🎚️ Market Depth Filter (Number of Players):",
        min_value=5,
        max_value=50,
        value=15,
        step=5,
    )

    tracker = []
    for p in elements:
        net = p["transfers_in_event"] - p["transfers_out_event"]
        abs_net = abs(net)

        if abs_net >= 40000:
            days_str = "🔥 Tonight"
        elif abs_net > 0:
            days_est = math.ceil((40000 - abs_net) / abs_net)
            days_str = "1 day" if days_est <= 1 else f"~{days_est} days"
        else:
            days_str = "No momentum"

        tracker.append(
            {
                "Name": p["web_name"],
                "Pos": POSITION_MAP.get(p["element_type"], "UNK"),
                "Cost (£m)": p["now_cost"] / 10,
                "Net Transfers": net,
                "Est. Price Change": days_str,
            }
        )

    df_tracker = pd.DataFrame(tracker)
    df_risers = df_tracker.sort_values(
        by="Net Transfers", ascending=False
    ).head(top_n)
    df_fallers = df_tracker.sort_values(by="Net Transfers", ascending=True).head(
        top_n
    )

    column_order = [
        "Name",
        "Pos",
        "Cost (£m)",
        "Net Transfers",
        "Est. Price Change",
    ]
    df_risers = df_risers[column_order]
    df_fallers = df_fallers[column_order]

    c1, c2 = st.columns(2)
    table_h = min((top_n + 1) * 35 + 5, 800)

    with c1:
        st.markdown("### 📈 Rising Assets (Buy Pressure)")
        st.dataframe(
            df_risers,
            use_container_width=True,
            hide_index=True,
            height=table_h,
            column_config={
                "Cost (£m)": st.column_config.NumberColumn(format="£%.1fm"),
                "Net Transfers": st.column_config.NumberColumn(format="%+d"),
            },
        )
    with c2:
        st.markdown("### 📉 Falling Assets (Sell Pressure)")
        st.dataframe(
            df_fallers,
            use_container_width=True,
            hide_index=True,
            height=table_h,
            column_config={
                "Cost (£m)": st.column_config.NumberColumn(format="£%.1fm"),
                "Net Transfers": st.column_config.NumberColumn(format="%+d"),
            },
        )

# ------------------------------------------------------------------------------
# TAB 2: MINI-LEAGUE SPY
# ------------------------------------------------------------------------------
with tab2:
    col_l1, col_l2 = st.columns([3, 1])
    with col_l1:
        st.markdown("### 🔎 Executive Mini-League Intelligence")
    with col_l2:
        selected_gw = st.selectbox(
            "Select Gameweek:",
            options=list(range(1, current_gw + 1)),
            index=current_gw - 1,
            key="tab2_gw_select",
        )

    col_in1, col_in2 = st.columns(2)
    with col_in1:
        league_id = st.text_input(
            "FPL Mini-League ID:", value=DEFAULT_LEAGUE_ID, key="ml_league_id"
        )
    with col_in2:
        my_entry_id = st.text_input(
            "Your FPL Team ID:", value=MY_TEAM_ID, key="ml_my_id"
        )

    if league_id and my_entry_id:
        with st.spinner(
            f"Loading Gameweek {selected_gw} Mini-League standings and tactical data..."
        ):
            league_json = fetch_league_data(league_id)
            if league_json and "standings" in league_json:
                st.markdown(
                    f"#### League Standings: **{league_json['league']['name']}**"
                )

                my_picks = fetch_manager_picks(
                    my_entry_id, selected_gw, player_dict
                )
                my_squad_set = set(my_picks["Squad"])

                standings = league_json["standings"]["results"]

                # Load manager picks and store prior totals for movement analysis
                manager_data = []
                for mgr in standings:
                    picks = fetch_manager_picks(
                        mgr["entry"], selected_gw, player_dict
                    )
                    hist = calculate_saved_fts_and_history(
                        mgr["entry"], selected_gw
                    )
                    prev_total = mgr["total"] - picks["GW_Pts"]
                    manager_data.append(
                        {
                            "mgr": mgr,
                            "picks": picks,
                            "hist": hist,
                            "prev_total": prev_total,
                        }
                    )

                # Derive exact mini-league rank trajectory using previous GW total points
                sorted_by_prev = sorted(
                    manager_data, key=lambda x: x["prev_total"], reverse=True
                )
                prev_rank_map = {
                    item["mgr"]["entry"]: idx + 1
                    for idx, item in enumerate(sorted_by_prev)
                }

                leader_pts = manager_data[0]["mgr"]["total"] if manager_data else 0
                rivals = []

                for idx, item in enumerate(manager_data):
                    mgr = item["mgr"]
                    picks = item["picks"]
                    hist = item["hist"]

                    diff_ids = set(picks["Squad"]) - my_squad_set
                    diff_names = [
                        player_dict.get(pid, "") for pid in list(diff_ids)[:3]
                    ]

                    curr_rank = idx + 1
                    prev_rank = prev_rank_map.get(mgr["entry"], curr_rank)

                    if selected_gw == 1:
                        trend = "⚪ NEW"
                    else:
                        rank_diff = prev_rank - curr_rank
                        if rank_diff > 0:
                            trend = f"🟢 (+{rank_diff})"
                        elif rank_diff < 0:
                            trend = f"🔴 ({rank_diff})"
                        else:
                            trend = "⚪ ="

                    pts_off_lead = mgr["total"] - leader_pts
                    pts_str = "Leader" if pts_off_lead == 0 else f"{pts_off_lead} pts"

                    rivals.append(
                        {
                            "Rank": f"{curr_rank} {trend}",
                            "Manager": mgr["player_name"],
                            "Team": mgr["entry_name"],
                            "GW Pts": picks["GW_Pts"],
                            "Total Pts": mgr["total"],
                            "Leader Gap": pts_str,
                            "Saved FTs": f"{hist['Saved FTs']} FT",
                            "Bank": f"£{picks['Bank']:.1f}m",
                            "Captain (VC)": f"{picks['Captain']} ({picks['VC']})",
                            "Bench Pts": picks["Bench Pts"],
                            "Differentials": ", ".join(diff_names)
                            if diff_names
                            else "Identical Squad",
                            "Chips Used": hist["Chips Used"],
                            "Chips Remaining": hist["Chips Remaining"],
                            "Hits": f"-{hist['Hits Cost']} pts",
                        }
                    )

                st.dataframe(
                    pd.DataFrame(rivals),
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown("---")

                # Shield & Sword Matrix
                st.markdown("### ⚔️ Target Window Tactical Matrix")

                my_rank_idx = next(
                    (
                        i
                        for i, m in enumerate(standings)
                        if str(m["entry"]) == str(my_entry_id)
                    ),
                    None,
                )

                if my_rank_idx is not None:
                    start_idx = max(0, my_rank_idx - 5)
                    end_idx = min(len(standings), my_rank_idx + 6)
                    target_rivals = standings[start_idx:end_idx]
                    num_target_rivals = len(target_rivals)

                    st.caption(
                        f"🎯 **Target Window Focus:** Analyzing your **{num_target_rivals} nearest competitors** (ranks {start_idx + 1} to {end_idx}) to isolate structural exposure vs. rank-climbing vectors."
                    )

                    starting_counts_target, captain_counts_target = {}, {}
                    for mgr in target_rivals:
                        mgr_picks = fetch_manager_picks(
                            mgr["entry"], selected_gw, player_dict
                        )
                        for pid in mgr_picks["Starting"]:
                            starting_counts_target[pid] = (
                                starting_counts_target.get(pid, 0) + 1
                            )
                        if mgr_picks["Cap_ID"]:
                            captain_counts_target[mgr_picks["Cap_ID"]] = (
                                captain_counts_target.get(
                                    mgr_picks["Cap_ID"], 0
                                )
                                + 1
                            )

                    shield_sword_data = []
                    weighted_data = []

                    for pid, s_count in starting_counts_target.items():
                        start_pct = (s_count / num_target_rivals) * 100
                        cap_pct = (
                            captain_counts_target.get(pid, 0)
                            / num_target_rivals
                        ) * 100
                        eo_val = start_pct + cap_pct
                        is_owned = pid in my_squad_set

                        # Ownership Logic
                        if eo_val >= 50.0 and is_owned:
                            tactic_type = "🛡️ Rank Shield"
                        elif eo_val >= 50.0 and not is_owned:
                            tactic_type = "⚔️ Rival Threat (Unowned)"
                        elif eo_val < 50.0 and is_owned:
                            tactic_type = "🗡️ Rank-Climbing Sword"
                        else:
                            tactic_type = "⚪ Low Impact Differential"

                        shield_sword_data.append(
                            {
                                "Player": player_dict.get(pid, "Unknown"),
                                "Owned by You": "✅ Yes" if is_owned else "❌ No",
                                "Target Group Starting %": f"{start_pct:.1f}%",
                                "Target Group Cap %": f"{cap_pct:.1f}%",
                                "Target Group EO %": round(eo_val, 1),
                                "Tactical Role": tactic_type,
                            }
                        )

                        # Performance Logic
                        p_obj = player_obj_dict.get(pid, {})
                        form_val = float(p_obj.get("form", 0.0))
                        xg_val = float(p_obj.get("expected_goals", 0.0))
                        xa_val = float(p_obj.get("expected_assists", 0.0))
                        xgi_val = xg_val + xa_val
                        xp_val = round((form_val * 0.5) + (xgi_val * 0.5), 2)

                        if eo_val >= 50.0 and xp_val >= 4.0 and not is_owned:
                            impact_role = "🚨 High-Priority Threat"
                        elif eo_val >= 50.0 and xp_val >= 4.0 and is_owned:
                            impact_role = "🛡️ Active Shield"
                        elif eo_val < 50.0 and xp_val >= 4.0 and is_owned:
                            impact_role = "🚀 Prime Differential Sword"
                        elif eo_val >= 50.0 and xp_val < 4.0:
                            impact_role = "💤 Low-Impact Rival Weight"
                        else:
                            impact_role = "⚪ Standard Differential"

                        weighted_data.append(
                            {
                                "Player": player_dict.get(pid, "Unknown"),
                                "Owned": "✅ Yes" if is_owned else "❌ No",
                                "Target Group EO %": round(eo_val, 1),
                                "Est. xP Proxy": xp_val,
                                "Form": form_val,
                                "xGI": round(xgi_val, 2),
                                "Impact Role": impact_role,
                            }
                        )

                    df_tactical = pd.DataFrame(shield_sword_data)
                    if not df_tactical.empty:
                        df_tactical = df_tactical.sort_values(
                            by="Target Group EO %", ascending=False
                        )

                    c_shield, c_sword = st.columns(2)
                    with c_shield:
                        st.markdown("#### 🛡️ Active Rank Shields")
                        df_shields = df_tactical[
                            df_tactical["Tactical Role"] == "🛡️ Rank Shield"
                        ][["Player", "Target Group EO %", "Target Group Cap %"]]
                        st.dataframe(
                            df_shields,
                            use_container_width=True,
                            hide_index=True,
                        )

                    with c_sword:
                        st.markdown("#### ⚔️ Dangerous Rival Threats")
                        df_threats = df_tactical[
                            df_tactical["Tactical Role"]
                            == "⚔️ Rival Threat (Unowned)"
                        ][["Player", "Target Group EO %", "Target Group Cap %"]]
                        st.dataframe(
                            df_threats,
                            use_container_width=True,
                            hide_index=True,
                        )

                    st.markdown(
                        "#### 📊 Table 1: Structural Ownership Matrix (Pure EO)"
                    )
                    df_eo_display = df_tactical[
                        [
                            "Player",
                            "Owned by You",
                            "Target Group Starting %",
                            "Target Group Cap %",
                            "Target Group EO %",
                            "Tactical Role",
                        ]
                    ]
                    eo_table_height = (
                        (len(df_eo_display) + 1) * 35 + 3
                        if not df_eo_display.empty
                        else 100
                    )
                    st.dataframe(
                        df_eo_display,
                        use_container_width=True,
                        hide_index=True,
                        height=min(eo_table_height, 450),
                        column_config={
                            "Target Group EO %": st.column_config.NumberColumn(
                                format="%.1f%%"
                            )
                        },
                    )

                    st.markdown("---")
                    st.markdown(
                        "#### 🔥 Table 2: High-Impact Threat Matrix (Weighted by Form & xP)"
                    )
                    st.caption(
                        "Combines target rival ownership with Form & Expected Metrics ($xGI$) to isolate actual high-priority threats from low-scoring dead weight."
                    )

                    df_weighted = pd.DataFrame(weighted_data)
                    if not df_weighted.empty:
                        df_weighted = df_weighted.sort_values(
                            by=["Target Group EO %", "Est. xP Proxy"],
                            ascending=[False, False],
                        )

                    weighted_table_height = (
                        (len(df_weighted) + 1) * 35 + 3
                        if not df_weighted.empty
                        else 100
                    )
                    st.dataframe(
                        df_weighted,
                        use_container_width=True,
                        hide_index=True,
                        height=min(weighted_table_height, 450),
                        column_config={
                            "Target Group EO %": st.column_config.NumberColumn(
                                format="%.1f%%"
                            ),
                            "Est. xP Proxy": st.column_config.NumberColumn(
                                format="%.2f pts"
                            ),
                            "Form": st.column_config.NumberColumn(
                                format="%.1f pts"
                            ),
                            "xGI": st.column_config.NumberColumn(
                                format="%.2f"
                            ),
                        },
                    )

                else:
                    st.warning(
                        "Your FPL Team ID was not found within this Mini-League's top standings."
                    )
            else:
                st.error("Invalid League ID.")

# ------------------------------------------------------------------------------
# TAB 3: AI SQUAD ADVISOR
# ------------------------------------------------------------------------------
with tab3:
    st.markdown("### 🤖 AI Squad Optimizer & Executive Transfer Advisor")

    col_ai_in1, col_ai_in2 = st.columns(2)
    with col_ai_in1:
        user_team_id = st.text_input(
            "Enter Your FPL Team ID:", value=MY_TEAM_ID, key="ai_my_id"
        )
    with col_ai_in2:
        advisor_league_id = st.text_input(
            "Mini-League ID for Context:",
            value=DEFAULT_LEAGUE_ID,
            key="ai_league_id",
        )

    if user_team_id:
        with st.spinner("Executing optimization algorithms and xP analysis..."):
            my_history = calculate_saved_fts_and_history(
                user_team_id, current_gw
            )
            my_picks = fetch_manager_picks(
                user_team_id, current_gw, player_dict
            )

            ml_ownership_map = {}
            if advisor_league_id:
                league_json = fetch_league_data(advisor_league_id)
                if league_json and "standings" in league_json:
                    standings = league_json["standings"]["results"]
                    total_mgrs = len(standings)
                    squad_counts = {}
                    for mgr in standings:
                        mgr_picks = fetch_manager_picks(
                            mgr["entry"], current_gw, player_dict
                        )
                        for pid in mgr_picks["Squad"]:
                            squad_counts[pid] = squad_counts.get(pid, 0) + 1
                    for pid, count in squad_counts.items():
                        ml_ownership_map[pid] = round(
                            (count / total_mgrs) * 100, 1
                        )

            squad_objs = [
                player_obj_dict[pid]
                for pid in my_picks["Squad"]
                if pid in player_obj_dict
            ]

            if squad_objs:
                df_squad = pd.DataFrame(squad_objs)
                df_squad["Form_Float"] = df_squad["form"].astype(float)
                df_squad["Cost_m"] = df_squad["now_cost"] / 10
                df_squad["Net_Transfers"] = (
                    df_squad["transfers_in_event"]
                    - df_squad["transfers_out_event"]
                )

                def compute_xp_and_price_risk(row):
                    team_id = row["team"]
                    f_info = next_fixtures_map.get(
                        team_id, {"fdr": 3, "opp": None, "is_home": True}
                    )
                    fdr = f_info["fdr"]
                    opp_name = teams.get(f_info["opp"], "TBD")
                    loc = "H" if f_info["is_home"] else "A"

                    xg_val = float(row.get("expected_goals", 0.0))
                    xa_val = float(row.get("expected_assists", 0.0))
                    xgi = xg_val + xa_val

                    pos_mult = 1.3 if row["element_type"] in [3, 4] else 0.9
                    xp = (
                        (row["Form_Float"] * 0.4)
                        + (xgi * 0.4)
                        + ((6 - fdr) * 0.6)
                    ) * pos_mult

                    net = row["Net_Transfers"]
                    status = (
                        "⚠️ Risk Drop"
                        if net < -30000
                        else ("🔥 Rising" if net > 30000 else "Stable")
                    )

                    return pd.Series(
                        [
                            round(xp, 2),
                            fdr,
                            f"{opp_name} ({loc})",
                            round(xgi, 2),
                            status,
                        ]
                    )

                df_squad[
                    ["xP", "FDR", "Next_Fixture", "xGI", "Price_Status"]
                ] = df_squad.apply(compute_xp_and_price_risk, axis=1)

                falling_squad = df_squad[
                    df_squad["Net_Transfers"] < -30000
                ].sort_values(by="Net_Transfers")
                if not falling_squad.empty:
                    sell_target = falling_squad.iloc[0]
                else:
                    sell_target = df_squad.sort_values(
                        by="xP", ascending=True
                    ).iloc[0]

                sorted_by_xp = df_squad.sort_values(by="xP", ascending=False)
                captain_target = sorted_by_xp.iloc[0]
                vc_target = sorted_by_xp.iloc[1]

                max_budget = sell_target["Cost_m"] + my_picks["Bank"]
                target_pos_id = int(sell_target["element_type"])
                target_pos_label = POSITION_MAP.get(target_pos_id, "DEF")

                market_targets = [
                    p
                    for p in elements
                    if int(p["element_type"]) == target_pos_id
                    and (p["now_cost"] / 10) <= max_budget
                    and p["id"] not in my_picks["Squad"]
                    and p["status"] == "a"
                ]

                if market_targets:
                    df_market = pd.DataFrame(market_targets)
                    df_market["Form_Float"] = df_market["form"].astype(float)
                    df_market["Net_Transfers"] = (
                        df_market["transfers_in_event"]
                        - df_market["transfers_out_event"]
                    )
                    df_market[
                        ["xP", "FDR", "Next_Fixture", "xGI", "Price_Status"]
                    ] = df_market.apply(compute_xp_and_price_risk, axis=1)
                    df_market["Target_Score"] = df_market["xP"] + (
                        df_market["Net_Transfers"] / 50000
                    )
                    buy_target = df_market.sort_values(
                        by="Target_Score", ascending=False
                    ).iloc[0]

                    (
                        buy_name,
                        buy_cost,
                        buy_xp,
                        buy_status,
                    ) = (
                        buy_target["web_name"],
                        buy_target["now_cost"] / 10,
                        buy_target["xP"],
                        buy_target["Price_Status"],
                    )
                    buy_pos_label = POSITION_MAP.get(
                        int(buy_target["element_type"]), target_pos_label
                    )
                else:
                    buy_name, buy_cost, buy_xp, buy_status = (
                        "No option",
                        0.0,
                        0.0,
                        "Stable",
                    )
                    buy_pos_label = target_pos_label

                # Positional Target Tables
                st.markdown("#### 🔥 Market Hotspots (Best Buy Targets)")
                st.caption(
                    "High Expected Points (xP) and positive transfer momentum. Excludes current squad."
                )

                unowned_elements = [
                    p
                    for p in elements
                    if p["id"] not in my_picks["Squad"] and p["status"] == "a"
                ]
                df_unowned = pd.DataFrame(unowned_elements)
                df_unowned["Form_Float"] = df_unowned["form"].astype(float)
                df_unowned["Cost_m"] = df_unowned["now_cost"] / 10
                df_unowned["Net_Transfers"] = (
                    df_unowned["transfers_in_event"]
                    - df_unowned["transfers_out_event"]
                )
                df_unowned[
                    ["xP", "FDR", "Next_Fixture", "xGI", "Price_Status"]
                ] = df_unowned.apply(compute_xp_and_price_risk, axis=1)
                df_unowned["Hybrid_Score"] = (df_unowned["xP"] * 0.6) + (
                    (df_unowned["Net_Transfers"] / 20000) * 0.4
                )

                col_def, col_mid, col_fwd = st.columns(3)

                def render_position_table(pos_id, title, icon, container):
                    pos_df = (
                        df_unowned[df_unowned["element_type"] == pos_id]
                        .sort_values(by="Hybrid_Score", ascending=False)
                        .head(3)
                        .copy()
                    )
                    pos_df_display = pos_df[
                        ["web_name", "Cost_m", "Price_Status", "Next_Fixture", "xP"]
                    ].copy()
                    pos_df_display.columns = [
                        "Name",
                        "Price",
                        "Status",
                        "Vs",
                        "xP",
                    ]

                    with container:
                        st.markdown(f"##### {icon} {title}")
                        st.dataframe(
                            pos_df_display,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Price": st.column_config.NumberColumn(
                                    format="£%.1fm"
                                ),
                                "xP": st.column_config.NumberColumn(
                                    format="%.2f"
                                ),
                            },
                        )

                render_position_table(2, "Top Defenders", "🛡️", col_def)
                render_position_table(3, "Top Midfielders", "🎯", col_mid)
                render_position_table(4, "Top Forwards", "⚡", col_fwd)

                st.markdown("---")

                # Executive Alerts
                if not falling_squad.empty:
                    st.markdown(
                        f"""
                        <div class="rec-card rec-card-danger">
                            <strong style="color: #dc2626;">🚨 Urgent Price Risk Alert:</strong> 
                            <strong>{sell_target['web_name']}</strong> has heavy net sales (<strong>{sell_target['Net_Transfers']:,} transfers out</strong>). 
                            Execute transfer early to preserve squad value.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric(
                        "💡 Recommended Strategy",
                        "HOLD CHIPS"
                        if current_gw <= 3
                        else "WILDCARD READY",
                    )
                    st.caption(
                        f"Banked Transfers: **{my_history['Saved FTs']} FT** | In Bank: **£{my_picks['Bank']:.1f}m**"
                    )

                with col_b:
                    st.metric(
                        "👑 Priority Captain",
                        f"{captain_target['web_name']} ({captain_target['xP']} xP)",
                    )
                    st.caption(
                        f"Fixture: **{captain_target['Next_Fixture']}** | Vice: **{vc_target['web_name']}**"
                    )

                with col_c:
                    st.metric(
                        "🔁 Tactical Transfer Call",
                        f"OUT: {sell_target['web_name']} ({target_pos_label})",
                    )
                    st.caption(
                        f"IN: **{buy_name}** ({buy_pos_label} | £{buy_cost:.1f}m | {buy_xp} xP)"
                    )

                st.markdown("---")

                st.markdown("#### 📋 Squad Performance & Risk Audit")

                df_squad["Pos"] = df_squad["element_type"].map(POSITION_MAP)
                df_squad["Global_Own_Str"] = (
                    df_squad["selected_by_percent"]
                    .astype(float)
                    .map(lambda v: f"{v:.1f}%")
                )
                df_squad["ML_Own_Str"] = df_squad["id"].map(
                    lambda pid: f"{ml_ownership_map.get(pid, 0.0):.1f}%"
                )

                display_cols = [
                    "web_name",
                    "Pos",
                    "Cost_m",
                    "xP",
                    "Price_Status",
                    "Net_Transfers",
                    "Next_Fixture",
                    "FDR",
                    "xGI",
                    "Form_Float",
                    "total_points",
                    "Global_Own_Str",
                    "ML_Own_Str",
                ]
                df_squad_display = df_squad[display_cols].copy()
                df_squad_display.columns = [
                    "Name",
                    "Position",
                    "Cost (£m)",
                    "Expected Pts (xP)",
                    "Price Status",
                    "Net Transfers",
                    "Next Fixture",
                    "FDR",
                    "xGI (xG+xA)",
                    "Form",
                    "Total Pts",
                    "Global Own %",
                    "Mini-League Own %",
                ]

                table_height = (len(df_squad_display) + 1) * 35 + 5

                st.dataframe(
                    df_squad_display.sort_values(
                        by="Expected Pts (xP)", ascending=False
                    ),
                    use_container_width=True,
                    hide_index=True,
                    height=table_height,
                    column_config={
                        "Cost (£m)": st.column_config.NumberColumn(
                            format="£%.1fm"
                        ),
                        "Expected Pts (xP)": st.column_config.NumberColumn(
                            format="%.2f pts"
                        ),
                        "Net Transfers": st.column_config.NumberColumn(
                            format="%+d"
                        ),
                        "FDR": st.column_config.NumberColumn(
                            format="Rating: %d"
                        ),
                        "xGI (xG+xA)": st.column_config.NumberColumn(
                            format="%.2f"
                        ),
                        "Form": st.column_config.NumberColumn(
                            format="%.1f pts"
                        ),
                    },
                )