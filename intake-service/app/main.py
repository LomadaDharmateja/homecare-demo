"""FastAPI entry point. Start with: uvicorn app.main:app --port 8000"""
from fastapi import FastAPI, HTTPException

from app import db
from app.agent import process_request
from app.schemas import IntakeIn
from app.tools import OllamaUnavailable

app = FastAPI(title="HOMECARE intake service (demo)")
db.init_db()


@app.post("/intake")
def intake(request: IntakeIn) -> dict:
    try:
        return process_request(request)
    except OllamaUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error))


@app.get("/overdue")
def overdue() -> dict:
    items = db.list_overdue()
    # n8n's IF node only needs the count; the list is there for the summary file.
    return {"count": len(items), "items": items}


@app.get("/requests")
def requests() -> list[dict]:
    return db.list_requests()
