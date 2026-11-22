import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Reviews Analyzer API",
    description="API системы анализа отзывов клиентов",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "Reviews Analyzer API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


if prototype_dir := os.getenv("PROTOTYPE_DIR"):
    app.mount("/prototype", StaticFiles(directory=Path(prototype_dir), html=True))
