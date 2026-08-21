import pandas as pd
import requests

from functools import lru_cache


# ==================================================
# SETTINGS
# ==================================================

REFERENCE_FILES = [
    "data/count_stress_2021.parquet",
    "data/count_stress_2022.parquet",
    "data/count_stress_2023.parquet",
    "data/count_stress_2024.parquet",
    "data/count_stress_2025.parquet",
]

SEASON_FILES = {
    2021: "data/count_stress_2021.parquet",
    2022: "data/count_stress_2022.parquet",
    2023: "data/count_stress_2023.parquet",
    2024: "data/count_stress_2024.parquet",
    2025: "data/count_stress_2025.parquet",
    2026: "data/count_stress_2026.parquet",
}

AVAILABLE_SEASONS = [
    2026,
    2025,
    2024,
    2023,
    2022,
    2021,
]

DEFAULT_SEASON = 2026


# Pitch Stress formula
BOS_WEIGHT = 0.60
CSS_WEIGHT = 0.40

# Count Stress formula
OFFENSIVE_DANGER_WEIGHT = 0.60
PITCH_CONSEQUENCE_WEIGHT = 0.40

# Pitch Stress threshold used for PS%
STRESSFUL_PITCH_THRESHOLD = 40.0


# ==================================================
# APS+ SETTINGS
# ==================================================

# Preferred comparison population
APS_PLUS_MIN_PITCHES = 500

# Minimum number of pitchers we want in the
# reference population before using that threshold
APS_PLUS_MIN_REFERENCE_PLAYERS = 20

# One standard deviation = 15 APS+ points
APS_PLUS_SD_SCALE = 15.0


# ==================================================
# BASIC DATA PREPARATION
# ==================================================

def prepare_pitch_data(df):
    df = df.copy()

    df["count"] = (
        df["balls"].astype(str)
        + "-"
        + df["strikes"].astype(str)
    )

    # Base-state coding:
    # 000 = Empty
    # 100 = 1st
    # 010 = 2nd
    # 001 = 3rd
    # 110 = 1st & 2nd
    # 101 = 1st & 3rd
    # 011 = 2nd & 3rd
    # 111 = Loaded
    df["base_state"] = (
        df["on_1b"].notna().astype(int).astype(str)
        + df["on_2b"].notna().astype(int).astype(str)
        + df["on_3b"].notna().astype(int).astype(str)
    )

    return df


# ==================================================
# LOAD FIXED 2021-2025 REFERENCE DATA
# ==================================================

reference_df = pd.concat(
    [
        pd.read_parquet(file)
        for file in REFERENCE_FILES
    ],
    ignore_index=True,
)

reference_df = prepare_pitch_data(
    reference_df
)


# ==================================================
# CALCULATE RUNS REMAINING
# ==================================================

reference_df = reference_df.sort_values(
    [
        "game_pk",
        "inning",
        "inning_topbot",
        "at_bat_number",
        "pitch_number",
    ]
).copy()

reference_df["inning_final_score"] = (
    reference_df.groupby(
        [
            "game_pk",
            "inning",
            "inning_topbot",
        ]
    )["post_bat_score"]
    .transform("max")
)

reference_df["runs_remaining"] = (
    reference_df["inning_final_score"]
    - reference_df["bat_score"]
)


# ==================================================
# RUN EXPECTANCY BY BASE/OUT STATE + COUNT
# ==================================================

state_count_re = (
    reference_df.groupby(
        [
            "base_state",
            "outs_when_up",
            "count",
        ]
    )["runs_remaining"]
    .mean()
    .reset_index(
        name="run_expectancy"
    )
)


# ==================================================
# OFFENSIVE DANGER
# ==================================================

baseline = (
    state_count_re[
        state_count_re["count"] == "0-0"
    ][
        [
            "base_state",
            "outs_when_up",
            "run_expectancy",
        ]
    ]
    .rename(
        columns={
            "run_expectancy": "re_0_0"
        }
    )
)

state_count_re = state_count_re.merge(
    baseline,
    on=[
        "base_state",
        "outs_when_up",
    ],
    how="left",
)

state_count_re["count_run_effect"] = (
    state_count_re["run_expectancy"]
    - state_count_re["re_0_0"]
)

offensive_danger_raw = (
    state_count_re
    .groupby("count")["count_run_effect"]
    .mean()
)

od_min = offensive_danger_raw.min()
od_max = offensive_danger_raw.max()

offensive_danger_score = (
    100
    * (
        offensive_danger_raw
        - od_min
    )
    / (
        od_max
        - od_min
    )
)


# ==================================================
# 0-0 RUN EXPECTANCY LOOKUP
# ==================================================

re_baseline_lookup = (
    state_count_re[
        state_count_re["count"] == "0-0"
    ]
    .set_index(
        [
            "base_state",
            "outs_when_up",
        ]
    )["run_expectancy"]
    .to_dict()
)


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def re_after_strikeout(
    base_state,
    outs,
):
    if outs == 2:
        return 0.0

    return re_baseline_lookup[
        (
            base_state,
            outs + 1,
        )
    ]


def base_state_after_walk(
    base_state,
):
    on_1b = (
        base_state[0] == "1"
    )

    on_2b = (
        base_state[1] == "1"
    )

    on_3b = (
        base_state[2] == "1"
    )

    new_1b = True
    new_2b = on_1b

    new_3b = (
        on_3b
        or (
            on_1b
            and on_2b
        )
    )

    return (
        str(int(new_1b))
        + str(int(new_2b))
        + str(int(new_3b))
    )


def re_after_walk(
    base_state,
    outs,
):
    new_state = (
        base_state_after_walk(
            base_state
        )
    )

    run_scored = (
        1
        if base_state == "111"
        else 0
    )

    return (
        run_scored
        + re_baseline_lookup[
            (
                new_state,
                outs,
            )
        ]
    )


# ==================================================
# PITCH CONSEQUENCE
# ==================================================

pitch_consequence_results = {}


# --------------------------------------------------
# NON-TERMINAL COUNTS
# --------------------------------------------------

count_transitions = {
    "0-0": ("1-0", "0-1"),
    "0-1": ("1-1", "0-2"),
    "1-0": ("2-0", "1-1"),
    "1-1": ("2-1", "1-2"),
    "2-0": ("3-0", "2-1"),
    "2-1": ("3-1", "2-2"),
}

for count, (
    ball_count,
    strike_count,
) in count_transitions.items():

    re_ball = (
        state_count_re[
            state_count_re["count"]
            == ball_count
        ][
            [
                "base_state",
                "outs_when_up",
                "run_expectancy",
            ]
        ]
        .rename(
            columns={
                "run_expectancy":
                    "re_ball"
            }
        )
    )

    re_strike = (
        state_count_re[
            state_count_re["count"]
            == strike_count
        ][
            [
                "base_state",
                "outs_when_up",
                "run_expectancy",
            ]
        ]
        .rename(
            columns={
                "run_expectancy":
                    "re_strike"
            }
        )
    )

    merged = re_ball.merge(
        re_strike,
        on=[
            "base_state",
            "outs_when_up",
        ],
    )

    merged["pitch_consequence"] = (
        merged["re_ball"]
        - merged["re_strike"]
    )

    pitch_consequence_results[count] = (
        merged["pitch_consequence"]
        .mean()
    )


# --------------------------------------------------
# TWO-STRIKE COUNTS
# --------------------------------------------------

two_strike_counts = {
    "0-2": "1-2",
    "1-2": "2-2",
    "2-2": "3-2",
}

for (
    count,
    ball_count,
) in two_strike_counts.items():

    re_ball = (
        state_count_re[
            state_count_re["count"]
            == ball_count
        ][
            [
                "base_state",
                "outs_when_up",
                "run_expectancy",
            ]
        ]
        .rename(
            columns={
                "run_expectancy":
                    "re_ball"
            }
        )
    )

    re_ball["re_strike"] = (
        re_ball.apply(
            lambda row:
                re_after_strikeout(
                    row["base_state"],
                    row["outs_when_up"],
                ),
            axis=1,
        )
    )

    re_ball["pitch_consequence"] = (
        re_ball["re_ball"]
        - re_ball["re_strike"]
    )

    pitch_consequence_results[count] = (
        re_ball["pitch_consequence"]
        .mean()
    )


# --------------------------------------------------
# THREE-BALL COUNTS
# --------------------------------------------------

three_ball_counts = {
    "3-0": "3-1",
    "3-1": "3-2",
}

for (
    count,
    strike_count,
) in three_ball_counts.items():

    re_strike = (
        state_count_re[
            state_count_re["count"]
            == strike_count
        ][
            [
                "base_state",
                "outs_when_up",
                "run_expectancy",
            ]
        ]
        .rename(
            columns={
                "run_expectancy":
                    "re_strike"
            }
        )
    )

    re_strike["re_ball"] = (
        re_strike.apply(
            lambda row:
                re_after_walk(
                    row["base_state"],
                    row["outs_when_up"],
                ),
            axis=1,
        )
    )

    re_strike["pitch_consequence"] = (
        re_strike["re_ball"]
        - re_strike["re_strike"]
    )

    pitch_consequence_results[count] = (
        re_strike["pitch_consequence"]
        .mean()
    )


# --------------------------------------------------
# FULL COUNT
# --------------------------------------------------

re_32 = (
    state_count_re[
        state_count_re["count"]
        == "3-2"
    ][
        [
            "base_state",
            "outs_when_up",
        ]
    ]
    .copy()
)

re_32["re_ball"] = (
    re_32.apply(
        lambda row:
            re_after_walk(
                row["base_state"],
                row["outs_when_up"],
            ),
        axis=1,
    )
)

re_32["re_strike"] = (
    re_32.apply(
        lambda row:
            re_after_strikeout(
                row["base_state"],
                row["outs_when_up"],
            ),
        axis=1,
    )
)

re_32["pitch_consequence"] = (
    re_32["re_ball"]
    - re_32["re_strike"]
)

pitch_consequence_results["3-2"] = (
    re_32["pitch_consequence"]
    .mean()
)


# ==================================================
# COUNT STRESS SCORE (CSS)
# ==================================================

pitch_consequence_raw = (
    pd.Series(
        pitch_consequence_results
    )
)

pc_min = pitch_consequence_raw.min()
pc_max = pitch_consequence_raw.max()

pitch_consequence_score = (
    100
    * (
        pitch_consequence_raw
        - pc_min
    )
    / (
        pc_max
        - pc_min
    )
)

count_stress_score = (
    OFFENSIVE_DANGER_WEIGHT
    * offensive_danger_score
    + PITCH_CONSEQUENCE_WEIGHT
    * pitch_consequence_score
)


# ==================================================
# COUNT STRESS LOOKUP TABLE
# ==================================================

count_stress_table = (
    pd.DataFrame({
        "offensive_danger_raw":
            offensive_danger_raw,

        "offensive_danger_score":
            offensive_danger_score,

        "pitch_run_swing":
            pitch_consequence_raw,

        "pitch_consequence_score":
            pitch_consequence_score,

        "css":
            count_stress_score,
    })
    .round(3)
    .sort_index()
)


# ==================================================
# BASE-OUT STRESS (BOS)
# ==================================================

base_out_re = (
    reference_df.groupby(
        [
            "base_state",
            "outs_when_up",
        ]
    )["runs_remaining"]
    .mean()
    .reset_index(
        name="run_expectancy"
    )
)

bos_min = (
    base_out_re[
        "run_expectancy"
    ].min()
)

bos_max = (
    base_out_re[
        "run_expectancy"
    ].max()
)

base_out_re["bos_score"] = (
    10
    + 90
    * (
        base_out_re[
            "run_expectancy"
        ]
        - bos_min
    )
    / (
        bos_max
        - bos_min
    )
)

base_out_re["bos_score"] = (
    base_out_re["bos_score"]
    .round(1)
)


# ==================================================
# FIXED LOOKUPS
# ==================================================

bos_lookup = (
    base_out_re
    .set_index(
        [
            "base_state",
            "outs_when_up",
        ]
    )["bos_score"]
    .to_dict()
)

css_lookup = (
    count_stress_score
    .to_dict()
)

run_swing_lookup = (
    pitch_consequence_raw
    .to_dict()
)


# ==================================================
# APPLY FIXED MODEL TO A SEASON
# ==================================================

def apply_stress_model(df):
    df = prepare_pitch_data(
        df
    )

    df["bos_score"] = (
        df.apply(
            lambda row:
                bos_lookup.get(
                    (
                        row["base_state"],
                        row["outs_when_up"],
                    )
                ),
            axis=1,
        )
    )

    df["css_score"] = (
        df["count"]
        .map(
            css_lookup
        )
    )

    df["pitch_run_swing"] = (
        df["count"]
        .map(
            run_swing_lookup
        )
    )

    df["pitch_stress_score"] = (
        BOS_WEIGHT
        * df["bos_score"]
        + CSS_WEIGHT
        * df["css_score"]
    )

    df["stressful_pitch"] = (
        df["pitch_stress_score"]
        >= STRESSFUL_PITCH_THRESHOLD
    )

    return df


# ==================================================
# BASEBALL IP CONVERSION
# ==================================================

def baseball_ip_to_decimal(ip):
    whole, partial = (
        str(ip).split(".")
    )

    whole = int(whole)
    partial = int(partial)

    return (
        whole
        + partial / 3
    )


# ==================================================
# OFFICIAL MLB INNINGS PITCHED
# ==================================================

@lru_cache(maxsize=None)
def get_official_ip(season):

    url = (
        "https://statsapi.mlb.com/"
        "api/v1/stats"
    )

    params = {
        "stats": "season",
        "group": "pitching",
        "season": int(season),
        "playerPool": "ALL",
        "limit": 2000,
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    official_rows = []

    for stats_group in (
        data.get(
            "stats",
            []
        )
    ):
        for split in (
            stats_group.get(
                "splits",
                []
            )
        ):

            player = (
                split.get(
                    "player",
                    {}
                )
            )

            stat = (
                split.get(
                    "stat",
                    {}
                )
            )

            pitcher_id = (
                player.get("id")
            )

            innings_pitched = (
                stat.get(
                    "inningsPitched"
                )
            )

            if (
                pitcher_id is not None
                and innings_pitched is not None
            ):
                official_rows.append({
                    "pitcher":
                        pitcher_id,

                    "official_ip":
                        innings_pitched,
                })

    official_ip = (
        pd.DataFrame(
            official_rows
        )
        .drop_duplicates(
            subset="pitcher"
        )
    )

    official_ip["ip_decimal"] = (
        official_ip["official_ip"]
        .apply(
            baseball_ip_to_decimal
        )
    )

    return official_ip.copy()


# ==================================================
# LOAD ONE SEASON
# ==================================================

@lru_cache(maxsize=None)
def load_season_data(season):

    season = int(season)

    if season not in SEASON_FILES:
        raise ValueError(
            f"Season {season} is not available."
        )

    df = pd.read_parquet(
        SEASON_FILES[season]
    )

    df = apply_stress_model(
        df
    )

    return df


# ==================================================
# APS+ REFERENCE POPULATION
# ==================================================

def get_aps_plus_reference_population(
    pitcher_stats,
):
    # First choice: pitchers with 500+ pitches
    reference = pitcher_stats[
        pitcher_stats["pitches"]
        >= APS_PLUS_MIN_PITCHES
    ].copy()

    # Early-season fallback:
    # if fewer than 20 pitchers have reached 500 pitches,
    # progressively lower the threshold.
    if (
        len(reference)
        < APS_PLUS_MIN_REFERENCE_PLAYERS
    ):
        for threshold in [
            400,
            300,
            200,
            100,
        ]:
            reference = pitcher_stats[
                pitcher_stats["pitches"]
                >= threshold
            ].copy()

            if (
                len(reference)
                >= APS_PLUS_MIN_REFERENCE_PLAYERS
            ):
                break

    # Absolute fallback
    if len(reference) < 2:
        reference = pitcher_stats.copy()

    return reference


# ==================================================
# BUILD SEASON PITCHER LEADERBOARD
# ==================================================

@lru_cache(maxsize=None)
def build_pitcher_stats(season):

    season = int(season)

    season_df = (
        load_season_data(
            season
        )
        .copy()
    )


    # ==============================================
    # RAW PITCHER STRESS STATS
    # ==============================================

    pitcher_stats = (
        season_df.groupby(
            [
                "pitcher",
                "player_name",
            ]
        )
        .agg(
            pitches=(
                "pitch_stress_score",
                "size",
            ),

            stressful_pitches=(
                "stressful_pitch",
                "sum",
            ),

            aps=(
                "pitch_stress_score",
                "mean",
            ),

            total_stress=(
                "pitch_stress_score",
                "sum",
            ),
        )
        .reset_index()
    )


    # ==============================================
    # PS%
    # ==============================================

    pitcher_stats["ps_pct"] = (
        100
        * pitcher_stats[
            "stressful_pitches"
        ]
        / pitcher_stats[
            "pitches"
        ]
    )


    # ==============================================
    # OFFICIAL IP
    # ==============================================

    official_ip = (
        get_official_ip(
            season
        )
    )

    pitcher_stats = (
        pitcher_stats.merge(
            official_ip[
                [
                    "pitcher",
                    "official_ip",
                    "ip_decimal",
                ]
            ],
            on="pitcher",
            how="left",
        )
    )


    # ==============================================
    # SS/9
    # ==============================================

    pitcher_stats["ss_per_9"] = (
        pitcher_stats["total_stress"]
        / pitcher_stats["ip_decimal"]
        * 9
    )


    # ==============================================
    # REMOVE PLAYERS WITHOUT VALID IP
    # ==============================================

    pitcher_stats = (
        pitcher_stats[
            pitcher_stats[
                "ip_decimal"
            ].notna()
            & (
                pitcher_stats[
                    "ip_decimal"
                ]
                > 0
            )
        ]
        .copy()
    )


    # ==============================================
    # APS+ REFERENCE POPULATION
    # ==============================================

    aps_reference = (
        get_aps_plus_reference_population(
            pitcher_stats
        )
    )

    aps_reference_mean = (
        aps_reference["aps"]
        .mean()
    )

    aps_reference_std = (
        aps_reference["aps"]
        .std()
    )


    # ==============================================
    # APS+
    # ==============================================

    if (
        pd.isna(aps_reference_std)
        or aps_reference_std == 0
    ):
        pitcher_stats["aps_plus"] = 100.0

    else:
        pitcher_stats["aps_plus"] = (
            100
            + APS_PLUS_SD_SCALE
            * (
                aps_reference_mean
                - pitcher_stats["aps"]
            )
            / aps_reference_std
        )


    # ==============================================
    # DISPLAY ROUNDING
    # ==============================================

    pitcher_stats["aps"] = (
        pitcher_stats["aps"]
        .round(1)
    )

    pitcher_stats["aps_plus"] = (
        pitcher_stats["aps_plus"]
        .round(0)
        .astype(int)
    )

    pitcher_stats["ps_pct"] = (
        pitcher_stats["ps_pct"]
        .round(1)
    )

    pitcher_stats["ss_per_9"] = (
        pitcher_stats["ss_per_9"]
        .round(1)
    )

    pitcher_stats = (
        pitcher_stats
        .sort_values(
            "aps_plus",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    return (
        pitcher_stats,
        aps_reference_mean,
        aps_reference_std,
        len(aps_reference),
    )


# ==================================================
# DEFAULT SEASON
# ==================================================

(
    pitcher_stats,
    league_aps,
    league_aps_std,
    aps_reference_count,
) = build_pitcher_stats(
    DEFAULT_SEASON
)


# ==================================================
# TEST OUTPUT
# ==================================================

if __name__ == "__main__":

    print(
        "\nFIXED COUNT STRESS TABLE"
    )

    print(
        count_stress_table
    )

    print(
        "\nFIXED BASE-OUT STRESS TABLE"
    )

    print(
        base_out_re
    )

    print(
        f"\n{DEFAULT_SEASON} "
        "PITCHER STRESS LEADERBOARD"
    )

    print(
        pitcher_stats[
            [
                "player_name",
                "pitches",
                "official_ip",
                "ps_pct",
                "aps",
                "aps_plus",
                "ss_per_9",
            ]
        ]
        .head(30)
    )

    print(
        f"\n{DEFAULT_SEASON} APS+ REFERENCE"
    )

    print(
        f"Reference pitchers: "
        f"{aps_reference_count}"
    )

    print(
        f"Reference mean APS: "
        f"{league_aps:.3f}"
    )

    print(
        f"Reference APS SD: "
        f"{league_aps_std:.3f}"
    )