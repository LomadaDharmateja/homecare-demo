"""The four predefined tools. These are the only code paths that write request data.

Each tool takes the shared `state` dict and returns a plain dict. The model only ever
chooses a tool *name*; it never produces SQL, code, or anything that is executed.
"""
import difflib
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
- service_type: shopping = buying or picking up things and bringing them to the person (groceries,
  medication from the pharmacy, glasses from the optician, parcels), even if it is a medical emergency.
  transport = driving the person themselves somewhere. companionship = visits, sitting or staying with someone,
  checking on someone, walks, social time. household = cleaning, laundry, tidying, packing, unpacking.
  other = anything else, or unclear what help is needed. A question about the price of a named service
  still gets that service's type.
- when_needed: the words in the request that say on which day or time help is needed, copied word for word
  in the request's language. null if no day is given or the timing is vague.
- urgency: high = safety or health risk, or help is needed today / tonight / right now.
  medium = needed on a later concrete day, even for medical appointments.
  low = general question, information or price request, or no time pressure.
- callback_requested: true only if the person explicitly asks to be called / called back.
- preferred_contact_time: morning, afternoon or evening only if they say when staff should call or reach them.
  Appointment or service times are not contact times. Otherwise null.
- location: a city name only, exactly as written. null if no city is named.
- summary: one short English sentence.

Examples (not real customers):
Request: "Could someone pick up my mother's prescription from the pharmacy in Aachen tomorrow and drop it at her flat?"
-> service_type shopping, when_needed "tomorrow", urgency medium, callback_requested false, preferred_contact_time null, location "Aachen"
Request: "Mein Vater ist gestürzt und hat Angst. Kann heute Abend jemand bei ihm in Siegen bleiben? Rufen Sie mich bitte sofort zurück."
-> service_type companionship, when_needed "heute Abend", urgency high, callback_requested true, preferred_contact_time null, location "Siegen"
Request: "My husband has a dentist appointment on Friday at 4 pm in Hamm and needs a lift."
-> service_type transport, when_needed "Friday at 4 pm", urgency medium, callback_requested false, preferred_contact_time null, location "Hamm"
Request: "What does your cleaning service cost? My aunt in Kleve may need it some time next year. Please call me in the evening."
-> service_type household, when_needed null, urgency low, callback_requested true, preferred_contact_time "evening", location "Kleve\""""

# Grounding rules. The model is good at spotting facts but sometimes invents or garbles them, so each
# extracted fact must be backed by the customer's own words.
VAGUE_TIMING = re.compile(
    r"\b(later|eventually|some ?day|some ?time|at some point|in the future|next year|now and then|sometimes|"
    r"coming months|after the summer|no rush|for now|irgendwann|später|nächste\w* jahr|gelegentlich|keine eile)\b",
    re.IGNORECASE,
)
CALL_WORDS = re.compile(r"\b(call|ring|phone me|anrufen|anruf|rufen|zurückrufen|rückruf|telefon)", re.IGNORECASE)
# Concrete day/time expressions, used as a backstop when the model leaves when_needed empty.
# "morgen" (tomorrow) is matched case-sensitively so "Guten Morgen" / "heute Morgen" do not count as tomorrow.
WEEKDAYS = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag"
TIME_PHRASES = re.compile(
    r"\b(today|tonight|tomorrow( morning| afternoon| evening)?|right now|asap|immediately|"
    r"this (morning|afternoon|evening|week|weekend|month)|next (week|month|couple of days|few days)|"
    rf"(next |on |this )?({WEEKDAYS})s?|the \d{{1,2}}(st|nd|rd|th)|am \d{{1,2}}(?=\.)|\d{{1,2}}(:\d\d)? ?(am|pm|uhr)|"
    r"heute( abend| nachmittag| noch)?|(?-i:morgen)|übermorgen|sofort|jetzt|diese woche|nächste\w* woche|"
    r"am wochenende|dieses wochenende)\b",
    re.IGNORECASE,
)
RELATIVE_PLACE = re.compile(r"(near|close to|next to|around|bei|nahe|neben|in der nähe)\b", re.IGNORECASE)
CONTACT_WORDS = re.compile(CALL_WORDS.pattern + r"|\b(reach|contact|erreichbar|erreichen|melden)", re.IGNORECASE)


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def ground_in_text(fields: dict, text: str) -> dict:
    """Check extracted facts against the request text; returns {field: [old, new]} for every correction."""
    text_words = _words(text)
    corrections = {}

    def correct(field, new_value):
        if fields[field] != new_value:
            corrections[field] = [fields[field], new_value]
            fields[field] = new_value

    for field in ("when_needed", "location"):  # small models sometimes write the string "null"
        if isinstance(fields[field], str) and fields[field].strip().lower() in ("", "null", "none"):
            correct(field, None)

    when = fields["when_needed"]
    if when:
        # Every word of the phrase must (nearly) appear in the text, otherwise it was invented.
        grounded = all(difflib.get_close_matches(word, text_words, n=1, cutoff=0.8) for word in _words(when))
        if not grounded or VAGUE_TIMING.search(when):
            correct("when_needed", None)
    if not fields["when_needed"]:
        found = [match.group(0) for match in TIME_PHRASES.finditer(text)]
        if found:
            correct("when_needed", ", ".join(found))

    location = fields["location"]
    if location and RELATIVE_PLACE.match(location):  # "near the station" describes a place, it is not a city
        correct("location", None)
    elif location and location.lower() not in text.lower():
        # Snap a misspelt copy ("henne") to the closest word the customer actually wrote ("herne").
        match = difflib.get_close_matches(location.lower(), text_words, n=1, cutoff=0.75)
        correct("location", next((w for w in re.findall(r"\w+", text) if w.lower() == match[0]), None) if match else None)

    if fields["callback_requested"] and not CALL_WORDS.search(text):
        correct("callback_requested", False)
    if fields["preferred_contact_time"] and not CONTACT_WORDS.search(text):
        correct("preferred_contact_time", None)
    return corrections


def extract_fields(state: dict) -> dict:
    raw = ask_llm(EXTRACTION_PROMPT, state["text"], ExtractedFields.model_schema_for_llm())
    fields = ExtractedFields.model_validate_json(raw).model_dump()
    corrections = ground_in_text(fields, state["text"])
    state["fields"] = fields
    db.update_request(state["request_id"], **fields)
    # The audit log keeps both what the model said and what the grounding rules changed.
    return {**fields, "grounding_corrections": corrections} if corrections else fields


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


DRAFT_PROMPT = """You write short, friendly follow-up messages for a home-help service for elderly people.
The service offers exactly four things: shopping and errands, transport to appointments, companionship
visits, and household help (cleaning, laundry, tidying). Never mention any other service.
Write in the same language as the customer's request (English or German). At most 4 sentences.
Thank them and repeat back what they asked for. If information is missing, ask for it. If they asked for
a callback, say a colleague will call them. Nothing is booked yet: never say a booking or appointment is
confirmed, and do not promise a specific helper, time, or price. Sign as "Your HOMECARE team"."""


def _looks_german(text: str) -> bool:
    return len(set(_words(text)) & {"und", "ich", "die", "der", "nicht", "bitte", "meine", "mein", "sie", "ist"}) >= 2


def draft_followup(state: dict) -> dict:
    fields = state["fields"]
    user_message = (
        f"Customer request:\n{state['text']}\n\n"
        f"Missing information to ask for: {', '.join(fields['missing_info']) or 'none'}\n"
        f"Callback requested: {fields['callback_requested']}"
    )
    draft = FollowupDraft.model_validate_json(
        ask_llm(DRAFT_PROMPT, user_message, FollowupDraft.model_json_schema())
    ).message.strip()
    if not re.search(r"homecare[ -]team", draft, re.IGNORECASE):  # the model sometimes drops the sign-off
        draft += "\n\nIhr HOMECARE-Team" if _looks_german(state["text"]) else "\n\nYour HOMECARE team"
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
