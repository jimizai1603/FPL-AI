import datetime
import math
import re
import pandas as pd
import requests
import streamlit as st

try:
    import bs4
except ImportError:
    bs4 = None

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
# UNIVERSAL LIGHT THEME UI/UX ENGINE & TRANSFER BADGE STYLES
# ------------------------------------------------------------------------------
st.markdown(
    """
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f8fafc !important;
        color: #0f172a !important;
    }
    h1, h2, h3, h4, h5, h6, label, div[data-testid="stMetricLabel"] p, .stCaption p, div[data-testid="stMarkdownContainer"] p {
        color: #0f172a !important;
        font-weight: 700 !important;
        opacity: 1 !important;
    }
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
    div[data-testid="stMetricValue"] {
        color: #0284c7 !important;
        font-weight: 800 !important;
        font-size: 2.2rem !important;
    }
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
    .rec-card-chip {
        background: #f0fdf4;
        border-color: #86efac;
        border-left-color: #16a34a;
        color: #14532d;
    }
    .badge-in {
        background-color: #dcfce7;
        color: #166534;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.88rem;
        display: inline-block;
        margin: 2px 0;
    }
    .badge-out {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.88rem;
        display: inline-block;
        margin: 2px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="executive-header">
        <h1>⚽ FPL AI DASHBORD</h1>
        <span class="header-subtitle">Advanced Real-Time Market Analytics, Rival Mini-League Spy & Performance AI</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------
# GLOBAL CONSTANTS & API HELPERS
# ------------------------------------------------------------------------------
DEFAULT_LEAGUE_ID = ""
MY_TEAM_ID = ""

POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
ALL_CHIPS = ["WILDCARD", "FREEHIT", "BBOOST", "3XC"]


@st.cache_data(ttl=3600)
def fetch_fpl_setpiece_map():
    url = "https://fantasy.premierleague.com/en/the-scout/set-piece-takers"
    headers = {"User-Agent": "Mozilla/5.0"}
    setpiece_db = {}

    if bs4 is None:
        return setpiece_db

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            lines = [
                line.strip()
                for line in soup.get_text().split("\n")
                if line.strip()
            ]
            current_duty = None

            for line in lines:
                if "Penalties" in line:
                    current_duty = "pen"
                elif "Direct free-kicks" in line:
                    current_duty = "fk"
                elif "Corners" in line:
                    current_duty = "corner"
                elif "Notes" in line or "Check back" in line:
                    current_duty = None
                elif current_duty:
                    clean_line = re.sub(r"[^\w\s]", "", line).lower()
                    words = [w for w in clean_line.split() if len(w) > 1]

                    if words:
                        surname = words[-1]
                        if surname not in setpiece_db:
                            setpiece_db[surname] = {
                                "pen": 99,
                                "fk": 99,
                                "corner": 99,
                            }
                        setpiece_db[surname][current_duty] = 1
    except Exception as e:
        st.warning(f"Live set-piece fetch note: {e}")

    return setpiece_db


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

            if h_team not in next_fixtures:
                next_fixtures[h_team] = []
            if a_team not in next_fixtures:
                next_fixtures[a_team] = []

            next_fixtures[h_team].append(
                {"opp": a_team, "fdr": f["team_h_difficulty"], "is_home": True}
            )
            next_fixtures[a_team].append(
                {"opp": h_team, "fdr": f["team_a_difficulty"], "is_home": False}
            )
    return next_fixtures


def calculate_saved_fts_and_history(entry_id, target_gw):
    hist_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
    res_hist = requests.get(hist_url)

    if res_hist.status_code != 200:
        return {
            "Chips Used": "-",
            "Chips Remaining": ", ".join(ALL_CHIPS),
            "Hits Cost": 0,
            "Saved FTs": 1,
        }

    data = res_hist.json()

    chips_played = data.get("chips", [])
    used_chips_raw = [c["name"].upper() for c in chips_played]
    remaining_chips = [c for c in ALL_CHIPS if c not in used_chips_raw]
    chips_rem_str = ", ".join(remaining_chips) if remaining_chips else "All Used"

    chip_gw_map = {c["event"]: c["name"].lower() for c in chips_played}

    current_history = data.get("current", [])
    history_up_to_gw = [
        gw for gw in current_history if gw.get("event", 0) <= target_gw
    ]
    total_hits = sum(
        gw.get("event_transfers_cost", 0) for gw in history_up_to_gw
    )

    fts_available = 1

    for gw_info in history_up_to_gw:
        event_id = gw_info.get("event", 0)
        raw_transfers = gw_info.get("event_transfers", 0)
        active_chip = chip_gw_map.get(event_id, "")

        if active_chip in ["wildcard", "freehit"]:
            transfers_made = 0
        else:
            transfers_made = raw_transfers

        fts_remaining = max(0, fts_available - transfers_made)

        if event_id < target_gw:
            fts_available = min(5, fts_remaining + 1)
        else:
            fts_available = fts_remaining

    return {
        "Chips Remaining": chips_rem_str,
        "Hits Cost": total_hits,
        "Saved FTs": fts_available,
    }


def fetch_gw_transfers(entry_id, target_gw, player_dict):
    t_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/transfers/"
    res = requests.get(t_url)

    if res.status_code != 200:
        return "-", "-"

    transfers = res.json()
    gw_transfers = [t for t in transfers if t.get("event") == target_gw]

    if not gw_transfers:
        return "-", "-"

    ins = []
    outs = []
    for t in gw_transfers:
        p_in = player_dict.get(t.get("element_in"), "Unknown")
        p_out = player_dict.get(t.get("element_out"), "Unknown")
        ins.append(f'<span class="badge-in">⬆️ {p_in}</span>')
        outs.append(f'<span class="badge-out">⬇️ {p_out}</span>')

    return "<br>".join(ins), "<br>".join(outs)


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
            "Bench": [],
            "GW_Pts": 0,
            "GW_Rank": "-",
            "Active_Chip": "-",
        }
    p_data = res.json()

    entry_hist = p_data.get("entry_history", {})
    bank = entry_hist.get("bank", 0) / 10
    bench_pts = entry_hist.get("points_on_bench", 0)
    gw_pts = entry_hist.get("points", 0)
    gw_rank = entry_hist.get("rank", "-")

    active_chip_raw = p_data.get("active_chip")
    active_chip = active_chip_raw.upper() if active_chip_raw else "-"

    captain, vc, cap_id = "Unknown", "Unknown", None
    squad_ids, starting_ids, bench_ids = [], [], []

    for pick in p_data.get("picks", []):
        pid = pick["element"]
        squad_ids.append(pid)
        if pick.get("position", 12) <= 11:
            starting_ids.append(pid)
        else:
            bench_ids.append(pid)
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
        "Bench": bench_ids,
        "GW_Pts": gw_pts,
        "GW_Rank": gw_rank,
        "Active_Chip": active_chip,
    }


# Load Core Datasets
data = fetch_fpl_data()
fixtures = fetch_fixtures_data()
setpiece_db = fetch_fpl_setpiece_map()

elements = data["elements"]
teams = {t["id"]: t["name"] for t in data["teams"]}
team_conceded_map = {t["id"]: t.get("strength_defence_home", 1200) for t in data["teams"]}
events = data["events"]
current_gw = get_current_gw(events)
next_gw = current_gw + 1

next_fixtures_map = get_next_gw_fixtures(fixtures, next_gw)
player_dict = {p["id"]: p["web_name"] for p in elements}
player_obj_dict = {p["id"]: p for p in elements}


# ------------------------------------------------------------------------------
# CORE XP ROUTER
# ------------------------------------------------------------------------------
def compute_player_xp(p_obj):
    pos_type = p_obj.get("element_type", 3)
    form_val = float(p_obj.get("form", 0.0))
    xg_val = float(p_obj.get("expected_goals", 0.0))
    xa_val = float(p_obj.get("expected_assists", 0.0))
    xgi_val = xg_val + xa_val

    t_id = p_obj.get("team")
    f_list = next_fixtures_map.get(t_id, [])
    fdr = f_list[0]["fdr"] if f_list else 3

    if pos_type in [1, 2]:
        fdr_cs_map = {1: 0.50, 2: 0.40, 3: 0.25, 4: 0.15, 5: 0.05}
        base_cs_prob = fdr_cs_map.get(fdr, 0.25)

        def_strength = team_conceded_map.get(t_id, 1100)
        if def_strength >= 1250:
            defcon_mult = 1.25
        elif def_strength >= 1050:
            defcon_mult = 1.00
        else:
            defcon_mult = 0.75

        cs_xp = (base_cs_prob * 4.0) * defcon_mult

        if pos_type == 1:
            saves_val = float(p_obj.get("saves", 0))
            mins_val = float(p_obj.get("minutes", 1))
            saves_per_90 = (saves_val / max(1.0, mins_val)) * 90.0
            save_xp = min(2.0, saves_per_90 * 0.33)
            return round(cs_xp + save_xp + 2.0 + (form_val * 0.05), 2)
        else:
            attacking_xp = xgi_val * 0.60
            return round(cs_xp + attacking_xp + 2.0 + (form_val * 0.05), 2)
    else:
        return round((form_val * 0.10) + (xgi_val * 0.75) + 2.0, 2)


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
        st.markdown(
    '<a href="https://fantasy.premierleague.com/en/price-changes" target="_blank" style="color: #0f172a; font-weight: 800; font-size: 0.9rem; text-decoration: underline;">View ACTUAL FPL Price Changes HERE</a>',
    unsafe_allow_html=True,
            
)
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
                "GW Change": f"+£{gw_change:.1f}m"
                if gw_change > 0
                else (f"-£{abs(gw_change):.1f}m" if gw_change < 0 else "£0.0m"),
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

    c1, c2 = st.columns(2)
    table_h = min((top_n + 1) * 35 + 5, 800)

    with c1:
        st.markdown("### 📈 Rising Assets (Buy Pressure)")
        st.dataframe(
            df_risers[column_order],
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
            df_fallers[column_order],
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
                    transfers_in_html, transfers_out_html = fetch_gw_transfers(
                        mgr["entry"], selected_gw, player_dict
                    )

                    prev_total = mgr["total"] - picks["GW_Pts"]
                    manager_data.append(
                        {
                            "mgr": mgr,
                            "picks": picks,
                            "hist": hist,
                            "transfers_in": transfers_in_html,
                            "transfers_out": transfers_out_html,
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

                leader_pts = (
                    manager_data[0]["mgr"]["total"] if manager_data else 0
                )
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
                    pts_str = (
                        "Leader" if pts_off_lead == 0 else f"{pts_off_lead} pts"
                    )

                    rivals.append(
                        {
                            "Rank": f"{curr_rank} {trend}",
                            "Manager": mgr["player_name"],
                            "Team": mgr["entry_name"],
                            "GW Pts": picks["GW_Pts"],
                            "Total Pts": mgr["total"],
                            "Saved FTs": f"{hist['Saved FTs']} FT",
                            "Bank": f"£{picks['Bank']:.1f}m",
                            "Captain (VC)": f"{picks['Captain']} ({picks['VC']})",

                            "Differentials": ", ".join(diff_names)
                            if diff_names
                            else "Identical Squad",
                            "Transfers In": item["transfers_in"],
                            "Transfers Out": item["transfers_out"],
                            "Bench Pts": picks["Bench Pts"],
                            "GW Chip Used": picks["Active_Chip"],
                            "Chips Remaining": hist["Chips Remaining"],
                            "Hits": f"-{hist['Hits Cost']} pts",
                        }
                    )

                df_rivals = pd.DataFrame(rivals)
                
                # Render using HTML to retain colored transfer badges
                st.write(
                    df_rivals.to_html(escape=False, index=False),
                    unsafe_allow_html=True,
                )

                st.markdown("---")

                # Tactical Matrix
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
                                "Owned by You": "✅ Yes"
                                if is_owned
                                else "❌ No",
                                "Target Group Starting %": f"{start_pct:.1f}%",
                                "Target Group Cap %": f"{cap_pct:.1f}%",
                                "Target Group EO %": round(eo_val, 1),
                                "Tactical Role": tactic_type,
                            }
                        )

                        p_obj = player_obj_dict.get(pid, {})
                        xp_val = compute_player_xp(p_obj)
                        form_val = float(p_obj.get("form", 0.0))
                        xgi_val = float(p_obj.get("expected_goals", 0.0)) + float(p_obj.get("expected_assists", 0.0))

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
                        "Combines target rival ownership with Form & Positional Expected Metrics to isolate actual high-priority threats."
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
        advisor_league_id = st.text_input(
            "FPL Mini-League ID:",
            value=DEFAULT_LEAGUE_ID,
            key="ai_league_id"
        )
    with col_ai_in2:
        user_team_id = st.text_input(
            "Your FPL Team ID:", value=MY_TEAM_ID, key="ai_my_id"
        )

    if user_team_id:
        with st.spinner(
            "Executing optimization algorithms and xP analysis..."
        ):
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

            # Squad Overview Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💼 Bank Remaining", f"£{my_picks['Bank']:.1f}m")
            m2.metric("🔄 Saved Transfers", f"{my_history['Saved FTs']} FT")
            m3.metric("📉 Active Hits Cost", f"-{my_history['Hits Cost']} pts")
            m4.metric("🛡️ Available Chips", my_history["Chips Remaining"])

            st.markdown("---")

            # Market Hotspots
            st.markdown("### 🔥 Market Hotspots (Best Buy Targets)")
            st.caption(
                "High Expected Points (xP) assets cross-referenced with Tab 1 real-time market price momentum."
            )

            col_ctrl1, col_ctrl2 = st.columns([1, 2])
            with col_ctrl1:
                hide_owned = st.toggle(
                    "👁️ Hide Owned Players", value=True, key="hs_hide_owned"
                )
            with col_ctrl2:
                num_rows = st.slider(
                    "🎚️ Display Row Limit (per position):",
                    min_value=3,
                    max_value=7,
                    value=5,
                    key="hs_rows",
                )

            my_squad_ids = set(my_picks["Squad"]) if hide_owned else set()

            market_hotspots = []
            for p in elements:
                if p["id"] in my_squad_ids:
                    continue

                xp_proxy = compute_player_xp(p)

                f_list = next_fixtures_map.get(p["team"], [])
                if f_list:
                    vs_strings = [
                        f"{teams.get(f['opp'], 'UNK')} {'(H)' if f['is_home'] else '(A)'}"
                        for f in f_list
                    ]
                    vs_str = " + ".join(vs_strings)
                else:
                    vs_str = "BLANK"

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
                        "Team_ID": p["team"],
                        "Team": teams.get(p["team"], "UNK"),
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
                            by=["xP", "Net_Transfers"],
                            ascending=[False, False],
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

            # Current Squad Table
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
                    xp_proxy = compute_player_xp(row.to_dict())
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
                        [xp_proxy, price_risk],
                        index=["xP_Proxy", "Price_Risk"],
                    )

                df_squad[["xP_Proxy", "Price_Risk"]] = df_squad.apply(
                    compute_xp_and_price_risk, axis=1
                )

                def get_fixture_info(row):
                    t_id = row["team"]
                    f_list = next_fixtures_map.get(t_id, [])
                    if not f_list:
                        return "BLANK", 5
                    vs_str = " + ".join(
                        [
                            f"{teams.get(f['opp'], 'UNK')} {'(H)' if f['is_home'] else '(A)'}"
                            for f in f_list
                        ]
                    )
                    avg_fdr = sum(f["fdr"] for f in f_list) / len(f_list)
                    return vs_str, avg_fdr

                fixture_data = df_squad.apply(get_fixture_info, axis=1)
                df_squad["Next_Fixture"] = [f[0] for f in fixture_data]
                df_squad["FDR"] = [f[1] for f in fixture_data]
                df_squad["ML_Ownership"] = df_squad["id"].map(
                    lambda x: f"{ml_ownership_map.get(x, 0.0):.1f}%"
                )

                # Price Risk Alert Banner
                high_risk_players = df_squad[
                    df_squad["Net_Transfers"] <= -50000
                ]
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
                    df_squad_display.sort_values(
                        by="Est. xP", ascending=False
                    ),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Cost (£m)": st.column_config.NumberColumn(
                            format="£%.1fm"
                        ),
                        "Form": st.column_config.NumberColumn(
                            format="%.1f pts"
                        ),
                        "Est. xP": st.column_config.NumberColumn(
                            format="%.2f pts"
                        ),
                        "FDR": st.column_config.NumberColumn(
                            format="Difficulty: %.1f"
                        ),
                    },
                )

                # --------------------------------------------------------------
                # CAPTAINCY ENGINE & INTUITION LOGIC
                # --------------------------------------------------------------
                st.markdown("---")
                st.markdown("### 👑 AI Captaincy Advice & Manager's Eye Engine")

                col_opt1, col_opt2 = st.columns([1, 2])
                with col_opt1:
                    enable_intuition = st.toggle(
                        "🧠 Enable 'Manager's Eye' Intuition Logic", value=True
                    )
                with col_opt2:
                    st.caption(
                        "Overrules short-term form spikes with set-piece dominance, home track records, DGW multipliers, and target fixtures."
                    )

                def calculate_captain_score(row):
                    form_val = float(row.get("form", 0.0))
                    xg_val = float(row.get("expected_goals", 0.0))
                    xa_val = float(row.get("expected_assists", 0.0))
                    xgi_val = xg_val + xa_val
                    cost_m = float(row.get("now_cost", 0)) / 10.0

                    player_name = str(row.get("web_name", "")).lower()
                    clean_pname = re.sub(r"[^\w\s]", "", player_name)

                    has_setpiece_duty = False
                    for surname, role_ranks in setpiece_db.items():
                        if surname in clean_pname or clean_pname in surname:
                            if role_ranks.get("pen") in [1, 2] or role_ranks.get("fk") in [1, 2]:
                                has_setpiece_duty = True
                                break

                    KEY_SET_PIECE_PLAYERS = [
                        "fernandes", "bruno", "saka", "palmer", "haaland", "salah"
                    ]
                    if any(k in clean_pname for k in KEY_SET_PIECE_PLAYERS):
                        has_setpiece_duty = True

                    quality_floor = max(0.0, (cost_m - 5.0) * 0.35)
                    set_piece_bonus = 0.80 if has_setpiece_duty else 0.0

                    base_xp = (form_val * 0.10) + (xgi_val * 0.75) + quality_floor + set_piece_bonus

                    t_id = row["team"]
                    f_list = next_fixtures_map.get(t_id, [])

                    if not f_list:
                        return pd.Series(
                            [0.0, 0.0, "Blank Gameweek"],
                            index=["AI_Score", "Intuition_Score", "Drivers"],
                        )

                    is_dgw = len(f_list) > 1
                    fdr_weights = {1: 1.35, 2: 1.18, 3: 1.00, 4: 0.82, 5: 0.65}

                    total_fixture_mult = 0
                    has_home_game = False
                    has_target_fixture = False

                    for f in f_list:
                        fdr = f["fdr"]
                        f_mult = fdr_weights.get(fdr, 1.00)
                        if f["is_home"]:
                            f_mult *= 1.10
                            has_home_game = True
                        else:
                            f_mult *= 0.95

                        if fdr <= 2:
                            has_target_fixture = True

                        total_fixture_mult += f_mult

                    ai_score = round(base_xp * total_fixture_mult, 2)

                    intuition_boost = 1.00
                    driver_list = []

                    if enable_intuition:
                        if is_dgw:
                            intuition_boost *= 1.40
                            driver_list.append("Double Gameweek (DGW)")

                        if has_target_fixture and has_home_game and has_setpiece_duty:
                            intuition_boost *= 1.35
                            driver_list.append("Home Target Fixture + Set-Piece Duty")
                        elif has_target_fixture and has_setpiece_duty:
                            intuition_boost *= 1.25
                            driver_list.append("Target Fixture + Set-Piece Duty")
                        elif has_target_fixture and has_home_game:
                            intuition_boost *= 1.15
                            driver_list.append("Home Target Fixture")
                        elif has_setpiece_duty:
                            intuition_boost *= 1.10
                            driver_list.append("Set-Piece Duty")

                    human_score = round(ai_score * intuition_boost, 2)
                    driver_str = (
                        " + ".join(driver_list)
                        if driver_list
                        else "Form / Base Matchup"
                    )

                    return pd.Series(
                        [ai_score, human_score, driver_str],
                        index=["AI_Score", "Intuition_Score", "Drivers"],
                    )

                df_squad[
                    ["AI_Score", "Intuition_Score", "Drivers"]
                ] = df_squad.apply(calculate_captain_score, axis=1)

                df_ai_caps = df_squad.sort_values(
                    by="AI_Score", ascending=False
                ).reset_index(drop=True)
                df_intuition_caps = df_squad.sort_values(
                    by="Intuition_Score", ascending=False
                ).reset_index(drop=True)

                top_ai_cap = df_ai_caps.iloc[0]
                top_ai_vc = (
                    df_ai_caps.iloc[1] if len(df_ai_caps) > 1 else top_ai_cap
                )
                top_human_cap = df_intuition_caps.iloc[0]

                if enable_intuition:
                    c_card1, c_card2, c_card3 = st.columns(3)
                else:
                    c_card1, c_card2 = st.columns(2)

                with c_card1:
                    st.markdown(
                        f"""
                        <div class="rec-card" style="border-left-color: #eab308; background-color: #fefce8;">
                            <h4 style="margin:0; color:#854d0e;">🤖 Pure AI Model Pick (C)</h4>
                            <h2 style="margin: 8px 0; color:#a16207;">{top_ai_cap['web_name']}</h2>
                            <p style="margin:0;">
                                <strong>Opponent:</strong> {top_ai_cap['Next_Fixture']} (FDR: {top_ai_cap['FDR']})<br/>
                                <strong>Form:</strong> {top_ai_cap['Form_Float']} | <strong>xGI:</strong> {float(top_ai_cap.get('expected_goals', 0))+float(top_ai_cap.get('expected_assists', 0)):.2f}<br/>
                                <strong>Model Score:</strong> <code>{top_ai_cap['AI_Score']} pts</code>
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with c_card2:
                    st.markdown(
                        f"""
                        <div class="rec-card" style="border-left-color: #64748b; background-color: #f8fafc;">
                            <h4 style="margin:0; color:#334155;">🛡️ AI Vice-Captain (VC)</h4>
                            <h2 style="margin: 8px 0; color:#475569;">{top_ai_vc['web_name']}</h2>
                            <p style="margin:0;">
                                <strong>Opponent:</strong> {top_ai_vc['Next_Fixture']} (FDR: {top_ai_vc['FDR']})<br/>
                                <strong>Form:</strong> {top_ai_vc['Form_Float']} | <strong>xGI:</strong> {float(top_ai_vc.get('expected_goals', 0))+float(top_ai_vc.get('expected_assists', 0)):.2f}<br/>
                                <strong>Model Score:</strong> <code>{top_ai_vc['AI_Score']} pts</code>
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if enable_intuition:
                    with c_card3:
                        st.markdown(
                            f"""
                            <div class="rec-card" style="border-left-color: #7c3aed; background-color: #f5f3ff;">
                                <h4 style="margin:0; color:#5b21b6;">🧠 Manager's Eye Pick (C)</h4>
                                <h2 style="margin: 8px 0; color:#6d28d9;">{top_human_cap['web_name']}</h2>
                                <p style="margin:0;">
                                    <strong>Opponent:</strong> {top_human_cap['Next_Fixture']} (FDR: {top_human_cap['FDR']})<br/>
                                    <strong>Intuition Drivers:</strong> {top_human_cap['Drivers']}<br/>
                                    <strong>Weighted Score:</strong> <code>{top_human_cap['Intuition_Score']} pts</code>
                                </p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                # --------------------------------------------------------------
                # AUTOMATED CHIP TRIGGER RADAR & DRAFT GENERATOR
                # --------------------------------------------------------------
                st.markdown("---")
                st.markdown("### ⚡ Automated Chip Trigger Radar")

                chips_remaining = my_history.get("Chips Remaining", [])

                tc_triggered = (
                    top_human_cap["Intuition_Score"] >= 8.5
                    and "3XC" in chips_remaining
                )

                bench_xp_sum = sum(
                    compute_player_xp(player_obj_dict[pid])
                    for pid in my_picks.get("Bench", [])
                    if pid in player_obj_dict
                )
                bb_triggered = (
                    bench_xp_sum >= 12.0 and "BBOOST" in chips_remaining
                )

                blank_starters_count = sum(
                    1
                    for pid in my_picks.get("Starting", [])
                    if pid in player_obj_dict
                    and not next_fixtures_map.get(
                        player_obj_dict[pid]["team"], []
                    )
                )
                fh_triggered = (
                    blank_starters_count >= 3 and "FREEHIT" in chips_remaining
                )

                if tc_triggered:
                    st.markdown(
                        f"""
                        <div class="rec-card rec-card-chip">
                            🚀 <strong>TRIPLE CAPTAIN CHIP RECOMMENDATION:</strong><br/>
                            <strong>{top_human_cap['web_name']}</strong> has reached an elite Manager's Eye Score of 
                            <code>{top_human_cap['Intuition_Score']} pts</code> ({top_human_cap['Drivers']}). 
                            Consider activating your <strong>Triple Captain (3XC)</strong> chip.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if bb_triggered:
                    st.markdown(
                        f"""
                        <div class="rec-card rec-card-chip">
                            🧱 <strong>BENCH BOOST CHIP RECOMMENDATION:</strong><br/>
                            Your substitute bench has a high total baseline projection of 
                            <code>{bench_xp_sum:.2f} xP</code>. Consider activating your 
                            <strong>Bench Boost (BBOOST)</strong> chip.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if fh_triggered:
                    st.markdown(
                        f"""
                        <div class="rec-card rec-card-danger">
                            🚨 <strong>FREE HIT CHIP RECOMMENDATION:</strong><br/>
                            You currently have <strong>{blank_starters_count} starting players</strong> facing a Blank Gameweek. 
                            Consider deploying your <strong>Free Hit (FREEHIT)</strong> chip.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if not (tc_triggered or bb_triggered or fh_triggered):
                    st.caption(
                        "⚪ No strict automatic chip triggers hit for this Gameweek."
                    )

                col_chip_t1, col_chip_t2 = st.columns([1, 2])
                with col_chip_t1:
                    enable_yolo_chip = st.toggle(
                        "🃏 Enable YOLO Wildcard / Free Hit Draft Mode",
                        value=False,
                        key="toggle_yolo_chip",
                    )
                with col_chip_t2:
                    st.caption(
                        "Constructs the optimal 15-player squad strictly adhering to current prices, budget limits, and max 3 players per club."
                    )

                if enable_yolo_chip:
                    st.markdown(
                        """
                        <div class="rec-card rec-card-chip" style="background-color: #f0fdf4; border-left-color: #16a34a;">
                            🃏 <strong>OPTIMAL WILDCARD / FREE HIT DRAFT: Existing + Target Market</strong><br/>
                            Evaluates your current squad alongside market targets. High-performing assets are retained, while underperforming assets are replaced to maximize total 15-man xP under budget.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    squad_value = (
                        sum(p["Cost_m"] for _, p in df_squad.iterrows())
                        if not df_squad.empty
                        else 100.0
                    )
                    total_budget = squad_value + my_picks.get("Bank", 0.0)

                    full_player_pool = []

                    for _, p_squad in df_squad.iterrows():
                        full_player_pool.append({
                            "ID": p_squad["id"],
                            "Name": p_squad["web_name"],
                            "Team_ID": p_squad["team"],
                            "Team": teams.get(p_squad["team"], "UNK"),
                            "Pos_ID": p_squad["element_type"],
                            "Pos": POSITION_MAP.get(p_squad["element_type"], "UNK"),
                            "Price": f"£{p_squad['Cost_m']:.1f}m",
                            "Cost_Raw": p_squad["Cost_m"],
                            "Status": "🛡️ Retained (Owned)",
                            "Vs": p_squad["Next_Fixture"],
                            "xP": p_squad["xP_Proxy"],
                            "Is_Owned": True
                        })

                    for p_mkt in market_hotspots:
                        if p_mkt["ID"] not in set(df_squad["id"]):
                            p_mkt_entry = dict(p_mkt)
                            p_mkt_entry["Is_Owned"] = False
                            p_mkt_entry["Status"] = "🆕 Market Buy"
                            full_player_pool.append(p_mkt_entry)

                    df_pool = pd.DataFrame(full_player_pool).sort_values(by="xP", ascending=False)

                    yolo_squad = []
                    team_counts = {}
                    pos_counts = {1: 0, 2: 0, 3: 0, 4: 0}
                    pos_limits = {1: 2, 2: 5, 3: 5, 4: 3}
                    spent_budget = 0.0

                    for _, player in df_pool.iterrows():
                        pos_id = player["Pos_ID"]
                        team_id = player["Team_ID"]
                        cost = player["Cost_Raw"]

                        if (
                            pos_counts[pos_id] < pos_limits[pos_id]
                            and team_counts.get(team_id, 0) < 3
                            and (spent_budget + cost) <= total_budget
                        ):
                            yolo_squad.append(player)
                            pos_counts[pos_id] += 1
                            team_counts[team_id] = team_counts.get(team_id, 0) + 1
                            spent_budget += cost

                        if len(yolo_squad) == 15:
                            break

                    df_yolo_squad = pd.DataFrame(yolo_squad)

                    if not df_yolo_squad.empty:
                        total_draft_cost = df_yolo_squad["Cost_Raw"].sum()
                        total_draft_xp = df_yolo_squad["xP"].sum()
                        retained_count = sum(1 for p in yolo_squad if p["Is_Owned"])
                        new_transfers_count = 15 - retained_count
                        remaining_bank = total_budget - total_draft_cost

                        c_d1, c_d2, c_d3, c_d4 = st.columns(4)
                        c_d1.metric("💰 Draft Squad Cost", f"£{total_draft_cost:.1f}m", f"Cap: £{total_budget:.1f}m")
                        c_d2.metric("💵 Remaining Bank", f"£{remaining_bank:.1f}m")
                        c_d3.metric("🔁 Transfers Made", f"{new_transfers_count} IN / {new_transfers_count} OUT", f"{retained_count} Retained")
                        c_d4.metric("⚡ Total Draft xP", f"{total_draft_xp:.2f} pts")

                        st.dataframe(
                            df_yolo_squad[["Name", "Pos", "Price", "Vs", "xP", "Status"]],
                            use_container_width=True,
                            hide_index=True,
                            height=((len(df_yolo_squad) + 1) * 35 + 5),
                            column_config={
                                "xP": st.column_config.NumberColumn(format="%.2f pts")
                            },
                        )
                    else:
                        st.warning("Unable to assemble a valid 15-player squad within the selected budget.")

                # --------------------------------------------------------------
                # STRATEGIC TRANSFER THRESHOLDS & MULTI-TRANSFER HIT COMBOS
                # --------------------------------------------------------------
                st.markdown("---")
                st.markdown("### 💡 Strategic Transfer Recommendations")

                available_fts = my_history.get("Saved FTs", 1)

                if available_fts > 0:
                    hit_cost = 0
                    xp_threshold = 2.5
                    transfer_label = f"Free Transfer ({available_fts} available)"
                else:
                    hit_cost = 4
                    xp_threshold = 4.5
                    transfer_label = "⚠️ -4 Point Hit Required (0 FTs remaining)"

                st.caption(
                    f"Current Status: **{transfer_label}**. Net advantage factors in the -{hit_cost} point hit penalty where applicable."
                )

                single_transfer_calls = []

                for pos_code in [1, 2, 3, 4]:
                    pos_name = POSITION_MAP.get(pos_code)
                    
                    if not df_squad.empty:
                        pos_squad_players = df_squad[df_squad["element_type"] == pos_code]
                    else:
                        pos_squad_players = pd.DataFrame()

                    best_pos_call = None
                    max_net_gain = -999.0

                    if not pos_squad_players.empty:
                        for _, sell_p in pos_squad_players.iterrows():
                            current_xp = sell_p["xP_Proxy"]
                            max_budget = sell_p["Cost_m"] + my_picks.get("Bank", 0.0)

                            replacements = [
                                p
                                for p in market_hotspots
                                if p["Pos_ID"] == pos_code
                                and p["Cost_Raw"] <= max_budget
                                and p["ID"] != sell_p["id"]
                            ]

                            for target in replacements:
                                raw_gain = target["xP"] - current_xp
                                net_gain = raw_gain - hit_cost

                                if net_gain > max_net_gain:
                                    max_net_gain = net_gain
                                    best_pos_call = (sell_p, target, raw_gain, net_gain)

                    if best_pos_call:
                        sell_p, top_target, raw_gain, net_gain = best_pos_call
                        single_transfer_calls.append({
                            "pos": pos_name,
                            "pos_code": pos_code,
                            "sell": sell_p,
                            "buy": top_target,
                            "raw_gain": raw_gain,
                            "net_gain": net_gain
                        })

                        meets_thresh = net_gain >= (xp_threshold - hit_cost)
                        tag_color = "#059669" if meets_thresh else "#64748b"

                        if hit_cost > 0:
                            status_msg = (
                                f"✅ Worth the -4 Hit (Net Gain >= +{xp_threshold - hit_cost:.1f} pts)"
                                if meets_thresh
                                else "❌ Avoid -4 Hit (Insufficient Net Gain)"
                            )
                        else:
                            status_msg = (
                                f"✅ Recommended Upgrade (>= +{xp_threshold:.1f} pts gain)"
                                if meets_thresh
                                else "⚪ Optional Upgrade"
                            )

                        st.markdown(
                            f"""
                            <div class="rec-card" style="border-left-color: {tag_color};">
                                🔄 <strong>Suggested Transfer Call ({pos_name}):</strong><br/>
                                <strong>OUT:</strong> {sell_p['web_name']} ({pos_name}) — Form: <code>{sell_p['Form_Float']}</code> | Price: <code>£{sell_p['Cost_m']:.1f}m</code> | Est. xP: <code>{sell_p['xP_Proxy']:.2f} pts</code><br/>
                                <strong>IN:</strong> {top_target['Name']} ({top_target['Pos']}) — Est. xP: <code>{top_target['xP']:.2f} pts</code> | Market Status: <code>{top_target['Status']}</code> | Price: <code>{top_target['Price']}</code><br/>
                                <strong>Raw xP Gain:</strong> <code>+{raw_gain:.2f} pts</code> | <strong>Hit Penalty:</strong> <code>-{hit_cost} pts</code><br/>
                                <strong>Projected Net Advantage:</strong> <code>{net_gain:+.2f} pts</code> — <em>{status_msg}</em>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"""
                            <div class="rec-card" style="border-left-color: #cbd5e1;">
                                ⚪ <strong>No Transfer Needed ({pos_name}):</strong> Your current {pos_name} assets are already fully optimized for budget & xP.
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                # --------------------------------------------------------------
                # MULTI-PLAYER "HIT COMBO" MODELING ENGINE
                # --------------------------------------------------------------
                st.markdown("---")
                st.markdown("### 💥 Multi-Player 'Hit Combo' Modeling Engine")
                st.caption(
                    "Simulates multi-transfer swaps (e.g., 2-player or 3-player moves) across positional boundaries, factoring in combined budget pooling and hit cost deductions."
                )

                valid_combos = [c for c in single_transfer_calls if c["raw_gain"] > 0]
                valid_combos = sorted(valid_combos, key=lambda x: x["raw_gain"], reverse=True)

                if len(valid_combos) >= 2:
                    combo2 = valid_combos[:2]
                    raw_gain_2 = sum(c["raw_gain"] for c in combo2)
                    transfers_count_2 = 2
                    
                    extra_transfers_2 = max(0, transfers_count_2 - available_fts)
                    combo2_hit_cost = extra_transfers_2 * 4
                    net_gain_2 = raw_gain_2 - combo2_hit_cost

                    c2_color = "#059669" if net_gain_2 > 0 else "#dc2626"

                    p1_str = f"OUT: <strong>{combo2[0]['sell']['web_name']}</strong> ➔ IN: <strong>{combo2[0]['buy']['Name']}</strong>"
                    p2_str = f"OUT: <strong>{combo2[1]['sell']['web_name']}</strong> ➔ IN: <strong>{combo2[1]['buy']['Name']}</strong>"

                    st.markdown(
                        f"""
                        <div class="rec-card" style="border-left-color: {c2_color};">
                            💥 <strong>2-Player Hit Combo ({transfers_count_2} Transfers):</strong><br/>
                            1️⃣ {p1_str}<br/>
                            2️⃣ {p2_str}<br/>
                            <strong>Combined Raw xP Gain:</strong> <code>+{raw_gain_2:.2f} pts</code> | <strong>Hit Penalty ({extra_transfers_2} Extra Transfers):</strong> <code>-{combo2_hit_cost} pts</code><br/>
                            <strong>Net Multi-Swap Advantage:</strong> <code>{net_gain_2:+.2f} pts</code> — <em>{'✅ Profitable Multi-Swap Combo' if net_gain_2 > 0 else '❌ Avoid Combo (Negative Net Value)'}</em>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if len(valid_combos) >= 3:
                    combo3 = valid_combos[:3]
                    raw_gain_3 = sum(c["raw_gain"] for c in combo3)
                    transfers_count_3 = 3
                    
                    extra_transfers_3 = max(0, transfers_count_3 - available_fts)
                    combo3_hit_cost = extra_transfers_3 * 4
                    net_gain_3 = raw_gain_3 - combo3_hit_cost

                    c3_color = "#059669" if net_gain_3 > 0 else "#dc2626"

                    p1_str = f"OUT: <strong>{combo3[0]['sell']['web_name']}</strong> ➔ IN: <strong>{combo3[0]['buy']['Name']}</strong>"
                    p2_str = f"OUT: <strong>{combo3[1]['sell']['web_name']}</strong> ➔ IN: <strong>{combo3[1]['buy']['Name']}</strong>"
                    p3_str = f"OUT: <strong>{combo3[2]['sell']['web_name']}</strong> ➔ IN: <strong>{combo3[2]['buy']['Name']}</strong>"

                    st.markdown(
                        f"""
                        <div class="rec-card" style="border-left-color: {c3_color};">
                            💥 <strong>3-Player Hit Combo ({transfers_count_3} Transfers):</strong><br/>
                            1️⃣ {p1_str}<br/>
                            2️⃣ {p2_str}<br/>
                            3️⃣ {p3_str}<br/>
                            <strong>Combined Raw xP Gain:</strong> <code>+{raw_gain_3:.2f} pts</code> | <strong>Hit Penalty ({extra_transfers_3} Extra Transfers):</strong> <code>-{combo3_hit_cost} pts</code><br/>
                            <strong>Net Multi-Swap Advantage:</strong> <code>{net_gain_3:+.2f} pts</code> — <em>{'✅ Profitable Multi-Swap Combo' if net_gain_3 > 0 else '❌ Avoid Combo (Negative Net Value)'}</em>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if len(valid_combos) < 2:
                    st.caption("⚪ Insufficient positive single-transfer moves to construct a multi-swap combo for this Gameweek.")
