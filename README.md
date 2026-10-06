# Лабораторная работа № 2. Игровая телеметрия

Сбор событий и анализ поведения игроков: длительность сессий, D1 retention,
карты смертей и конверсия прохождения.

**Стек:** Python 3.11+, FastAPI, PostgreSQL, SQLAlchemy, psycopg, pandas, matplotlib, Streamlit.

```text
client/python_logger.py -> HTTP POST /events -> server/app.py -> PostgreSQL
                                                               |
                                                     analysis/analyze.py
                                                        /           \
                                                    results/   dashboard/app.py
```

## Подготовка

Нужна запущенная служба PostgreSQL, база `game_telemetry` и роль `telemetry_user`
с правами подключения и создания таблиц в схеме `public`.
Настройки подключения задаются в `.env` по образцу `.env.example`.
`.env` содержит пароль и не включается в Git.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Запуск

Команды выполняются из корня проекта. В первом терминале:

```powershell
.\.venv\Scripts\python.exe -m server.models
.\.venv\Scripts\python.exe -m uvicorn server.app:app --reload
```

API: <http://127.0.0.1:8000/docs>. Проверка подключения к БД: <http://127.0.0.1:8000/health>.

Во втором терминале:

```powershell
.\.venv\Scripts\python.exe client/python_logger.py --simulate 20 --seed 42
.\.venv\Scripts\python.exe analysis/analyze.py
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py
```

Dashboard: <http://localhost:8501>. Повторная генерация добавляет новые сессии.

## Просмотр PostgreSQL

В pgAdmin выберите `game_telemetry` и откройте Query Tool:

```sql
SELECT * FROM public.events ORDER BY id LIMIT 20;

SELECT count(*) AS events,
       count(DISTINCT session_id) AS sessions,
       count(DISTINCT player_id) AS players
FROM public.events;

SELECT event_type, count(*) FROM public.events GROUP BY event_type ORDER BY event_type;
```

## Метрики и результаты

- Длительность: `session_end.ts - session_start.ts`; сессии без корректного окончания исключаются.
- D1: доля игроков с новой сессией на следующий календарный день UTC после первой сессии.
- Heatmap: число смертей в ячейках 5×5, отдельно по уровням; пунктиром отмечены зоны симулятора.
- Воронка: уникальные сессии, последовательно достигшие `session_start`, `checkpoint`, `level_complete`.
  Проценты считаются от начала, потери — от предыдущего этапа.
- Фильтр dashboard выбирает сессии по начальному уровню; D1 остаётся общим для всех игроков.

Скрипт анализа создаёт в `results/` таблицы CSV, графики PNG и краткие выводы `conclusions.txt`.
Соответствие номеров heatmap уровням записывается в `levels.csv`.
Схема событий: [docs/event_schema.md](docs/event_schema.md).

Контрольный запуск на пустой БД с `--simulate 20 --seed 42`: 107 событий, 20 сессий,
12 игроков; D1 — 4/12 = 33,33%; медиана — 262,5 с; воронка — 20 → 16 → 8.
Это синтетические данные для демонстрации расчётов.
