from fastapi import FastAPI

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
