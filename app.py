import pandas as pd
import streamlit as st

# ------------------------------------------------------------------
# 📋 SETUP / MOCK DATA ASSUMPTIONS (Adjust to your variable names)
# ------------------------------------------------------------------
POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# Example placeholder variables if not already defined globally in your app:
# my_picks -> dict containing player IDs in your squad, e.g., my_picks = {"Squad": [101, 102, ...]}
# elements -> list of all player dictionaries from FPL API
# teams -> dict mapping team ID to name, e.g., {1: "ARS", 2: "AVL", ...}
# next_fixtures_map -> dict mapping team ID to next fixture info


# ------------------------------------------------------------------
# 🔥 TAB 3: MARKET HOTSPOTS (WITH SQUAD TOGGLE & AUTO-SORT)
# ------------------------------------------------------------------
def render_market_hotspots(elements, my_picks, teams, next_fixtures_map):
    st.markdown("### 🔥 Market Hotspots (Best Buy Targets)")

    # 1. Controls Layout: Slider (Left), Toggle (Right)
    col_ctrl1, col_ctrl2 = st.columns([2, 1])

    with col_ctrl1:
        num_rows = st.slider(
            "🎚️ Display Row Limit (per position):",
            min_value=3,
            max_value=7,
            value=5,
            key="hs_rows",
        )

    with col_ctrl2:
        exclude_owned = st.toggle(
            "🙈 Hide My Owned Players",
            value=True,
            help="Turn off to include players in your current squad (e.g., De Cuyper) alongside transfer targets.",
            key="hs_exclude_toggle",
        )

    st.caption(
        "High Expected Points (xP) assets cross-referenced with real-time market price momentum."
    )

    # 2. Extract Owned Squad IDs
    my_squad_ids = set(my_picks.get("Squad", []))

    # 3. Process & Compute Market Data
    market_hotspots = []

    for p in elements:
        # Check toggle: skip owned players only when toggle is enabled
        if exclude_owned and p["id"] in my_squad_ids:
            continue

        # Calculate xP proxy metric
        form_val = float(p.get("form", 0.0))
        xg_val = float(p.get("expected_goals", 0.0))
        xa_val = float(p.get("expected_assists", 0.0))
        xgi_val = xg_val + xa_val
        xp_proxy = round((form_val * 0.5) + (xgi_val * 0.5), 2)

        # Fixture Information
        f_info = next_fixtures_map.get(p["team"], {})
        opp_name = teams.get(f_info.get("opp"), "UNK") if f_info else "N/A"
        loc = "(H)" if f_info.get("is_home") else "(A)"
        vs_str = f"{opp_name} {loc}"

        # Status & Momentum Calculation
        net = p.get("transfers_in_event", 0) - p.get("transfers_out_event", 0)
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

        # Label owned players visually when revealed
        player_name = (
            f"{p['web_name']} (Owned)"
            if (not exclude_owned and p["id"] in my_squad_ids)
            else p["web_name"]
        )

        market_hotspots.append(
            {
                "ID": p["id"],
                "Name": player_name,
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

    # 4. Render 4-Column Layout Grid
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

            if not df_hotspots.empty:
                # Force programmatic sorting by xP (and Net Transfers as tie-breaker)
                sub_df = (
                    df_hotspots[df_hotspots["Pos_ID"] == pos_code]
                    .sort_values(
                        by=["xP", "Net_Transfers"], ascending=[False, False]
                    )
                    .head(num_rows)[display_fields]
                )
                calc_height = (len(sub_df) + 1) * 35 + 5
            else:
                sub_df = pd.DataFrame(columns=display_fields)
                calc_height = 100

            st.dataframe(
                sub_df,
                use_container_width=True,
                hide_index=True,
                height=calc_height,
                column_config={
                    "xP": st.column_config.NumberColumn(format="%.2f"),
                },
            )
