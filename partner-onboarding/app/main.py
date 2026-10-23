"""HTTP API for n8n. Run: python -m uvicorn app.main:app --port 8003"""
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import service

app = FastAPI(title="HOMECARE Onboarding-Cockpit (Demo, erfundene Partner)")


class Update(BaseModel):
    partner_id: int
    nachricht: str = Field(min_length=3, max_length=2000)
    quelle: str = "E-Mail"


class Entscheidung(BaseModel):
    freigeben: bool
    von: str = Field(min_length=2)
    punkte: Optional[list[str]] = None  # only these task ids; None = all proposed changes


@app.get("/partner")
def partner():
    return [{k: v for k, v in p.items() if k != "tasks"} for p in service.overview()]


@app.post("/updates")
def update(body: Update):
    """A partner's free-text update -> proposal. Changes nothing until a person approves it."""
    try:
        return service.submit_update(body.partner_id, body.nachricht, body.quelle)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.get("/vorschlaege")
def vorschlaege():
    return service.pending()


@app.post("/vorschlaege/{proposal_id}/entscheidung")
def entscheidung(proposal_id: int, body: Entscheidung):
    try:
        return service.decide(proposal_id, body.freigeben, body.von, body.punkte)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/risiken")
def risiken():
    return service.risks()


@app.get("/protokoll")
def protokoll(limit: int = 50):
    return service.audit_log(limit)
