"""Клиентский логгер: буфер событий → JSONL-файл и/или HTTP POST батчами.
Запуск с --simulate N генерирует N синтетических сессий (для отладки пайплайна)."""

import argparse
import json
import random
import time
import uuid
from pathlib import Path

import requests

SERVER = "http://localhost:8000/events"
OUT = Path(__file__).resolve().parents[1] / "data" / "events.jsonl"


class TelemetryLogger:
    def __init__(self, player_id: str, batch_size: int = 20, send_http: bool = True):
        self.session_id = uuid.uuid4().hex
        self.player_id = player_id
        self.batch_size = batch_size
        self.send_http = send_http
        self.buffer: list[dict] = []
        OUT.parent.mkdir(exist_ok=True)

    def log(self, event_type: str, **kw) -> None:
        self.buffer.append({"session_id": self.session_id, "player_id": self.player_id,
                            "event_type": event_type, "ts": time.time(), **kw})
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        with OUT.open("a", encoding="utf-8") as f:
            for e in self.buffer:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        if self.send_http:
            try:
                requests.post(SERVER, json=self.buffer, timeout=2)
            except requests.RequestException as exc:
                print("send failed:", exc)
        self.buffer.clear()


def simulate(n_sessions: int) -> None:
    for _ in range(n_sessions):
        lg = TelemetryLogger(player_id=f"p{random.randint(1, 8)}")
        lg.log("session_start", level="L1")
        for _ in range(random.randint(3, 15)):
            lg.log(random.choice(["death", "checkpoint", "item_pickup"]), level="L1",
                   x=random.uniform(0, 100), y=random.uniform(0, 100))
        lg.log(random.choice(["level_complete", "session_end"]), level="L1")
        lg.flush()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", type=int, default=0)
    a = ap.parse_args()
    if a.simulate:
        simulate(a.simulate)
        print(f"Сгенерировано {a.simulate} сессий → {OUT}")
