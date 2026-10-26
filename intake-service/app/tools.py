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
- summary: one short sentence in German (the office team reads German), even if the request is English.

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
# "morgen" alone means "tomorrow" and "Guten Morgen" is a greeting, so only "morgens" counts as morning.
DAYTIME = {"morning": "morning", "morgens": "morning", "vormittag": "morning", "vormittags": "morning",
           "afternoon": "afternoon", "nachmittag": "afternoon", "nachmittags": "afternoon",
           "evening": "evening", "abend": "evening", "abends": "evening"}
DAYTIME_WORDS = re.compile(r"\b(" + "|".join(DAYTIME) + r")\b", re.IGNORECASE)


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
    elif fields["preferred_contact_time"]:
        # If the sentence asking for a call names exactly one time of day, trust the customer's word.
        said = {DAYTIME[m.group(0).lower()] for sentence in re.split(r"[.!?]", text) if CONTACT_WORDS.search(sentence)
                for m in DAYTIME_WORDS.finditer(sentence)}
        if len(said) == 1 and fields["preferred_contact_time"] not in said:
            correct("preferred_contact_time", said.pop())
    return corrections


SUMMARY_LABEL = {"shopping": "Einkauf", "transport": "Fahrdienst", "companionship": "Begleitung",
                 "household": "Haushaltshilfe", "other": "Allgemeine Anfrage"}
# Who the help is for: relation words only, never names.
PERSON = [(r"mutter|mama|mum|mom|mother", "Mutter"), (r"vater|papa|dad|father", "Vater"),
          (r"oma|großmutter|grandmother|grandma|nan|nana", "Oma"), (r"opa|großvater|grandfather|grandad|grandpa", "Opa"),
          (r"eltern|parents", "Eltern"), (r"tante|aunt", "Tante"), (r"onkel|uncle", "Onkel"),
          (r"frau|ehefrau|wife", "Ehefrau"), (r"mann|ehemann|husband", "Ehemann")]
HEALTH_DE = {"fell": "gestürzt", "fallen": "gestürzt", "sturz": "gestürzt", "breath": "Atemnot", "unconscious": "bewusstlos",
             "pain": "Schmerzen", "bleed": "Blutung", "blut": "Blutung", "weak": "schwach", "confused": "verwirrt",
             "diarr": "Durchfall", "fever": "Fieber", "ill": "krank", "sick": "krank", "helpless": "hilflos",
             "can't get up": "kommt nicht hoch", "schmerz": "Schmerzen", "atmet": "Atemnot"}
PRICE = re.compile(r"\b(kost\w*|preis\w*|price\w*|cost\w*|how much)\b", re.I)
DAYTIME_DE = {"morning": "vormittags", "afternoon": "nachmittags", "evening": "abends"}


def _code_summary(fields: dict, text: str) -> str:
    """One German line built from the checked fields. The 3B model's own summaries were often garbled German
    ("Rüstkörchen und Elektroläser"), sometimes English, and twice contained the customer's full name."""
    low = text.lower()
    # "Frau"/"Mann" also mean Ms/man, so they need "meine"/"my" in front; the other words count on their own.
    person = next((de for pattern, de in PERSON
                   if re.search(r"\b(meine?[nmrs]?\s+|my\s+)" + ("" if de in ("Ehefrau", "Ehemann") else "?")
                                + rf"({pattern})\b", low)), None)
    line = SUMMARY_LABEL[fields["service_type"]] + (f" für {person}" if person else "")
    line += f" in {fields['location']}" if fields["location"] else ""
    line += f", „{fields['when_needed']}“" if fields.get("when_needed") else ""  # the customer's own words
    line += "."
    if fields["callback_requested"]:
        when = DAYTIME_DE.get(fields["preferred_contact_time"])
        line += f" Rückruf gewünscht{' (' + when + ')' if when else ''}."
    signs = []
    for m in HEALTH_RISK.finditer(text):
        word = m.group(0).lower()
        if word.startswith("blutdruck"):  # blood-pressure medicine is not bleeding
            continue
        de = next((v for k, v in HEALTH_DE.items() if word.startswith(k)), word)
        if de not in signs:
            signs.append(de)
    if PRICE.search(text):
        line += " Fragt nach dem Preis."
    if signs:
        line += " Hinweis im Text: " + ", ".join(signs) + "."
    return line


def extract_fields(state: dict) -> dict:
    raw = ask_llm(EXTRACTION_PROMPT, state["text"], ExtractedFields.model_schema_for_llm())
    fields = ExtractedFields.model_validate_json(raw).model_dump()
    corrections = ground_in_text(fields, state["text"])
    # The summary is rebuilt by code; the model's sentence stays visible in the audit log as a correction.
    code_summary = _code_summary(fields, state["text"])
    if code_summary != fields["summary"]:
        corrections["summary"] = [fields["summary"], code_summary]
        fields["summary"] = code_summary
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
You write AS the service TO the customer. Never ask the customer to call you, and never copy their own sentences
("please call me ...") into the reply. Thank them and repeat back what they asked for in your own words. If
information is missing, ask for it. If they asked for a callback, use the callback sentence given.
Nothing is booked yet: never say a booking or appointment is confirmed, never say what you "will" do, and do not
promise a specific helper, time, or price. Sign as "Your HOMECARE team" (German: "Ihr HOMECARE-Team")."""


GERMAN_WORDS = {"und", "ich", "die", "der", "das", "nicht", "bitte", "meine", "mein", "meinen", "meiner", "sie",
                "ist", "wir", "jemand", "könnte", "können", "hallo", "guten", "tag", "mit", "für", "zur", "zum", "nächsten"}


def _looks_german(text: str) -> bool:
    # Words only: umlauts alone would make "Münster" or "Lünen" look German.
    return len(set(_words(text)) & GERMAN_WORDS) >= 2


# A draft must not ask the customer to call us, and must not promise anything: nothing is booked yet.
ECHOED_CALL = re.compile(r"\b(rufen sie mich|ruf mich|melden sie sich bei mir|call me|ring me|contact me)\b", re.I)
PROMISE = re.compile(
    r"\b(i'll|i will|we'll|we will|werde ich|ich werde|werden wir|wir werden|gebucht|eingeplant|bestätig\w*|"
    r"zugesagt|organisiert|booked|confirmed|scheduled|arranged|is set up|fahren können|kommt am|kommt um|"
    r"kostenlos|kostenfrei|gratis|free of charge|for free)\b|\d+\s?(€|euro\b|eur\b)", re.I)
WHEN_DE = {"morning": " am Vormittag", "afternoon": " am Nachmittag", "evening": " am Abend"}
WHEN_EN = {"morning": " in the morning", "afternoon": " in the afternoon", "evening": " in the evening"}
SERVICE_DE = {"shopping": "Hilfe beim Einkaufen", "transport": "eine Fahrt", "companionship": "Begleitung oder Gesellschaft",
              "household": "Hilfe im Haushalt", "other": "Unterstützung"}
SERVICE_EN = {"shopping": "help with shopping", "transport": "a lift", "companionship": "companionship",
              "household": "help in the household", "other": "support"}
ASK_DE = {"location": "In welcher Stadt wird die Hilfe gebraucht?",
          "date": "An welchem Tag und zu welcher Uhrzeit brauchen Sie die Hilfe?",
          "details": "Können Sie kurz beschreiben, wobei genau wir helfen dürfen?"}
ASK_EN = {"location": "In which town is the help needed?", "date": "On which day and at what time do you need the help?",
          "details": "Could you briefly describe what kind of help you need?"}


def _callback_sentence(fields: dict, german: bool) -> str:
    if not fields["callback_requested"]:
        return ""
    when = fields["preferred_contact_time"]
    if german:
        return f"Eine Kollegin oder ein Kollege ruft Sie{WHEN_DE.get(when, '')} zurück."
    return f"A colleague will call you back{WHEN_EN.get(when, '')}."


HEALTH_RISK = re.compile(r"\b(gestürzt|sturz|fell|fallen|atmet|atemnot|breath\w*|bewusstlos|unconscious|schmerz\w*|pain|"
                         r"blut\w*|bleed\w*|schwach|weak|verwirrt|confused|durchfall|diarr\w*|fieber|fever|krank|ill|sick|hilflos|helpless|can\'t get up)\b", re.I)


def _template_draft(fields: dict, german: bool, text: str = "") -> str:
    """Reply built by code from the checked fields: restates the request, asks for what is missing, promises nothing."""
    city = f" in {fields['location']}" if fields["location"] else ""
    when = f" ({fields['when_needed']})" if fields.get("when_needed") else ""  # the customer's own words
    urgent = fields["urgency"] == "high"
    health = urgent and bool(HEALTH_RISK.search(text))
    if german:
        parts = ["Guten Tag, vielen Dank für Ihre Nachricht.",
                 f"Sie suchen {SERVICE_DE[fields['service_type']]}{city}{when}."]
        if urgent:
            parts.append("Wir behandeln Ihre Anfrage vorrangig.")
        if health:
            parts.append("Bei einem medizinischen Notfall rufen Sie bitte sofort 112 an.")
        parts += [ASK_DE[m] for m in fields["missing_info"]]
        parts.append(_callback_sentence(fields, True) or "Eine Kollegin oder ein Kollege meldet sich mit einem Vorschlag bei Ihnen.")
        return " ".join(parts) + "\n\nIhr HOMECARE-Team"
    parts = ["Hello, thank you for your message.", f"You are looking for {SERVICE_EN[fields['service_type']]}{city}{when}."]
    if urgent:
        parts.append("We are treating your request as a priority.")
    if health:
        parts.append("In a medical emergency, please call 112 right away.")
    parts += [ASK_EN[m] for m in fields["missing_info"]]
    parts.append(_callback_sentence(fields, False) or "A colleague will get back to you with a suggestion.")
    return " ".join(parts) + "\n\nYour HOMECARE team"


# "template" (default): code writes the reply from the checked fields. "model": the LLM writes it and the guard
# above falls back to the template on a promise or an echoed "call me". On the final test set the 3B model's own
# drafts needed edits in 7 of 13 cases, so the template is the default; a larger model could change that.
DRAFT_MODE = os.getenv("DRAFT_MODE", "template")


def draft_followup(state: dict) -> dict:
    fields = state["fields"]
    german = _looks_german(state["text"])
    if DRAFT_MODE == "template":
        draft = _template_draft(fields, german, state["text"])
        db.update_request(state["request_id"], followup_draft=draft, followup_status="pending_approval")
        return {"followup_draft": draft, "followup_status": "pending_approval", "draft_source": "template"}
    callback = _callback_sentence(fields, german)
    user_message = (
        f"Customer request:\n{state['text']}\n\n"
        f"Write the reply in {'German' if german else 'English'}.\n"
        f"Missing information to ask for: {', '.join(fields['missing_info']) or 'none'}\n"
        f"Callback sentence to include: {callback or 'none (no callback requested)'}"
    )
    draft = FollowupDraft.model_validate_json(
        ask_llm(DRAFT_PROMPT, user_message, FollowupDraft.model_json_schema())
    ).message.strip()
    source = "model"
    problem = ECHOED_CALL.search(draft) or PROMISE.search(draft)
    if problem:
        draft, source = _template_draft(fields, german, state["text"]), f"template (model wrote '{problem.group(0)}')"
    elif not re.search(r"homecare[ -]team", draft, re.IGNORECASE):  # the model sometimes drops the sign-off
        draft += "\n\nIhr HOMECARE-Team" if german else "\n\nYour HOMECARE team"
    # Never sent from here: a human must approve it in the dashboard.
    db.update_request(state["request_id"], followup_draft=draft, followup_status="pending_approval")
    return {"followup_draft": draft, "followup_status": "pending_approval", "draft_source": source}


SAME_DAY = re.compile(r"\b(today|tonight|this (afternoon|evening)|right now|asap|heute|sofort)\b", re.IGNORECASE)


# Danger words (fall, breathing, bleeding, no medication ...): always priority 1, whatever the model said.
# Checked against all 100 test requests: every match is labelled urgent, so no false alarms there.
EMERGENCY = re.compile(
    r"(gestürzt|gestolpert|hingefallen|\bsturz\b|\bfell\b|has fallen|slipped|can'?t get up|cannot get up"
    r"|kommt nicht (mehr )?hoch|\bstuck\b|bewusstlos|unconscious|not breathing|atemnot|keine luft|can'?t breathe"
    r"|short of breath|chest pain|brustschmerz|blutet|bleeding|stroke|schlaganfall|herzinfarkt|heart attack"
    r"|notfall|emergency|hohes fieber|high fever|ran out of|run out of"
    r"|out of (his |her |their )?(oxygen|medication|insulin|tablets|pills)|aufgebraucht"
    r"|keine (medikamente|tabletten) mehr|insulin)", re.IGNORECASE)


def set_priority(state: dict) -> dict:
    # Fixed rules instead of model judgement, so staff can predict and explain the ordering.
    fields = state["fields"]
    result = {}
    # Safety floors: the rules can only raise urgency, never lower it, because missing an urgent
    # case is worse than over-triaging a normal one.
    when_needed = fields["when_needed"] or ""
    danger = EMERGENCY.search(state["text"])
    if danger and fields["urgency"] != "high":
        result["urgency_raised_from"] = fields["urgency"]
        result["emergency_word"] = danger.group(0)
        fields["urgency"] = "high"
    elif danger:
        result["emergency_word"] = danger.group(0)
    elif fields["urgency"] != "high" and SAME_DAY.search(when_needed):
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
