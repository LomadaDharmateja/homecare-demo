"""Agent loop: the model picks the next tool by name, Python executes it, repeat (max 4 steps)."""
import json

from app import db, tools
from app.schemas import AgentDecision, IntakeIn

MAX_STEPS = 4

PLANNER_PROMPT = """You coordinate the intake of a customer request for a home-help service.
Choose the next tool to run, or "finish" when the record is complete.
A complete record has: extracted fields, checked missing information, a priority, and a drafted
follow-up message for staff to approve. Each tool can run only once.

Tools:
{tool_list}"""


def decision_schema(allowed: list[str]) -> dict:
    # Narrowing the enum means the model physically cannot name a tool that does not exist or already ran.
    schema = AgentDecision.model_json_schema()
    schema["properties"]["tool"]["enum"] = allowed
    return schema


def choose_next_tool(state: dict, remaining: list[str]) -> AgentDecision:
    tool_list = "\n".join(f"- {name}: {tools.TOOLS[name][1]}" for name in remaining)
    progress = {"tools_already_run": state["completed"], "current_fields": state.get("fields")}
    raw = tools.ask_llm(
        PLANNER_PROMPT.format(tool_list=tool_list),
        f"Request:\n{state['text']}\n\nProgress:\n{json.dumps(progress, ensure_ascii=False)}",
        decision_schema(remaining + ["finish"]),
    )
    return AgentDecision.model_validate_json(raw)


def process_request(intake: IntakeIn) -> dict:
    db.init_db()
    request_id = db.insert_request(intake.text, intake.channel, intake.received_at.isoformat(timespec="seconds"))
    db.log_audit(request_id, "received", input_data=intake.model_dump(mode="json"))
    state = {"request_id": request_id, "text": intake.text, "completed": []}

    for step in range(1, MAX_STEPS + 1):
        remaining = [name for name in tools.TOOLS if name not in state["completed"]]
        if not remaining:
            break
        decision = choose_next_tool(state, remaining)
        # Guardrail: nothing else can work without extracted fields, so extraction is forced first.
        if "extract_fields" in remaining and decision.tool != "extract_fields":
            decision = AgentDecision(tool="extract_fields", reason=f"guardrail override (model chose {decision.tool})")
        db.log_audit(request_id, "agent_decision", input_data={"step": step, "allowed": remaining},
                     output_data=decision.model_dump())
        if decision.tool == "finish":
            break
        tools.run_tool(decision.tool, state)
        state["completed"].append(decision.tool)
        if "fields" not in state:  # extraction failed; the other tools need its output
            break

    if "fields" not in state:
        # Fail safe, not silent: an unclassified request goes to the top of the queue for a human.
        db.update_request(request_id, priority=1, summary="Automatic extraction failed - needs manual triage")
        db.log_audit(request_id, "guardrail", output_data={"reason": "extraction failed, flagged for manual triage"})
    else:
        # Guardrail: the two rule-based tools are cheap and every record needs their output to be
        # triaged correctly, so they run even if the model skipped them. Drafting stays optional.
        for name in ("check_missing_info", "set_priority"):
            if name not in state["completed"]:
                db.log_audit(request_id, "guardrail", output_data={"reason": f"model finished without {name}"})
                tools.run_tool(name, state)
                state["completed"].append(name)

    record = db.get_request(request_id)
    record["tools_run"] = state["completed"]
    return record


if __name__ == "__main__":
    example = IntakeIn(text="My mum needs a lift to the dentist on Monday at 9:30. She lives in Krefeld. Please call me back in the morning.")
    print(json.dumps(process_request(example), indent=2, ensure_ascii=False))
