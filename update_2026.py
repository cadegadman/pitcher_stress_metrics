from datetime import date, timedelta

from pybaseball import statcast


# ==================================================
# SETTINGS
# ==================================================

START_DATE = "2026-03-25"
END_DATE = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

OUTPUT_FILE = "data/count_stress_2026.parquet"


# ==================================================
# DOWNLOAD 2026 STATCAST DATA
# ==================================================

print(
    f"Downloading 2026 Statcast data "
    f"from {START_DATE} through {END_DATE}..."
)

df = statcast(
    start_dt=START_DATE,
    end_dt=END_DATE,
)


# ==================================================
# SAVE DATA
# ==================================================

df.to_parquet(
    OUTPUT_FILE,
    index=False,
)

print()
print("2026 Statcast download complete.")
print(f"Total pitches: {len(df):,}")
print(f"Saved to: {OUTPUT_FILE}")


# ==================================================
# REBUILD 2026 LEADERBOARD
# ==================================================

print()
print("Rebuilding 2026 pitcher stress leaderboard...")

from count_stress_data import export_leaderboard

export_leaderboard(2026)

print("2026 leaderboard update complete.")