"""Приёмник телеметрии: POST /events → SQLite (telemetry.db)."""

import sqlite3
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

DB = Path(__file__).resolve().parents[1] / "data" / "telemetry.db"
DB.parent.mkdir(exist_ok=True)
app = FastAPI(title="Telemetry ingest")


class Event(BaseModel):
    session_id: str
    player_id: str
    event_type: str
    ts: float
    level: str | None = None
    x: float | None = None
    y: float | None = None
    payload: dict = {}


def init_db() -> None:
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY, session_id TEXT, player_id TEXT, event_type TEXT,
            ts REAL, level TEXT, x REAL, y REAL, payload TEXT)""")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.post("/events", status_code=202)
def ingest(events: list[Event]) -> dict:
    import json

    with sqlite3.connect(DB) as c:
        c.executemany(
            "INSERT INTO events(session_id,player_id,event_type,ts,level,x,y,payload) "
            "VALUES(?,?,?,?,?,?,?,?)",
            [(e.session_id, e.player_id, e.event_type, e.ts, e.level, e.x, e.y, json.dumps(e.payload))
             for e in events],
        )
    return {"accepted": len(events)}
