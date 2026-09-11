"""Heat Copilot package for SIH26083 Extreme Heatwave Warning Platform."""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models import CopilotIntent, CopilotChatRequest, CopilotChatResponse
from backend.copilot.intent_router import classify_intent
from backend.copilot.personal_risk_handler import handle_personal_risk_query
from backend.copilot.general_qa_handler import handle_general_question
from backend.copilot.dashboard_help_handler import handle_dashboard_help
from backend.copilot.llm_client import maybe_enhance_with_llm


def process_copilot_chat(
    req: CopilotChatRequest,
    db: Optional[Session] = None,
) -> CopilotChatResponse:
    """Orchestrate Heat Copilot chat pipeline: intent routing -> handler -> optional polish -> response."""
    intent = classify_intent(req.message, req.user_context)

    if intent == CopilotIntent.PERSONAL_RISK_QUERY:
        res = handle_personal_risk_query(
            message=req.message,
            ward_id=req.ward_id,
            user_context=req.user_context,
            db=db,
        )
    elif intent == CopilotIntent.DASHBOARD_HELP:
        res = handle_dashboard_help(req.message)
    else:
        res = handle_general_question(req.message)

    # Polish with LLM if key is present (preserving numbers strictly)
    polished_text = maybe_enhance_with_llm(res["response_text"], req.message)

    return CopilotChatResponse(
        response_text=polished_text,
        intent=intent.value,
        risk_score=res.get("risk_score"),
        risk_tier=res.get("risk_tier"),
        recommendation=res.get("recommendation"),
        suggested_better_time=res.get("suggested_better_time"),
        dominant_factor=res.get("dominant_factor"),
        requires_ward_selection=res.get("requires_ward_selection", False),
    )


__all__ = [
    "classify_intent",
    "handle_personal_risk_query",
    "handle_general_question",
    "handle_dashboard_help",
    "process_copilot_chat",
    "maybe_enhance_with_llm",
]
