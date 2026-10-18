"""The four predefined tools. These are the only code paths that write request data.

Each tool takes the shared `state` dict and returns a plain dict. The model only ever
chooses a tool *name*; it never produces SQL, code, or anything that is executed.
"""
import os
import re

import httpx  # installed with the ollama client; needed to catch its connection error
import ollama
from pydantic import ValidationError

from app import db
from app.schemas import ExtractedFields, FollowupDraft

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b")
client = ollama.Client(host=OLLAMA_HOST)


class OllamaUnavailable(RuntimeError):
    pass


def ask_llm(system: str, user: str, schema: dict) -> str:
    """One chat call constrained to a JSON schema, so the reply always parses."""
    try:
        response = client.chat(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            format=schema,
            # temperature 0: repeatable output matters more than creativity here.
            # num_predict: small models can loop endlessly; a hard cap turns that into a catchable error.
            options={"temperature": 0, "num_predict": 400},
        )
    except (ConnectionError, httpx.ConnectError) as error:
        raise OllamaUnavailable(
            f"Cannot reach Ollama at {OLLAMA_HOST}. Start it with `ollama serve` and try again."
        ) from error
    except ollama.ResponseError as error:
        raise OllamaUnavailable(
            f"Ollama error: {error.error}. If the model is missing, run `ollama pull {MODEL_NAME}`."
        ) from error
    return response.message.content


EXTRACTION_PROMPT = """You extract structured fields from customer requests sent to a home-help service
for elderly people (shopping, transport, companionship, household help). Requests may be English or German.

Rules:
- service_type: shopping (buying or picking up things and bringing them to the person: groceries,
  medication from the pharmacy, parcels), transport (driving the person somewhere),
  companionship (visits, sitting with someone, checking on someone, walks, social time),
  household (cleaning, laundry, tidying, unpacking), other (anything else, or unclear what help is needed).
- when_needed: the concrete day or time the help is needed, copied from the text ("today", "Monday 9:30",
  "next week", "the 24th"). null if no day is given or it is vague ("later", "after the summer", "next year",
  "now and then", "sometime").
- urgency: high = safety or health risk, or help is needed today / tonight / right now.
  medium = needed on a later concrete day (tomorrow, Monday, this week, next week), even for medical appointments.
  low = general question, information or price request, or no time pressure.
- callback_requested: true only if the person explicitly asks to be called / called back.
- preferred_contact_time: morning, afternoon or evening only if they say when staff should contact them.
  Appointment times are not contact times. Otherwise null.
- location: a city name only, exactly as written. null if no city is named ("near the station" is not a city).
- summary: one short English sentence."""


def extract_fields(state: dict) -> dict:
    raw = ask_llm(EXTRACTION_PROMPT, state["text"], ExtractedFields.model_schema_for_llm())
    fields = ExtractedFields.model_validate_json(raw).model_dump()
    state["fields"] = fields
    db.update_request(state["request_id"], **fields)
    return fields


def check_missing_info(state: dict) -> dict:
    # Fixed rules over extracted facts: a 3B model judges "is something missing?" poorly (20% in the
    # first eval), but it reliably extracts whether a city or a day was mentioned.
    fields = state["fields"]
    missing = []
    if not fields["location"]:
        missing.append("location")
    if not fields["when_needed"]:
        missing.append("date")
    if fields["service_type"] == "other":
        missing.append("details")
    fields["missing_info"] = missing
    db.update_request(state["request_id"], missing_info=missing)
    return {"missing_info": missing}


DRAFT_PROMPT = """You write short, friendly follow-up messages for a home-help service.
Write in the same language as the customer's request (English or German). At most 4 sentences.
Thank them and repeat back what they asked for. If information is missing, ask for it. If they asked for
a callback, say a colleague will call them. Nothing is booked yet: never say a booking or appointment is
confirmed, and do not promise a specific helper, time, or price. Sign as "Your HOMECARE team"."""


def draft_followup(state: dict) -> dict:
    fields = state["fields"]
    user_message = (
        f"Customer request:\n{state['text']}\n\n"
        f"Missing information to ask for: {', '.join(fields['missing_info']) or 'none'}\n"
        f"Callback requested: {fields['callback_requested']}"
    )
    draft = FollowupDraft.model_validate_json(
        ask_llm(DRAFT_PROMPT, user_message, FollowupDraft.model_json_schema())
    ).message
    # Never sent from here: a human must approve it in the dashboard.
    db.update_request(state["request_id"], followup_draft=draft, followup_status="pending_approval")
    return {"followup_draft": draft, "followup_status": "pending_approval"}


SAME_DAY = re.compile(r"\b(today|tonight|this (afternoon|evening)|right now|asap|heute|sofort)\b", re.IGNORECASE)


def set_priority(state: dict) -> dict:
    # Fixed rules instead of model judgement, so staff can predict and explain the ordering.
    fields = state["fields"]
    result = {}
    # Safety floor: same-day need is high urgency by definition. The rule can only raise urgency,
    # never lower it, because missing an urgent case is worse than over-triaging a normal one.
    when_needed = fields["when_needed"] or ""
    if fields["urgency"] != "high" and SAME_DAY.search(when_needed):
        result["urgency_raised_from"] = fields["urgency"]
        fields["urgency"] = "high"
    elif fields["urgency"] == "low" and when_needed:  # a concrete day means at least medium
        result["urgency_raised_from"] = "low"
        fields["urgency"] = "medium"
    base = {"high": 1, "medium": 2, "low": 4}[fields["urgency"]]
    priority = 1 if base == 1 else base + (0 if fields["callback_requested"] else 1)
    db.update_request(state["request_id"], priority=priority, urgency=fields["urgency"])
    return {**result, "urgency": fields["urgency"], "priority": priority}


TOOLS = {
    "extract_fields": (extract_fields, "Read the request and extract the structured fields. Must run first."),
    "check_missing_info": (check_missing_info, "Verify which information staff still need from the customer."),
    "draft_followup": (draft_followup, "Draft a reply to the customer for a human to approve."),
    "set_priority": (set_priority, "Assign a work priority (1 = handle first, 5 = can wait)."),
}


def run_tool(name: str, state: dict) -> dict:
    """Execute a whitelisted tool and write the call to the audit log."""
    function, _ = TOOLS[name]
    tool_input = {"text": state["text"], "fields": dict(state.get("fields") or {})}
    try:
        output = function(state)
    except ValidationError as error:
        # Model output did not match the schema (e.g. truncated). Record it and let the agent carry on.
        output = {"error": f"invalid model output: {error.errors()[0]['msg']}"}
        db.log_audit(state["request_id"], "tool_error", tool=name, input_data=tool_input, output_data=output)
        return output
    db.log_audit(state["request_id"], "tool_call", tool=name, input_data=tool_input, output_data=output)
    return output
