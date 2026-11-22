import os
from urllib.error import URLError
from urllib.request import urlopen

import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Reviews Analyzer dev stub")


@app.get("/health")
def health():
    service = os.environ["DEV_SERVICE"]
    try:
        if service == "storage":
            with psycopg.connect(connect_timeout=2) as connection:
                connection.execute("SELECT 1 FROM analysis_runs LIMIT 1")
        for url in filter(None, os.getenv("DEV_DEPENDENCIES", "").split(",")):
            with urlopen(url, timeout=1):
                pass
    except (psycopg.Error, URLError, TimeoutError) as error:
        raise HTTPException(503, "Dev dependency unavailable") from error

    return {"status": "ok", "service": service, "mode": "stub"}
