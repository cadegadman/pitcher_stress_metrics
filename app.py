from pathlib import Path

import pandas as pd
import streamlit as st


# ==================================================
# SETTINGS
# ==================================================

AVAILABLE_SEASONS = [
    2026,
    2025,
    2024,
    2023,
    2022,
    2021,
]

DEFAULT_SEASON = 2026

LEADERBOARD_DIR = Path(
    "data/leaderboards"
)


# ==================================================
# PAGE SETUP
# ==================================================

st.set_page_config(
    page_title="Pitcher Stress Metrics",
    page_icon="⚾",
    layout="wide",
)


# ==================================================
# LOAD SEASON LEADERBOARD
# ==================================================

@st.cache_data
def load_leaderboard(season):

    file = (
        LEADERBOARD_DIR
        / f"leaderboard_{season}.csv"
    )

    df = pd.read_csv(file)

    return df


# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.title(
    "Pitcher Stress Metrics"
)

page = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "Leaderboard",
    ],
)

selected_season = st.sidebar.selectbox(
    "Season",
    options=AVAILABLE_SEASONS,
    index=AVAILABLE_SEASONS.index(
        DEFAULT_SEASON
    ),
)


# ==================================================
# LOAD DATA
# ==================================================

season_df = load_leaderboard(
    selected_season
)

league_aps = (
    season_df[
        "aps_reference_mean"
    ]
    .iloc[0]
)

league_aps_std = (
    season_df[
        "aps_reference_std"
    ]
    .iloc[0]
)

aps_reference_count = (
    season_df[
        "aps_reference_count"
    ]
    .iloc[0]
)


# ==================================================
# DISPLAY LEADERBOARD
# ==================================================

leaderboard = season_df[
    [
        "player_name",
        "official_ip",
        "ip_decimal",
        "pitches",
        "ps_pct",
        "aps",
        "aps_plus",
        "ss_per_9",
    ]
].copy()

leaderboard = leaderboard.rename(
    columns={
        "player_name": "Pitcher",
        "official_ip": "IP",
        "pitches": "Pitches",
        "ps_pct": "PS%",
        "aps": "APS",
        "aps_plus": "APS+",
        "ss_per_9": "SS/9",
    }
)


# ==================================================
# HOME PAGE
# ==================================================

if page == "Home":

    st.title(
        "Pitcher Stress Metrics"
    )

    st.write(
        f"""
        Measuring how frequently and how intensely MLB pitchers
        operate in stressful situations.

        **Currently viewing the {selected_season} MLB season.**
        """
    )

    st.divider()


    # ==============================================
    # METRIC SUMMARY
    # ==============================================

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "APS",
            f"{league_aps:.1f} Avg",
        )

        st.caption(
            "Average Pitch Stress. "
            "Lower is better."
        )

    with col2:

        st.metric(
            "APS+",
            "100 = Average",
        )

        st.caption(
            "Standardized Average Pitch Stress. "
            "Higher is better."
        )

    with col3:

        st.metric(
            "PS%",
            "40+ Stress Score",
        )

        st.caption(
            "Percentage of pitches classified "
            "as stressful. Lower is better."
        )

    with col4:

        st.metric(
            "SS/9",
            "Stress per 9 IP",
        )

        st.caption(
            "Stress Score accumulated per "
            "nine innings. Lower is better."
        )

    st.divider()


    # ==============================================
    # QUALIFICATION FILTER
    # ==============================================

    max_ip = int(
        leaderboard[
            "ip_decimal"
        ].max()
    )

    default_home_ip = min(
        100,
        max_ip,
    )

    home_min_ip = st.slider(
        "Minimum Innings Pitched",
        min_value=0,
        max_value=max_ip,
        value=default_home_ip,
        step=5,
        key=(
            f"home_min_ip_"
            f"{selected_season}"
        ),
    )

    qualified = leaderboard[
        leaderboard["ip_decimal"]
        >= home_min_ip
    ].copy()

    st.caption(
        f"{len(qualified)} pitchers with "
        f"at least {home_min_ip} IP"
    )

    st.divider()


    # ==============================================
    # TOP 10 APS+
    # ==============================================

    st.subheader(
        "Top 10 — APS+"
    )

    aps_plus_top = (
        qualified
        .sort_values(
            "APS+",
            ascending=False,
        )
        .head(10)
        .reset_index(drop=True)
    )

    aps_plus_top.index += 1
    aps_plus_top.index.name = "Rank"

    st.dataframe(
        aps_plus_top[
            [
                "Pitcher",
                "IP",
                "APS+",
            ]
        ],
        use_container_width=True,
        column_config={
            "Pitcher":
                st.column_config.TextColumn(
                    "Pitcher",
                    width="medium",
                ),

            "IP":
                st.column_config.TextColumn(
                    "IP",
                ),

            "APS+":
                st.column_config.NumberColumn(
                    "APS+",
                    format="%d",
                ),
        },
    )

    st.divider()


    # ==============================================
    # TOP 10 PS%
    # ==============================================

    st.subheader(
        "Top 10 — PS%"
    )

    ps_top = (
        qualified
        .sort_values(
            "PS%",
            ascending=True,
        )
        .head(10)
        .reset_index(drop=True)
    )

    ps_top.index += 1
    ps_top.index.name = "Rank"

    st.dataframe(
        ps_top[
            [
                "Pitcher",
                "IP",
                "PS%",
            ]
        ],
        use_container_width=True,
        column_config={
            "Pitcher":
                st.column_config.TextColumn(
                    "Pitcher",
                    width="medium",
                ),

            "IP":
                st.column_config.TextColumn(
                    "IP",
                ),

            "PS%":
                st.column_config.NumberColumn(
                    "PS%",
                    format="%.1f%%",
                ),
        },
    )

    st.divider()


    # ==============================================
    # TOP 10 SS/9
    # ==============================================

    st.subheader(
        "Top 10 — SS/9"
    )

    ss9_top = (
        qualified
        .sort_values(
            "SS/9",
            ascending=True,
        )
        .head(10)
        .reset_index(drop=True)
    )

    ss9_top.index += 1
    ss9_top.index.name = "Rank"

    st.dataframe(
        ss9_top[
            [
                "Pitcher",
                "IP",
                "SS/9",
            ]
        ],
        use_container_width=True,
        column_config={
            "Pitcher":
                st.column_config.TextColumn(
                    "Pitcher",
                    width="medium",
                ),

            "IP":
                st.column_config.TextColumn(
                    "IP",
                ),

            "SS/9":
                st.column_config.NumberColumn(
                    "SS/9",
                    format="%.1f",
                ),
        },
    )

    st.divider()


    # ==============================================
    # HOW THE METRICS WORK
    # ==============================================

    st.header(
        "How the Metrics Work"
    )

    st.markdown(
        """
### APS — Average Pitch Stress

**Lower is better.**

APS measures the average stress level of every pitch a pitcher
throws. Each pitch receives a Pitch Stress Score based on the
base/out situation and the count.

Base-Out Stress accounts for the run-scoring danger created by
the current baserunners and number of outs. Count Stress accounts
for both the offensive danger of the count and how much expected
run value can swing based on the outcome of the next pitch.

APS averages those Pitch Stress Scores across all of a pitcher's
pitches.

**What it tells you:** How stressful is the environment of the
pitcher's typical pitch?

---

### APS+ — Average Pitch Stress Plus

**100 is average. Higher is better.**

APS+ places a pitcher's APS on a standardized league-relative
scale.

- **100** = average
- **115** = approximately one standard deviation better
- **130** = approximately two standard deviations better
- **145** = approximately three standard deviations better
- **85** = approximately one standard deviation worse

Because lower raw APS is better, APS+ reverses the scale so
higher numbers represent better stress avoidance.

---

### PS% — Pitch Stress Percentage

**Lower is better.**

PS% measures the percentage of a pitcher's total pitches that
qualify as stressful pitches.

A pitch qualifies as stressful when its Pitch Stress Score is
**40 or higher**.

**PS% = Stressful Pitches / Total Pitches × 100**

---

### SS/9 — Stress Score per 9 Innings

**Lower is better.**

SS/9 measures how much total Pitch Stress a pitcher accumulates
over the equivalent of nine innings.

**SS/9 = Total Pitch Stress / Innings Pitched × 9**

It incorporates both the stress level of pitches and the number
of pitches required to record innings.
        """
    )


# ==================================================
# LEADERBOARD PAGE
# ==================================================

elif page == "Leaderboard":

    st.title(
        f"{selected_season} "
        "Pitcher Stress Leaderboard"
    )

    st.write(
        """
        Explore MLB pitchers across APS, APS+, PS%, and SS/9.
        """
    )

    st.divider()


    # ==============================================
    # FILTERS
    # ==============================================

    max_ip = int(
        leaderboard[
            "ip_decimal"
        ].max()
    )

    default_min_ip = min(
        50,
        max_ip,
    )

    filter_col1, filter_col2 = (
        st.columns(
            [1, 2]
        )
    )

    with filter_col1:

        min_ip = st.slider(
            "Minimum Innings Pitched",
            min_value=0,
            max_value=max_ip,
            value=default_min_ip,
            step=5,
            key=(
                f"leaderboard_min_ip_"
                f"{selected_season}"
            ),
        )

    with filter_col2:

        search = st.text_input(
            "Search Pitcher",
            placeholder=(
                "Search by name..."
            ),
        )


    # ==============================================
    # APPLY FILTERS
    # ==============================================

    filtered = leaderboard[
        leaderboard["ip_decimal"]
        >= min_ip
    ].copy()

    if search:

        filtered = filtered[
            filtered["Pitcher"]
            .str.contains(
                search,
                case=False,
                na=False,
            )
        ]

    st.caption(
        f"{len(filtered)} pitchers with "
        f"at least {min_ip} IP"
    )


    # ==============================================
    # DEFAULT SORT
    # ==============================================

    filtered = (
        filtered
        .sort_values(
            "APS+",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    filtered.index += 1
    filtered.index.name = "Rank"


    # ==============================================
    # FULL LEADERBOARD
    # ==============================================

    st.dataframe(
        filtered[
            [
                "Pitcher",
                "IP",
                "Pitches",
                "APS",
                "APS+",
                "PS%",
                "SS/9",
            ]
        ],
        use_container_width=True,
        height=750,
        column_config={
            "Pitcher":
                st.column_config.TextColumn(
                    "Pitcher",
                    width="medium",
                ),

            "IP":
                st.column_config.TextColumn(
                    "IP",
                ),

            "Pitches":
                st.column_config.NumberColumn(
                    "Pitches",
                    format="%d",
                ),

            "APS":
                st.column_config.NumberColumn(
                    "APS",
                    format="%.1f",
                ),

            "APS+":
                st.column_config.NumberColumn(
                    "APS+",
                    format="%d",
                ),

            "PS%":
                st.column_config.NumberColumn(
                    "PS%",
                    format="%.1f%%",
                ),

            "SS/9":
                st.column_config.NumberColumn(
                    "SS/9",
                    format="%.1f",
                ),
        },
    )