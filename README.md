# Лабораторная работа № 2. Сбор и анализ игровой телеметрии

Дисциплина «Игровой искусственный интеллект»


## Стек

Unity/Python клиент · SQLite/PostgreSQL · pandas · Streamlit/Jupyter

## Что нужно сдать

- [ ] Клиентский логгер событий
- [ ] БД с 20+ сессиями
- [ ] Скрипт анализа: 4 расчёта (длина сессий, retention, heatmap смертей, конверсия)
- [ ] Дашборд с 3+ визуализациями

Полное задание, критерии оценки и типичные ошибки — в методических указаниях (ЛР № 2).

## Структура

```
client/python_logger.py        логгер событий (JSON Lines → файл или HTTP POST)
client/unity/TelemetryLogger.cs  то же для Unity
server/app.py                  FastAPI: POST /events → SQLite
analysis/analyze.py            4 расчёта + сохранение графиков в results/
dashboard/app.py               Streamlit-дашборд
docs/event_schema.md           схема событий (заполнить)
```

```bash
pip install -r requirements.txt   # или: make install (все команды: make help)
uvicorn server.app:app --reload         # сервер
python client/python_logger.py --simulate 20   # 20 синтетических сессий
python analysis/analyze.py && streamlit run dashboard/app.py
```

## Пример выполнения

**Где это в играх.** Bungie при разработке Halo 3 строила тепловые карты смертей на мультиплеерных картах и по ним
находила перекошенные позиции. King отслеживает, на каком уровне Candy Crush игроки застревают и бросают игру, и
по этим данным подстраивает сложность. В free-to-play-играх метрики retention D1/D7/D30 решают судьбу проекта:
игру с низким удержанием закрывают ещё в софт-запуске.

**Зачем:** разработчик не видит, как играют тысячи людей, и телеметрия заменяет ему наблюдение. Логгер → БД → анализ →
дашборд из этой ЛР — уменьшенная копия этого пайплайна.

**Пример событий одной сессии** (`data/events.jsonl`, одна строка на событие):

```json
{"session_id": "a1f3", "player_id": "p5", "event_type": "session_start", "ts": 1727080000.0, "level": "L1"}
{"session_id": "a1f3", "player_id": "p5", "event_type": "death", "ts": 1727080042.5, "level": "L1", "x": 12.4, "y": 3.1, "cause": "spikes"}
{"session_id": "a1f3", "player_id": "p5", "event_type": "checkpoint", "ts": 1727080090.1, "level": "L1", "x": 40.0, "y": 5.0}
{"session_id": "a1f3", "player_id": "p5", "event_type": "level_complete", "ts": 1727080155.0, "level": "L1", "time_s": 155.0}
{"session_id": "a1f3", "player_id": "p5", "event_type": "session_end", "ts": 1727080300.0, "level": "L2", "reason": "quit"}
```

**Пример расчёта: длина сессии** (SQL поверх таблицы `events`):

```sql
SELECT session_id, MAX(ts) - MIN(ts) AS length_s
FROM events
GROUP BY session_id
ORDER BY length_s DESC;
```

**Как определить метрики** (формулировки обязательно приведите в README):

| Метрика | Определение |
|---|---|
| Длина сессии | `ts(session_end) − ts(session_start)`, медиана и гистограмма |
| Retention D1 | доля игроков, у которых есть сессия на следующий день после первой |
| Heatmap смертей | 2D-гистограмма `(x, y)` событий `death`, отдельно по уровням |
| Конверсия | воронка `session_start → checkpoint → level_complete`, % на каждом шаге |

**Пример вывода:** «60 % смертей на L1 приходится на участок x ∈ [10, 15] (шипы), воронка теряет 45 % игроков между
checkpoint и level_complete — участок стоит упростить». Главное — не только график, но и вывод по нему.

**Дашборд:** гистограмма длины сессий, heatmap смертей поверх схемы уровня, воронка конверсии, фильтр по уровню.


