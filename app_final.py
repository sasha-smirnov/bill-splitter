"""Bill Splitter — сервис для разделения общего счёта в компании."""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator

APP_VERSION = "0.2.0"

# Настройки из переменных окружения 
APP_NAME = os.getenv("APP_NAME", "Bill Splitter")
CURRENCY = os.getenv("CURRENCY", "RUB")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Логирование
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


# Модели данных
class ExpenseIn(BaseModel):
    """Одна трата: кто заплатил, сколько и за кого."""

    description: str = Field(min_length=1, examples=["Пицца"])
    payer: str = Field(min_length=1, examples=["Аня"])
    amount: float = Field(gt=0, examples=[1500])
    shared_by: list[str] | None = Field(
        default=None,
        description="Кто делит эту трату. Если не указано — все участники.",
        examples=[["Аня", "Борис"]],
    )


class BillCreate(BaseModel):
    """Новый счёт: название, участники и траты."""

    title: str = Field(min_length=1, examples=["Пятница в пиццерии"])
    participants: list[str] = Field(min_length=2, examples=[["Аня", "Борис", "Вика"]])
    expenses: list[ExpenseIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_names(self):
        if len(set(self.participants)) != len(self.participants):
            raise ValueError("Имена участников должны быть уникальными")
        for expense in self.expenses:
            check_expense_names(expense, self.participants)
        return self


def check_expense_names(expense: ExpenseIn, participants: list[str]) -> None:
    """Проверяет, что плательщик и все, кто делит трату, есть среди участников."""
    if expense.payer not in participants:
        raise ValueError(f"Плательщик '{expense.payer}' не входит в участников счёта")
    for name in expense.shared_by or []:
        if name not in participants:
            raise ValueError(f"Участник '{name}' из shared_by не входит в счёт")
    if expense.shared_by == []:
        raise ValueError("shared_by не может быть пустым списком")


# Хранилище в памяти
bills: dict[int, dict] = {}
next_bill_id = 1


def save_bill(data: BillCreate) -> dict:
    global next_bill_id
    bill = {
        "id": next_bill_id,
        "title": data.title,
        "participants": data.participants,
        "expenses": [expense.model_dump() for expense in data.expenses],
    }
    bills[next_bill_id] = bill
    next_bill_id += 1
    return bill


def get_bill_or_404(bill_id: int) -> dict:
    bill = bills.get(bill_id)
    if bill is None:
        logger.warning("Счёт %s не найден", bill_id)
        raise HTTPException(status_code=404, detail=f"Счёт {bill_id} не найден")
    return bill


def bill_total(bill: dict) -> float:
    return round(sum(expense["amount"] for expense in bill["expenses"]), 2)


# Демонстрационный счёт
save_bill(BillCreate(
    title="Демо: пицца у Ани",
    participants=["Аня", "Борис", "Вика"],
    expenses=[
        ExpenseIn(description="Пицца", payer="Аня", amount=2400),
        ExpenseIn(description="Напитки", payer="Борис", amount=600),
        ExpenseIn(description="Десерт", payer="Вика", amount=450, shared_by=["Аня", "Вика"]),
    ],
))


# Служебные маршруты
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


# Счета
@app.get("/bills")
def list_bills(participant: str | None = Query(default=None, description="Показать только счета с этим участником")):
    result = [
        {
            "id": bill["id"],
            "title": bill["title"],
            "participants": bill["participants"],
            "total": bill_total(bill),
            "currency": CURRENCY,
        }
        for bill in bills.values()
        if participant is None or participant in bill["participants"]
    ]
    return {"count": len(result), "bills": result}


@app.post("/bills", status_code=201)
def create_bill(data: BillCreate):
    bill = save_bill(data)
    logger.info(
        "Создан счёт %s '%s': %s участников, %s трат",
        bill["id"], bill["title"], len(bill["participants"]), len(bill["expenses"]),
    )
    return {**bill, "total": bill_total(bill), "currency": CURRENCY}


@app.get("/bills/{bill_id}")
def get_bill(bill_id: int):
    bill = get_bill_or_404(bill_id)
    return {**bill, "total": bill_total(bill), "currency": CURRENCY}


@app.post("/bills/{bill_id}/expenses", status_code=201)
def add_expense(bill_id: int, expense: ExpenseIn):
    bill = get_bill_or_404(bill_id)
    try:
        check_expense_names(expense, bill["participants"])
    except ValueError as error:
        logger.warning("Трата не добавлена в счёт %s: %s", bill_id, error)
        raise HTTPException(status_code=422, detail=str(error))
    bill["expenses"].append(expense.model_dump())
    logger.info("В счёт %s добавлена трата '%s' на %s", bill_id, expense.description, expense.amount)
    return {**bill, "total": bill_total(bill), "currency": CURRENCY}


@app.delete("/bills/{bill_id}", status_code=204)
def delete_bill(bill_id: int):
    get_bill_or_404(bill_id)
    del bills[bill_id]
    logger.info("Счёт %s удалён", bill_id)


def to_cents(value: float) -> int:
    return int(round(value * 100))


def calculate_split(bill: dict, tip_percent: float) -> dict:
    people = bill["participants"]
    paid = {name: 0 for name in people}
    share = {name: 0 for name in people}

    for expense in bill["expenses"]:
        amount = to_cents(expense["amount"] * (1 + tip_percent / 100))
        sharers = expense["shared_by"] or people
        paid[expense["payer"]] += amount
        base, remainder = divmod(amount, len(sharers))
        for index, name in enumerate(sharers):
            share[name] += base + (1 if index < remainder else 0)

    balance = {name: paid[name] - share[name] for name in people}

   
    debtors = sorted(([n, -b] for n, b in balance.items() if b < 0), key=lambda x: -x[1])
    creditors = sorted(([n, b] for n, b in balance.items() if b > 0), key=lambda x: -x[1])
    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][1], creditors[j][1])
        transfers.append({"from": debtors[i][0], "to": creditors[j][0], "amount": amount / 100})
        debtors[i][1] -= amount
        creditors[j][1] -= amount
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    return {
        "bill_id": bill["id"],
        "title": bill["title"],
        "currency": CURRENCY,
        "tip_percent": tip_percent,
        "total": sum(paid.values()) / 100,
        "people": [
            {
                "name": name,
                "paid": paid[name] / 100,
                "share": share[name] / 100,
                "balance": balance[name] / 100,
            }
            for name in people
        ],
        "transfers": transfers,
    }


@app.get("/bills/{bill_id}/split")
def split_bill(
    bill_id: int,
    tip: float | None = Query(
        default=None, ge=0, le=100,
        description="Чаевые в процентах. Если не указано — DEFAULT_TIP_PERCENT.",
    ),
):
    bill = get_bill_or_404(bill_id)
    tip_percent = DEFAULT_TIP_PERCENT if tip is None else tip
    result = calculate_split(bill, tip_percent)
    logger.info(
        "Расчёт счёта %s: итого %s %s, чаевые %s%%, переводов %s",
        bill_id, result["total"], CURRENCY, tip_percent, len(result["transfers"]),
    )
    return result
