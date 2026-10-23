"""Bill Splitter — сервис для разделения общего счёта в компании."""

from fastapi import FastAPI

APP_VERSION = "0.1.0"

app = FastAPI(title="Bill Splitter", version=APP_VERSION)


@app.get("/")
def root():
    return {"message": "Сервис работает"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": APP_VERSION}
