import sys
from pathlib import Path

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.analyze import (  
    death_figure,
    funnel,
    funnel_figure,
    length_figure,
    load,
    plt,
    retention_table,
    session_table,
)

st.set_page_config(page_title="Игровая телеметрия")
st.title("Игровая телеметрия")
st.button("Обновить данные")

try:
    events = load()
except (SQLAlchemyError, ValueError):
    st.error("Не удалось прочитать PostgreSQL. Проверьте службу, таблицу events и настройки .env.")
    st.stop()

if events.empty:
    st.info("Событий пока нет. Запустите клиент с --simulate 20.")
    st.stop()

levels = sorted(events.level.dropna().unique())
selected = st.selectbox("Уровень", [None, *levels], format_func=lambda level: level or "Все уровни", key="level")
sessions = session_table(events)
if selected is not None:
    sessions = sessions[sessions.level == selected]

players = retention_table(events)
table = funnel(events, sessions)
lengths = sessions.length_s.dropna()
rate = players.returned_d1.mean() if len(players) else None
c1, c2, c3, c4 = st.columns(4)
c1.metric("Сессий", len(sessions))
c2.metric("Игроков в выборке", sessions.player_id.nunique())
c3.metric("Медиана сессии", f"{lengths.median():.1f} с" if len(lengths) else "—")
c4.metric("D1 — все уровни", f"{rate:.2%}" if rate is not None else "—")
st.caption("Фильтр — по стартовому уровню сессии. D1 — по всем игрокам, календарные дни UTC.")
pending = int((~players.d1_observed).sum()) if len(players) else 0
if pending:
    st.warning(f"У {pending} игроков день D1 ещё не закончился: общий показатель предварительный.")
invalid = int(sessions.length_s.isna().sum())
if invalid:
    st.warning(f"В длительность не включены {invalid} сессий без корректной пары start/end.")

st.subheader("Длительность сессий")
figure = length_figure(sessions)
st.pyplot(figure)
plt.close(figure)

st.subheader("Воронка конверсии")
figure = funnel_figure(table)
st.pyplot(figure)
plt.close(figure)
st.dataframe(table, hide_index=True)

st.subheader("Карта смертей")
for level in [selected] if selected is not None else levels:
    figure = death_figure(events, level)
    st.pyplot(figure)
    plt.close(figure)
st.caption("Heatmap: ячейки 5×5, пунктир — зоны симулятора. Выводы сохраняются при запуске анализа в results.")
