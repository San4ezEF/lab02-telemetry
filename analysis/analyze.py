"""4 обязательных расчёта: длина сессий, retention, heatmap смертей, конверсия в прохождение."""

import sqlite3
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB, RES = ROOT / "data" / "telemetry.db", ROOT / "results"
RES.mkdir(exist_ok=True)


def load() -> pd.DataFrame:
    with sqlite3.connect(DB) as c:
        return pd.read_sql("SELECT * FROM events", c, parse_dates=False)


def session_length(df: pd.DataFrame) -> pd.Series:
    g = df.groupby("session_id")["ts"]
    return (g.max() - g.min()).rename("length_s")


def retention(df: pd.DataFrame) -> float:
    per_player = df.groupby("player_id")["session_id"].nunique()
    return float((per_player >= 2).mean())


def death_heatmap(df: pd.DataFrame) -> Path:
    d = df[df.event_type == "death"]
    plt.figure()
    plt.hist2d(d.x, d.y, bins=10)
    plt.title("Death heatmap")
    out = RES / "death_heatmap.png"
    plt.savefig(out, dpi=150)
    return out


def completion_rate(df: pd.DataFrame) -> float:
    done = df[df.event_type == "level_complete"].session_id.nunique()
    return done / df.session_id.nunique()


if __name__ == "__main__":
    df = load()
    sl = session_length(df)
    print(f"Сессий: {df.session_id.nunique()}, средняя длина: {sl.mean():.1f} c")
    print(f"Retention (2+ сессии): {retention(df):.2%}")
    print(f"Конверсия в прохождение: {completion_rate(df):.2%}")
    print("Heatmap:", death_heatmap(df))
    sl.describe().to_csv(RES / "session_length.csv")
