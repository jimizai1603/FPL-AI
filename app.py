import pandas as pd
import requests
import streamlit as st

# --- Page Config ---
st.set_page_config(
    page_title="FPL AI Dashboard", page_icon="⚽", layout="wide"
)

# --- Styling & CSS ---
st.markdown(
    """
<style>
    .rec-card {
        padding: 15px;
        border-radius: 8px;
        background-color: #f0f2f6;
        margin-bottom: 10px;
        border-left: 5px solid #00ff87;
    }
    .rec-card-danger {
        background-color: #fff0f0;
        border-left: 5px solid #ff4b4b;
    }
</style>
""",
    unsafe_allow_html=True,
)

# --- Constants & Mappings ---
POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


# --- Data Fetching Functions ---
@st.cache_data(ttl=3600)
def fetch_fpl_bootstrap():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None


@st.cache_data(ttl=3600)
def fetch_user_team(team_id):
    url = f"https://fantasy.premierleague.com/api/entry/{team_id}/my-team/"
    # Public endpoint alternative for user picks if unauthenticated
    history_url = (
        f"https://fantasy.premierleague.com/api/entry/{team_id}/history/"
    )
    res = requests.get(history_url)
    if res.status_code == 200:
        current_gw = (
            res.json().get("current", [])[-1]["event"]
            if res.json().get("current")
            else 1
        )
        picks_url = f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{current_gw}/picks/"
        picks_res = requests.get(picks_url)
        if picks_res.status_code == 200:
            return picks_res.json(), current_gw
    return None, 1


# --- Analytics Computation ---
def compute_xp_and_price_risk(row, next_fixtures_map, ml_ownership_map):
    pid = row["id"]
    t_id = row["team"]
    form_val = row["Form_Float"]

    # Expected Points Proxy: Form (50%) + xGI (50%) adjusted by FDR
    xg_val = float(row.get("expected_goals", 0.0))
    xa_val = float(row.get("expected_assists", 0.0))
    xgi_val = xg_val + xa_val

    base_xp = (form_val * 0.5) + (xgi_val * 0.5)

    # Next GW Fixture Difficulty Multiplier
    fix_info = next_fixtures_map.get(t_id, {})
    fdr = fix_info.get("fdr", 3)
    fdr_multiplier = 1.2 if fdr <= 2 else (0.8 if fdr >= 4 else 1.0)
    est_xp = round(base_xp * fdr_multiplier, 2)

    # Dynamic Price Risk Evaluation
    net_trans = row.get("transfers_in_event", 0) - row.get(
        "transfers_out_event", 0
    )
    gw_change = row.get("cost_change_event", 0) / 10
    effective_net = net_trans - (gw_change * 10 * 50000)

    if effective_net <= -40000:
        price_risk = "🚨 Drop Imminent"
    elif effective_net < -15000:
        price_risk = "⚠️ Sell Pressure"
    elif effective_net >= 40000:
        price_risk = "🚀 Rise Imminent"
    else:
        price_risk = "🟢 Price Stable"

    ml_eo = ml_ownership_map.get(pid, float(row.get("selected_by_percent", 0)))

    return pd.Series([est_xp, price_risk, ml_eo, fdr])


# --- Main App Interface ---
st.title("⚽ FPL AI Squad Advisor")

# Sidebar - Team Selection
st.sidebar.header("User Settings")
team_id_input = st.sidebar.number_input(
    "Enter FPL Team ID", min_value=1, value=1, step=1
)

# Fetch Base Data
bootstrap_data = fetch_fpl_bootstrap()

if bootstrap_data:
    elements = bootstrap_data["elements"]
    events = bootstrap_data["events"]

    # Determine Next Gameweek
    current_gw_obj = next(
        (e for e in events if e["is_current"]), events[0]
    )
    current_gw = current_gw_obj["id"]
    next_gw = current_gw + 1

    # Load User Squad Data
    user_picks_data, user_gw = fetch_user_team(team_id_input)

    if user_picks_data and "picks" in user_picks_data:
        squad_pids = [p["element"] for p in user_picks_data["picks"]]

        # Dataframe Transformations
        all_players_df = pd.DataFrame(elements)
        all_players_df["Cost_m"] = all_players_df["now_cost"] / 10
        all_players_df["Form_Float"] = all_players_df["form"].astype(float)

        df_squad = all_players_df[
            all_players_df["id"].isin(squad_pids)
        ].copy()

        # Placeholders for Fixtures and Mini-League Mapping
        next_fixtures_map = {}
        ml_ownership_map = {}

        # Compute Metrics
        df_squad[["Est_xP", "Price_Risk", "ML_EO%", "Next_FDR"]] = (
            df_squad.apply(
                compute_xp_and_price_risk,
                axis=1,
                args=(next_fixtures_map, ml_ownership_map),
            )
        )

        # 1. Squad Display Table
        df_squad_display = df_squad[
            [
                "web_name",
                "element_type",
                "Cost_m",
                "Form_Float",
                "Est_xP",
                "Next_FDR",
                "Price_Risk",
                "ML_EO%",
            ]
        ].copy()
        df_squad_display["Pos"] = df_squad_display["element_type"].map(
            POSITION_MAP
        )
        df_squad_display = df_squad_display.rename(
            columns={
                "web_name": "Player",
                "Cost_m": "Cost (£m)",
                "Form_Float": "Form",
                "Est_xP": f"Est. xP (GW{next_gw})",
                "ML_EO%": "Selected %",
            }
        )

        st.markdown(f"#### 📋 Current Squad Analytics (GW {next_gw} Outlook)")
        st.dataframe(
            df_squad_display[
                [
                    "Player",
                    "Pos",
                    "Cost (£m)",
                    "Form",
                    f"Est. xP (GW{next_gw})",
                    "Next_FDR",
                    "Price_Risk",
                    "Selected %",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        # 2. Executive Transfer Recommendations
        st.markdown("---")
        st.markdown("### 💡 Executive Transfer & Risk Recommendations")
        c_rec1, c_rec2 = st.columns(2)

        # Priority Sell Candidates
        sell_candidates = df_squad[
            (df_squad["Est_xP"] < 3.0)
            | (df_squad["Price_Risk"].str.contains("Drop|Sell"))
        ].sort_values(by="Est_xP", ascending=True)

        with c_rec1:
            st.markdown("#### 🚨 Priority Exit Targets")
            if not sell_candidates.empty:
                for _, row in sell_candidates.head(3).iterrows():
                    st.markdown(
                        f"""
                        <div class="rec-card rec-card-danger">
                            <strong>🔴 {row['web_name']}</strong> ({POSITION_MAP.get(row['element_type'])}) — £{row['Cost_m']:.1f}m<br>
                            • <strong>Est. xP:</strong> {row['Est_xP']} pts | <strong>Status:</strong> {row['Price_Risk']}<br>
                            • <em>Action:</em> Consider offloading to preserve squad value.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    """
                    <div class="rec-card">
                        <strong>✅ Squad Value & Form Optimized</strong><br>
                        No immediate price drops or low-performing assets flagged for exit.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Priority Buy Candidates
        buy_candidates = all_players_df[
            ~all_players_df["id"].isin(squad_pids)
            & (
                all_players_df["chance_of_playing_next_round"].fillna(100)
                == 100
            )
        ].sort_values(
            by=["transfers_in_event", "Form_Float"], ascending=[False, False]
        )

        with c_rec2:
            st.markdown("#### 🚀 Target Buy Vectors")
            for _, row in buy_candidates.head(3).iterrows():
                st.markdown(
                    f"""
                    <div class="rec-card">
                        <strong>🟢 {row['web_name']}</strong> ({POSITION_MAP.get(row['element_type'])}) — £{row['Cost_m']:.1f}m<br>
                        • <strong>Form:</strong> {row['Form_Float']} pts | <strong>Transfers In:</strong> +{row['transfers_in_event']:,}<br>
                        • <em>Action:</em> High market pressure asset. Candidate for price rises.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.warning(
            f"Unable to load squad details for Team ID `{team_id_input}`. Please verify your FPL Team ID in the sidebar."
        )
else:
    st.error("Failed to connect to Fantasy Premier League APIs.")
