"""Модель таблицы игровых событий."""

import sys

from sqlalchemy import BigInteger, CheckConstraint, Double, Identity, String
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('session_start', 'death', 'checkpoint', 'level_complete', 'session_end')",
            name="ck_events_event_type",
        ),
        CheckConstraint("ts >= 0", name="ck_events_ts"),
        CheckConstraint("time_s >= 0", name="ck_events_time_s"),
        CheckConstraint("(x IS NULL) = (y IS NULL)", name="ck_events_coordinates_pair"),
        CheckConstraint("event_type <> 'death' OR x IS NOT NULL", name="ck_events_death_coordinates"),
        {"schema": "public"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    player_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    ts: Mapped[float] = mapped_column(Double)
    level: Mapped[str] = mapped_column(String(32))
    x: Mapped[float | None] = mapped_column(Double)
    y: Mapped[float | None] = mapped_column(Double)
    cause: Mapped[str | None] = mapped_column(String(64))
    time_s: Mapped[float | None] = mapped_column(Double)
    reason: Mapped[str | None] = mapped_column(String(64))


if __name__ == "__main__":
    from server.database import engine

    try:
        Base.metadata.create_all(engine)
        print("Таблица public.events готова.")
    except SQLAlchemyError:
        sys.exit("Не удалось создать таблицу. Проверьте подключение и права на схему public.")
    finally:
        engine.dispose()
