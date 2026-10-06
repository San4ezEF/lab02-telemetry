import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.analyze import completion_rate, death_heatmap, load, retention, session_length  # noqa: E402

st.title("Игровая телеметрия — дашборд")
df = load()
c1, c2, c3 = st.columns(3)
c1.metric("Сессий", df.session_id.nunique())
c2.metric("Retention", f"{retention(df):.0%}")
c3.metric("Конверсия", f"{completion_rate(df):.0%}")
st.subheader("Длина сессий")
st.bar_chart(session_length(df))
st.subheader("Heatmap смертей")
st.image(str(death_heatmap(df)))
