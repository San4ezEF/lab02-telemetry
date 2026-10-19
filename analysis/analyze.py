"""Расчёт метрик PostgreSQL и сохранение результатов."""

import math
import sys
from pathlib import Path

import matplotlib
import pandas as pd
from sqlalchemy import select

matplotlib.use("Agg")
import matplotlib.pyplot as plt  
from matplotlib.patches import Rectangle 

RES = Path(__file__).resolve().parents[1] / "results"
STAGES = ["session_start", "checkpoint", "level_complete"]


def load():
    from server.database import engine
    from server.models import Event

    with engine.connect() as connection:
        return pd.read_sql_query(select(Event).order_by(Event.id), connection)


def session_table(df):
    rows = []
    for session_id, events in df.groupby("session_id"):
        starts = events[events.event_type == "session_start"].drop_duplicates(["ts", "level"])
        ends = events[events.event_type == "session_end"].drop_duplicates(["ts", "level"])
        start, end = starts.ts.min(), ends.ts.max()
        valid = len(starts) == 1 and len(ends) <= 1 and events.player_id.nunique() == 1
        valid = valid and events.ts.min() >= start and (ends.empty or events.ts.max() <= end)
        rows.append({
            "session_id": session_id, "player_id": events.player_id.iloc[0],
            "level": starts.level.iloc[0] if len(starts) == 1 else None,
            "start_ts": start, "length_s": end - start if valid else float("nan"), "valid": valid,
        })
    return pd.DataFrame(rows, columns=["session_id", "player_id", "level", "start_ts", "length_s", "valid"])


def retention_table(df):
    starts = df[df.event_type == "session_start"].copy()
    starts["day"] = pd.to_datetime(starts.ts, unit="s", utc=True).dt.normalize()
    rows = []
    for player, events in starts.groupby("player_id"):
        first = events.day.min()
        rows.append({
            "player_id": player, "first_day": first,
            "returned_d1": (events.day == first + pd.Timedelta(days=1)).any(),
            "d1_observed": first + pd.Timedelta(days=2) <= pd.Timestamp.now(tz="UTC"),
        })
    return pd.DataFrame(rows, columns=["player_id", "first_day", "returned_d1", "d1_observed"])


def funnel(df, sessions):
    counts = [0, 0, 0]
    for session in sessions[sessions.valid.astype(bool)].itertuples(index=False):
        events = df[(df.session_id == session.session_id) & (df.level == session.level)]
        timestamp = session.start_ts
        # Сессия учитывается один раз на этапе, только после предыдущего этапа.
        for index, stage in enumerate(STAGES):
            reached = events[(events.event_type == stage) & (events.ts >= timestamp)]
            if reached.empty:
                break
            counts[index] += 1
            timestamp = reached.ts.min()
    table = pd.DataFrame({"stage": STAGES, "sessions": counts})
    previous = table.sessions.shift(1, fill_value=counts[0])
    table["percent_start"] = table.sessions / (counts[0] or float("nan")) * 100
    table["lost_sessions"] = previous - table.sessions
    table["loss_percent_previous"] = table.lost_sessions / previous.replace(0, float("nan")) * 100
    return table


def length_statistics(sessions):
    return sessions.length_s.dropna().astype(float).agg(["count", "mean", "median", "min", "max"])


def length_figure(sessions):
    fig, ax = plt.subplots(figsize=(8, 4))
    lengths = sessions.length_s.dropna().astype(float)
    if len(lengths):
        ax.hist(lengths, bins="auto", edgecolor="white")
        ax.axvline(lengths.median(), color="orange", label=f"Медиана: {lengths.median():.1f} с")
        ax.legend()
    ax.set(title="Длительность сессий", xlabel="Секунды", ylabel="Количество")
    fig.tight_layout()
    return fig


def funnel_figure(table):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(table.stage, table.sessions)
    ax.invert_yaxis()
    ax.set(title="Воронка конверсии", xlabel="Количество сессий")
    fig.tight_layout()
    return fig


def death_figure(df, level):
    points = df[(df.event_type == "death") & (df.level == level)].dropna(subset=["x", "y"])
    fig, ax = plt.subplots(figsize=(8, 4))
    if len(points):
        xbins = range(min(0, math.floor(points.x.min() / 5) * 5), max(100, math.ceil(points.x.max() / 5) * 5) + 5, 5)
        ybins = range(min(0, math.floor(points.y.min() / 5) * 5), max(50, math.ceil(points.y.max() / 5) * 5) + 5, 5)
        histogram = ax.hist2d(points.x, points.y, bins=[xbins, ybins], cmap="YlOrRd", cmin=1)
        fig.colorbar(histogram[3], ax=ax, label="Смерти")
    # Условные зоны генератора, не карта реальной игры.
    zones = {"L1": [(12.5, 3, "Шипы"), (45, 20, "Враги")], "L2": [(70, 12, "Шипы"), (30, 35, "Враги")]}
    for x, y, label in zones.get(level, []):
        ax.add_patch(Rectangle((x - 5, y - 3), 10, 6, fill=False, linestyle="--"))
        ax.text(x, y + 4, label, ha="center")
    ax.set(title=f"Смерти: {level}", xlabel="x", ylabel="y", aspect="equal")
    fig.tight_layout()
    return fig


def conclusions(df, table):
    lines = []
    if table.sessions.iloc[0]:
        index = table.lost_sessions.iloc[1:].idxmax()
        loss = table.loc[index]
        lines.append(
            f"Наибольшая потеря: {STAGES[index - 1]} -> {loss.stage}, "
            f"{loss.lost_sessions} сессий ({loss.loss_percent_previous:.1f}%). Проверьте сложность этого участка."
        )
    for level, deaths in df[df.event_type == "death"].dropna(subset=["x", "y"]).groupby("level"):
        cells = deaths.groupby([deaths.x // 5 * 5, deaths.y // 5 * 5]).size()
        x, y = cells.idxmax()
        lines.append(
            f"{level}: ячейка x=[{x:g}, {x + 5:g}), y=[{y:g}, {y + 5:g}) содержит "
            f"{cells.max() / len(deaths):.1%} смертей. Проверьте препятствие в этой зоне."
        )
    return lines


def save_results(df, output=RES):
    if df.empty:
        print("Событий нет. Сначала запустите симулятор.")
        return
    output.mkdir(parents=True, exist_ok=True)
    sessions, players = session_table(df), retention_table(df)
    table, stats = funnel(df, sessions), length_statistics(sessions)
    sessions.to_csv(output / "sessions.csv", index=False)
    players.to_csv(output / "retention_d1.csv", index=False)
    table.to_csv(output / "conversion_funnel.csv", index=False)
    stats.to_csv(output / "session_statistics.csv", header=["value"])
    figures = [("session_lengths.png", length_figure(sessions)), ("conversion_funnel.png", funnel_figure(table))]
    levels = sorted(df.level.unique())
    for index, level in enumerate(levels, start=1):
        figures.append((f"death_heatmap_{index}.png", death_figure(df, level)))
    pd.DataFrame({"number": range(1, len(levels) + 1), "level": levels}).to_csv(output / "levels.csv", index=False)
    for name, figure in figures:
        figure.savefig(output / name, dpi=150)
        plt.close(figure)
    lines = [
        f"Сессии: {len(sessions)}; игроки: {len(players)}; D1 (UTC): {players.returned_d1.mean():.2%}.",
        f"Длительность, с: среднее {stats['mean']:.1f}, медиана {stats['median']:.1f}, "
        f"минимум {stats['min']:.1f}, максимум {stats['max']:.1f}.",
        f"Без корректного окончания: {sessions.length_s.isna().sum()}; "
        f"игроки с незавершённым днём D1: {(~players.d1_observed.astype(bool)).sum()}.",
        *conclusions(df, table),
        "Данные синтетические. Heatmap показывает число смертей, а не вероятность гибели.",
    ]
    (output / "conclusions.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(table.to_string(index=False, float_format="%.1f"))
    print(f"Файлы: {output}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    save_results(load())
