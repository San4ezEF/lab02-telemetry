"""Запись событий в JSONL и отправка пакетов на сервер."""

import argparse
import json
import time
import uuid
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Создать одну сессию из пяти событий")
    parser.add_argument("--no-http", action="store_true", help="Записывать только JSONL")
    parser.add_argument("--url", default=SERVER, help="Адрес POST /events")
    parser.add_argument("--output", type=Path, default=OUT, help="Путь к JSONL")
    args = parser.parse_args()
    if not args.demo:
        parser.print_help()
    else:
        try:
            logger = TelemetryLogger(
                player_id="demo_player", send_http=not args.no_http,
                server_url=args.url, output=args.output,
            )
            demo(logger)
        except (OSError, ValueError, RuntimeError) as exc:
            parser.exit(1, f"Ошибка: {exc}\n")
        destination = "JSONL" if args.no_http else "JSONL и PostgreSQL"
        print(f"5 событий → {destination}; session_id={logger.session_id}")
