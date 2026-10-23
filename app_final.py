"""Bill Splitter — сервис для разделения общего счёта в компании."""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

APP_VERSION = "0.1.0"

# --- Настройки из переменных окружения ---------------------------------
APP_NAME = os.getenv("APP_NAME", "Bill Splitter")
CURRENCY = os.getenv("CURRENCY", "RUB")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Логирование ---------------------------------------------------------
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("bill_splitter")


def read_tip_percent() -> float:
    """Читает DEFAULT_TIP_PERCENT; при ошибке пишет предупреждение и берёт 0."""
    raw = os.getenv("DEFAULT_TIP_PERCENT", "0")
    try:
        value = float(raw)
    except ValueError:
        logger.warning("DEFAULT_TIP_PERCENT=%r не число, используется 0", raw)
        return 0.0
    if not 0 <= value <= 100:
        logger.warning("DEFAULT_TIP_PERCENT=%s вне диапазона 0–100, используется 0", value)
        return 0.0
    return value


DEFAULT_TIP_PERCENT = read_tip_percent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Запуск %s v%s (валюта=%s, чаевые по умолчанию=%s%%)",
        APP_NAME, APP_VERSION, CURRENCY, DEFAULT_TIP_PERCENT,
    )
    yield
    logger.info("Остановка %s", APP_NAME)


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


@app.get("/")
def root():
    return {"message": "Сервис работает", "app_name": APP_NAME}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": APP_VERSION}


@app.get("/info")
def info():
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "currency": CURRENCY,
        "default_tip_percent": DEFAULT_TIP_PERCENT,
    }
