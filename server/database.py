"""Подключение к PostgreSQL и фабрика сессий SQLAlchemy."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"Задайте {name} в .env или переменных окружения")
    return value


def database_url() -> URL:
    try:
        port = int(required_env("DB_PORT"))
    except ValueError as exc:
        raise ValueError("DB_PORT должен быть целым числом от 1 до 65535") from exc
    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT должен быть целым числом от 1 до 65535")

    return URL.create(
        drivername="postgresql+psycopg",
        username=required_env("DB_USER"),
        password=required_env("DB_PASSWORD"),
        host=required_env("DB_HOST"),
        port=port,
        database=required_env("DB_NAME"),
    )


engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine)


if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            row = connection.execute(text("SELECT current_database(), current_user")).one()
            print(f"Подключение успешно: database={row[0]}, user={row[1]}")
    except SQLAlchemyError:
        sys.exit("Подключение не удалось. Проверьте службу PostgreSQL и параметры DB_* в .env.")
    finally:
        engine.dispose()
