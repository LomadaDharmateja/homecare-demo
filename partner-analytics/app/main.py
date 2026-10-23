"""HTTP API for n8n and other tools. Run: python -m uvicorn app.main:app --port 8001"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .ask import OllamaUnavailable, ask
from .report import build_alerts, weekly_report

app = FastAPI(title="HOMECARE partner analytics (demo, fictional data)")


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=300)


@app.post("/ask")
def ask_endpoint(body: Question):
    try:
        return ask(body.question)
    except OllamaUnavailable as e:
        raise HTTPException(503, str(e))


@app.get("/report/weekly")
def report_endpoint():
    return weekly_report()


@app.get("/alerts")
def alerts_endpoint():
    alerts, month, young = build_alerts()
    return {"month": month, "count": len(alerts), "young_locations": young, "alerts": alerts}
