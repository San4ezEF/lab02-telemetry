"""Запись событий в JSONL и отправка пакетов на сервер."""

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

SERVER = "http://localhost:8000/events"
OUT = Path(__file__).resolve().parents[1] / "data" / "events.jsonl"
EVENT_TYPES = {"session_start", "death", "checkpoint", "level_complete", "session_end"}


class TelemetryLogger:
    def __init__(
        self, player_id: str, batch_size: int = 20, send_http: bool = True,
        *, server_url: str = SERVER, output: Path = OUT, session_id: str | None = None,
    ):
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size должен быть положительным целым числом")
        self.session_id = session_id if session_id is not None else uuid.uuid4().hex
        self.player_id = player_id
        self.batch_size = batch_size
        self.send_http = send_http
        self.server_url = server_url
        self.output = Path(output)
        self.buffer: list[dict] = []
        self.send_failed = False
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, *, level: str, ts: float | None = None, **fields) -> None:
        if self.send_failed:
            raise RuntimeError("Логгер остановлен после ошибки отправки; проверьте JSONL и сервер")
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Неизвестный тип события: {event_type}")
        if fields.keys() - {"x", "y", "cause", "time_s", "reason"}:
            raise ValueError("Переданы неизвестные или служебные поля события")
        event = {
            "session_id": self.session_id,
            "player_id": self.player_id,
            "event_type": event_type,
            "ts": time.time() if ts is None else ts,
            "level": level,
            **fields,
        }
        line = json.dumps(event, ensure_ascii=False, allow_nan=False)
        with self.output.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
        self.buffer.append(event)
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if self.send_failed:
            raise RuntimeError("Повторная отправка заблокирована: предыдущий пакет мог сохраниться в БД")
        if not self.buffer:
            return
        if self.send_http:
            try:
                with requests.post(
                    self.server_url, json=list(self.buffer), timeout=5, allow_redirects=False,
                ) as response:
                    response.raise_for_status()
                    if response.status_code != 201 or response.json() != {"accepted": len(self.buffer)}:
                        raise ValueError("Некорректное подтверждение сервера")
            except (requests.RequestException, ValueError) as exc:
                self.send_failed = True
                raise RuntimeError(
                    f"Отправка не подтверждена. События сохранены в {self.output}; "
                    "перед повтором проверьте БД, чтобы не создать дубликаты"
                ) from exc
        self.buffer.clear()


def demo(logger: TelemetryLogger) -> None:
    start = time.time() - 300
    logger.log("session_start", level="L1", ts=start)
    logger.log("death", level="L1", ts=start + 42.5, x=12.4, y=3.1, cause="spikes")
    logger.log("checkpoint", level="L1", ts=start + 90, x=40.0, y=5.0)
    logger.log("level_complete", level="L1", ts=start + 155, time_s=155)
    logger.log("session_end", level="L1", ts=start + 300, reason="quit")
    logger.flush()


def simulate(
    n_sessions: int, *, seed: int = 42, send_http: bool = True,
    server_url: str = SERVER, output: Path = OUT,
) -> str:
    if isinstance(n_sessions, bool) or not isinstance(n_sessions, int) or n_sessions < 20:
        raise ValueError("Для симуляции нужно не менее 20 сессий")
    random.seed(seed)
    run_id = "sim_" + uuid.uuid4().hex
    first_day = datetime(2026, 9, 1, 10, tzinfo=timezone.utc).timestamp()
    n_players = n_sessions * 3 // 5
    d1_players = (n_sessions - n_players) // 2

    for index in range(n_sessions):
        if index < n_players:
            player = index
            day = 0
        else:
            player = index - n_players
            day = 1 if player < d1_players else 2
        start = first_day + day * 86400 + (player % 12) * 1200
        level = "L1" if player % 2 == 0 else "L2"
        outcome = index % 5
        reached_checkpoint = outcome != 0
        completed = outcome >= 3
        if completed:
            duration = random.randint(330, 420)
        elif reached_checkpoint:
            duration = random.randint(210, 270)
        else:
            duration = random.randint(90, 120)

        events = []
        for death_index in range(random.randint(1, 3)):
            main_cluster = (index + death_index) % 4 != 0
            if main_cluster:
                center = (12.5, 3.0) if level == "L1" else (70.0, 12.0)
                cause = "spikes"
            else:
                center = (45.0, 20.0) if level == "L1" else (30.0, 35.0)
                cause = "enemy"
            offset = 20 + death_index * 20
            if reached_checkpoint and death_index > 0:
                offset += 100
            events.append((offset, "death", {
                "x": round(random.gauss(center[0], 1.0), 2),
                "y": round(random.gauss(center[1], 0.8), 2),
                "cause": cause,
            }))
        if reached_checkpoint:
            events.append((90, "checkpoint", {"x": 40.0, "y": 5.0}))
        if completed:
            events.append((duration - 20, "level_complete", {"time_s": duration - 20}))

        logger = TelemetryLogger(
            player_id=f"{run_id}_p{player + 1}", session_id=f"{run_id}_s{index + 1}",
            send_http=send_http, server_url=server_url, output=output,
        )
        logger.log("session_start", level=level, ts=start)
        for offset, event_type, fields in sorted(events, key=lambda event: event[0]):
            logger.log(event_type, level=level, ts=start + offset, **fields)
        logger.log("session_end", level=level, ts=start + duration, reason="completed" if completed else "quit")
        logger.flush()
    return run_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="Создать одну сессию из пяти событий")
    mode.add_argument("--simulate", type=int, metavar="N", help="Сгенерировать N сессий (минимум 20)")
    parser.add_argument("--seed", type=int, default=42, help="Начальное состояние генератора случайных чисел")
    parser.add_argument("--no-http", action="store_true", help="Записывать только JSONL")
    parser.add_argument("--url", default=SERVER, help="Адрес POST /events")
    parser.add_argument("--output", type=Path, default=OUT, help="Путь к JSONL")
    args = parser.parse_args()
    if not args.demo and args.simulate is None:
        parser.print_help()
    else:
        try:
            if args.simulate is not None:
                run_id = simulate(
                    args.simulate, seed=args.seed, send_http=not args.no_http,
                    server_url=args.url, output=args.output,
                )
                summary = f"{args.simulate} сессий; seed={args.seed}; run_id={run_id}"
            else:
                logger = TelemetryLogger(
                    player_id="demo_player", send_http=not args.no_http,
                    server_url=args.url, output=args.output,
                )
                demo(logger)
                summary = f"5 событий; session_id={logger.session_id}"
        except (OSError, ValueError, RuntimeError) as exc:
            parser.exit(1, f"Ошибка: {exc}\n")
        destination = "JSONL" if args.no_http else "JSONL и PostgreSQL"
        print(f"{summary} → {destination}")
