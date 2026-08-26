import pandas as pd
import streamlit as st

# --- Helper Maps & Constants ---
POSITION_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


# --- 1. Compute Analytics ---
def compute_xp_and_price_risk(row, next_fixtures_map, ml_ownership_map):
    pid = row["id"]
    t_id = row["team"]
    form_val = row["Form_Float"]

    # Expected Points Proxy Math: Form (50%) + xGI (50%) adjusted by FDR
    xg_val = float(row.get("expected_goals", 0.0))
    xa_val = float(row.get("expected_assists", 0.0))
    xgi_val = xg_val + xa_val

    base_xp = (form_val * 0.5) + (xgi_val * 0.5)

    # Apply Next GW Fixture Difficulty Multiplier
    fix_info = next_fixtures_map.get(t_id, {})
    fdr = fix_info.get("fdr", 3)
    fdr_multiplier = 1.2 if fdr <= 2 else (0.8 if fdr >= 4 else 1.0)
    est_xp = round(base_xp * fdr_multiplier, 2)

    # Dynamic Price Risk Evaluation
    net_trans = row.get("Net_Transfers", 0)
    gw_change = row.get("cost_change_event", 0) / 10
    effective_net = net_trans - (gw_change * 10 * 50000)

    if effective_net <= -40000:
        price_risk = "🚨 Drop Imminent (Tonight)"
    elif effective_net < -15000:
        price_risk = "⚠️ Sell Pressure High"
    elif effective_net >= 40000:
        price_risk = "🚀 Rise Imminent"
    else:
        price_risk = "🟢 Price Stable"

    # Mini-League Ownership context
    ml_eo = ml_ownership_map.get(pid, 0.0)

    return pd.Series([est_xp, price_risk, ml_eo, fix_info.get("fdr", "-")])


def run_squad_advisor(
    df_squad,
    next_fixtures_map,
    ml_ownership_map,
    next_gw,
    elements,
    my_picks,
):
    # Compute Analytics for Squad
    df_squad[["Est_xP", "Price_Risk", "ML_EO%", "Next_FDR"]] = df_squad.apply(
        compute_xp_and_price_risk,
        axis=1,
        args=(next_fixtures_map, ml_ownership_map),
    )

    # --- 2. Squad Breakdown Display ---
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
            "ML_EO%": "League Ownership %",
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
                "League Ownership %",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    # --- 3. Executive Recommendations ---
    st.markdown("---")
    st.markdown("### 💡 Executive Transfer & Risk Recommendations")

    c_rec1, c_rec2 = st.columns(2)

    # Priority Sell Candidates (Low xP + Drop Risk)
    sell_candidates = df_squad[
        (df_squad["Est_xP"] < 3.0)
        | (df_squad["Price_Risk"].str.contains("Drop|Sell"))
    ].sort_values(by="Est_xP", ascending=True)

    with c_rec1:
        st.markdown(
            "#### 🚨 Priority Exit Targets (Sell Pressure / Low xP)"
        )
        if not sell_candidates.empty:
            for _, row in sell_candidates.head(3).iterrows():
                st.markdown(
                    f"""
                    <div class="rec-card rec-card-danger">
                        <strong>🔴 {row['web_name']}</strong> ({POSITION_MAP.get(row['element_type'])}) — £{row['Cost_m']:.1f}m<br>
                        • <strong>Est. xP:</strong> {row['Est_xP']} pts | <strong>Status:</strong> {row['Price_Risk']}<br>
                        • <em>Action:</em> Consider offloading to preserve squad value and unlock funds.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                """
                <div class="rec-card">
                    <strong>✅ Squad Value & Form Optimized</strong><br>
                    No immediate price drops or low-performing assets flagged for urgent exit.
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Buy Candidates (High Market Momentum + Form)
    all_players_df = pd.DataFrame(elements)
    all_players_df["Cost_m"] = all_players_df["now_cost"] / 10
    all_players_df["Form_Float"] = all_players_df["form"].astype(float)

    buy_candidates = all_players_df[
        ~all_players_df["id"].isin(my_picks["Squad"])
        & (
            all_players_df["chance_of_playing_next_round"].fillna(100) == 100
        )
    ].sort_values(
        by=["transfers_in_event", "Form_Float"], ascending=[False, False]
    )

    with c_rec2:
        st.markdown("#### 🚀 Target Buy Vectors (High Momentum Riser)")
        for _, row in buy_candidates.head(3).iterrows():
            st.markdown(
                f"""
                <div class="rec-card">
                    <strong>🟢 {row['web_name']}</strong> ({POSITION_MAP.get(row['element_type'])}) — £{row['Cost_m']:.1f}m<br>
                    • <strong>Form:</strong> {row['Form_Float']} pts | <strong>Transfers In:</strong> +{row['transfers_in_event']:,}<br>
                    • <em>Action:</em> High market pressure asset. Strong candidate to capture price rises.
                </div>
                """,
                unsafe_allow_html=True,
            )
