"""Приём игровых событий и запись в PostgreSQL."""

from typing import Annotated, Literal, Self

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from server.database import SessionLocal
from server.models import Event

app = FastAPI(title="Game telemetry")


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, str_strip_whitespace=True)

    session_id: str = Field(min_length=1, max_length=64)
    player_id: str = Field(min_length=1, max_length=64)
    event_type: Literal["session_start", "death", "checkpoint", "level_complete", "session_end"]
    ts: float = Field(ge=0)
    level: str = Field(min_length=1, max_length=32)
    x: float | None = None
    y: float | None = None
    cause: str | None = Field(default=None, min_length=1, max_length=64)
    time_s: float | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def check_event_fields(self) -> Self:
        if (self.x is None) != (self.y is None):
            raise ValueError("Координаты x и y должны передаваться вместе")
        if self.event_type == "death" and self.x is None:
            raise ValueError("Для death обязательны координаты x и y")
        if self.cause is not None and self.event_type != "death":
            raise ValueError("cause используется только для death")
        if self.time_s is not None and self.event_type != "level_complete":
            raise ValueError("time_s используется только для level_complete")
        if self.reason is not None and self.event_type != "session_end":
            raise ValueError("reason используется только для session_end")
        return self


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Не возвращаем исходные значения: NaN/Infinity нельзя сериализовать в ответ JSON.
    details = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with SessionLocal() as session:
            session.scalar(select(Event.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="База данных или таблица events недоступна") from None
    return {"status": "ok", "database": "ok"}


@app.post("/events", status_code=201)
def ingest(events: Annotated[list[EventIn], Body(min_length=1)]) -> dict[str, int]:
    with SessionLocal() as session:
        try:
            session.add_all([Event(**event.model_dump()) for event in events])
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            raise HTTPException(status_code=503, detail="Не удалось сохранить события") from None
    return {"accepted": len(events)}
