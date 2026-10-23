"""HTTP API (for n8n / a Telegram bot). Run: python -m uvicorn app.main:app --port 8002"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import assistant

app = FastAPI(title="HOMECARE Partnerhandbuch-Assistent (Demo, fiktives Handbuch)")


class Frage(BaseModel):
    frage: str = Field(min_length=3, max_length=500)


@app.post("/frage")
def frage(body: Frage):
    try:
        return assistant.ask(body.frage)
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.get("/wissensluecken")
def wissensluecken():
    gaps = assistant.knowledge_gaps()
    return {"count": len(gaps), "items": gaps}
