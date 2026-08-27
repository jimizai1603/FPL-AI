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
DEFAULT_LEAGUE_ID = "1304670"
MY_TEAM_ID = "4224092"

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
ALL_CHIPS = ["WILDCARD", "FREEHIT", "BBOOST", "3XC"]


@st.cache_data(ttl=300)
def fetch_fpl_data():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    res = requests.get(url)
    return res.json()


@st.cache_data(ttl=300)
def fetch_fixtures_data():
    url = "https://fantasy.premierleague.com/api/fixtures/"
    res = requests.get(url)
    return res.json()


def fetch_league_data(league_id):
    """Fetches ALL managers in a classic mini-league across all API pages."""
    all_results = []
    page = 1
    league_name = "Mini-League"

    while True:
        url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/?page_standings={page}"
        res = requests.get(url)
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
    res = requests.get(hist_url)
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
    res = requests.get(picks_url)
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
        gw_change = p.get("cost_change_event", 0) / 10

        effective_net = net - (gw_change * 10 * 50000)
        abs_eff_net = abs(effective_net)

        if gw_change > 0:
            status = f"✅ Rose GW{current_gw} (+£{gw_change:.1f}m)"
        elif gw_change < 0:
            status = f"❌ Dropped GW{current_gw} (-£{abs(gw_change):.1f}m)"
        elif abs_eff_net >= 40000:
            status = "🔥 Tonight"
        elif abs_eff_net > 0:
            days_est = math.ceil((40000 - abs_eff_net) / abs_eff_net)
            status = "1 day" if days_est <= 1 else f"~{days_est} days"
        else:
            status = "No momentum"

        tracker.append(
            {
                "Name": p["web_name"],
                "Pos": POSITION_MAP.get(p["element_type"], "UNK"),
                "Cost (£m)": p["now_cost"] / 10,
                "GW Change Raw": gw_change,
                "GW Change": f"+£{gw_change:.1f}m" if gw_change > 0 else (f"-£{abs(gw_change):.1f}m" if gw_change < 0 else "£0.0m"),
                "Net Transfers": net,
                "Est. Price Change": status,
            }
        )

    df_tracker = pd.DataFrame(tracker)

    df_risers = df_tracker.sort_values(
        by=["GW Change Raw", "Net Transfers"], ascending=[False, False]
    ).head(top_n)

    df_fallers = df_tracker.sort_values(
        by=["GW Change Raw", "Net Transfers"], ascending=[True, True]
    ).head(top_n)

    column_order = [
        "Name",
        "Pos",
        "Cost (£m)",
        "GW Change",
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
# TAB 3: AI SQUAD ADVISOR (WITH GKP SUPPORT & CROSS-TAB MARKET MOMENTUM)
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

            # --- SQUAD OVERVIEW METRICS ---
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💼 Bank Remaining", f"£{my_picks['Bank']:.1f}m")
            m2.metric("🔄 Saved Transfers", f"{my_history['Saved FTs']} FT")
            m3.metric("📉 Active Hits Cost", f"-{my_history['Hits Cost']} pts")
            m4.metric("🛡️ Available Chips", my_history["Chips Remaining"])

            st.markdown("---")

            # ------------------------------------------------------------------
            # 🔥 MARKET HOTSPOTS: LINKED WITH TAB 1 MARKET DATA
            # ------------------------------------------------------------------
            st.markdown("### 🔥 Market Hotspots (Best Buy Targets)")
            st.caption(
                "High Expected Points (xP) assets cross-referenced with Tab 1 real-time market price momentum."
            )

            # Controls: Toggle to hide/show owned players & Display Slider
            col_ctrl1, col_ctrl2 = st.columns([1, 2])
            with col_ctrl1:
                hide_owned = st.toggle("👁️ Hide Owned Players", value=True, key="hs_hide_owned")
            with col_ctrl2:
                num_rows = st.slider(
                    "🎚️ Display Row Limit (per position):",
                    min_value=3,
                    max_value=7,
                    value=5,
                    key="hs_rows",
                )

            # Build player set conditionally based on toggle state
            my_squad_ids = set(my_picks["Squad"]) if hide_owned else set()

            # Build comprehensive player pool linked with Tab 1 data
            market_hotspots = []
            for p in elements:
                if p["id"] in my_squad_ids:
                    continue

                form_val = float(p.get("form", 0.0))
                xg_val = float(p.get("expected_goals", 0.0))
                xa_val = float(p.get("expected_assists", 0.0))
                xgi_val = xg_val + xa_val
                xp_proxy = round((form_val * 0.5) + (xgi_val * 0.5), 2)

                f_info = next_fixtures_map.get(p["team"], {})
                opp_name = teams.get(f_info.get("opp"), "UNK") if f_info else "N/A"
                loc = "(H)" if f_info.get("is_home") else "(A)"
                vs_str = f"{opp_name} {loc}"

                net = p["transfers_in_event"] - p["transfers_out_event"]
                gw_change = p.get("cost_change_event", 0) / 10
                effective_net = net - (gw_change * 10 * 50000)

                if gw_change > 0:
                    status = "✅ Rose"
                elif abs(effective_net) >= 40000:
                    status = "🔥 Rising Tonight"
                elif net > 10000:
                    status = "📈 Demand"
                else:
                    status = "⚪ Stable"

                market_hotspots.append(
                    {
                        "ID": p["id"],
                        "Name": p["web_name"],
                        "Pos_ID": p["element_type"],
                        "Pos": POSITION_MAP.get(p["element_type"], "UNK"),
                        "Price": f"£{p['now_cost'] / 10:.1f}m",
                        "Cost_Raw": p["now_cost"] / 10,
                        "Status": status,
                        "Vs": vs_str,
                        "xP": xp_proxy,
                        "Net_Transfers": net,
                    }
                )

            df_hotspots = pd.DataFrame(market_hotspots)

            # 4 Columns Grid (GKP, DEF, MID, FWD)
            col_gkp, col_def, col_mid, col_fwd = st.columns(4)

            pos_cols = [
                (col_gkp, 1, "🧤 Top Goalkeepers"),
                (col_def, 2, "🛡️ Top Defenders"),
                (col_mid, 3, "🎯 Top Midfielders"),
                (col_fwd, 4, "⚡ Top Forwards"),
            ]

            display_fields = ["Name", "Price", "Status", "Vs", "xP"]

            for col_obj, pos_code, title in pos_cols:
                with col_obj:
                    st.markdown(f"#### {title}")
                    sub_df = (
                        df_hotspots[df_hotspots["Pos_ID"] == pos_code]
                        .sort_values(
                            by=["xP", "Net_Transfers"], ascending=[False, False]
                        )
                        .head(num_rows)[display_fields]
                    )

                    calc_height = (len(sub_df) + 1) * 35 + 5
                    st.dataframe(
                        sub_df,
                        use_container_width=True,
                        hide_index=True,
                        height=calc_height,
                        column_config={
                            "xP": st.column_config.NumberColumn(format="%.2f"),
                        },
                    )

            st.markdown("---")

            # ------------------------------------------------------------------
            # CURRENT SQUAD METRICS TABLE & RECOMMENDATIONS
            # ------------------------------------------------------------------
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
                    form_val = float(row.get("form", 0.0))
                    xg_val = float(row.get("expected_goals", 0.0))
                    xa_val = float(row.get("expected_assists", 0.0))
                    xgi_val = xg_val + xa_val
                    xp_proxy = round((form_val * 0.5) + (xgi_val * 0.5), 2)

                    net_transfers = row["Net_Transfers"]
                    if net_transfers <= -50000:
                        price_risk = "🚨 Heavy Drop Risk"
                    elif net_transfers <= -20000:
                        price_risk = "⚠️ Moderate Risk"
                    elif net_transfers >= 50000:
                        price_risk = "🔥 High Rise Potential"
                    else:
                        price_risk = "⚪ Stable"

                    return pd.Series(
                        [xp_proxy, price_risk], index=["xP_Proxy", "Price_Risk"]
                    )

                df_squad[["xP_Proxy", "Price_Risk"]] = df_squad.apply(
                    compute_xp_and_price_risk, axis=1
                )

                def get_fixture_info(row):
                    t_id = row["team"]
                    f_info = next_fixtures_map.get(t_id, {})
                    if not f_info:
                        return "N/A", "N/A", 3
                    opp_name = teams.get(f_info["opp"], "UNK")
                    loc = "(H)" if f_info["is_home"] else "(A)"
                    return f"{opp_name} {loc}", f_info["fdr"], f_info["fdr"]

                fixture_data = df_squad.apply(get_fixture_info, axis=1)
                df_squad["Next_Fixture"] = [f[0] for f in fixture_data]
                df_squad["FDR"] = [f[1] for f in fixture_data]
                df_squad["ML_Ownership"] = df_squad["id"].map(
                    lambda x: f"{ml_ownership_map.get(x, 0.0):.1f}%"
                )

                # Price Risk Alert Banner
                high_risk_players = df_squad[df_squad["Net_Transfers"] <= -50000]
                if not high_risk_players.empty:
                    for _, hr_p in high_risk_players.iterrows():
                        st.markdown(
                            f"""
                            <div class="rec-card rec-card-danger">
                                🚨 <strong>Urgent Price Risk Alert:</strong> <strong>{hr_p['web_name']}</strong> 
                                has heavy net sales (<code>{hr_p['Net_Transfers']:,} transfers out</code>). 
                                Execute transfer early to preserve squad value.
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                # Current Squad Table
                st.markdown("#### 📋 Current Squad Analytical Breakdown")
                display_cols = [
                    "web_name",
                    "element_type",
                    "Cost_m",
                    "Form_Float",
                    "xP_Proxy",
                    "Next_Fixture",
                    "FDR",
                    "ML_Ownership",
                    "Price_Risk",
                ]

                df_squad_display = df_squad[display_cols].copy()
                df_squad_display["element_type"] = df_squad_display[
                    "element_type"
                ].map(POSITION_MAP)
                df_squad_display.rename(
                    columns={
                        "web_name": "Player",
                        "element_type": "Pos",
                        "Cost_m": "Cost (£m)",
                        "Form_Float": "Form",
                        "xP_Proxy": "Est. xP",
                        "Next_Fixture": "Next Match",
                        "ML_Ownership": "ML Ownership",
                        "Price_Risk": "Market Risk",
                    },
                    inplace=True,
                )

                st.dataframe(
                    df_squad_display.sort_values(by="Est. xP", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Cost (£m)": st.column_config.NumberColumn(format="£%.1fm"),
                        "Form": st.column_config.NumberColumn(format="%.1f pts"),
                        "Est. xP": st.column_config.NumberColumn(format="%.2f pts"),
                        "FDR": st.column_config.NumberColumn(format="Difficulty: %d"),
                    },
                )

                st.markdown("---")

                # Strategic Recommendations
                st.markdown("#### 💡 Strategic Transfer Recommendations")
                sell_candidates = df_squad[
                    (df_squad["Form_Float"] < 3.0)
                    | (df_squad["Net_Transfers"] < -30000)
                ]

                if not sell_candidates.empty:
                    for _, sell_p in sell_candidates.iterrows():
                        pos_id = sell_p["element_type"]
                        max_budget = sell_p["Cost_m"] + my_picks["Bank"]

                        replacements = [
                            p
                            for p in market_hotspots
                            if p["Pos_ID"] == pos_id
                            and p["Cost_Raw"] <= max_budget
                        ]
                        replacements = sorted(
                            replacements, key=lambda x: x["xP"], reverse=True
                        )

                        if replacements:
                            top_target = replacements[0]
                            st.markdown(
                                f"""
                                <div class="rec-card">
                                    <strong>🔄 Suggested Transfer Call:</strong><br/>
                                    <strong>OUT:</strong> {sell_p['web_name']} ({POSITION_MAP.get(pos_id)}) — Form: <code>{sell_p['Form_Float']}</code> | Price: <code>£{sell_p['Cost_m']:.1f}m</code><br/>
                                    <strong>IN:</strong> {top_target['Name']} ({top_target['Pos']}) — Est. xP: <code>{top_target['xP']}</code> | Market Status: <code>{top_target['Status']}</code> | Price: <code>{top_target['Price']}</code>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                else:
                    st.markdown(
                        """
                        <div class="rec-card">
                            <strong>✅ Squad Stable:</strong> No immediate high-priority forced transfers detected. 
                            Consider rolling your Free Transfer for maximum flexibility next Gameweek.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
