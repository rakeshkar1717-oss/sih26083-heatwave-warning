"""Intent Router for Heat Copilot.

Classifies incoming user messages into one of three canonical intents:
- personal_risk_query : Queries about personal safety, activities, times, trips, and risk.
- general_question    : Scientific/meteorological inquiries (WBGT, UTCI, HVI, formulas, sources).
- dashboard_help      : Instructions on operating dashboard UI controls, maps, and features.
"""

import re
import logging
from typing import Dict, Any, Optional

from backend.models import CopilotIntent

logger = logging.getLogger(__name__)

# Keyword and regex patterns for deterministic classification
PERSONAL_RISK_PATTERNS = [
    r"\b(safe|safe to|can i|should i|is it ok|is it safe)\b",
    r"\b(walk|run|jog|play|commute|travel|drive|work|cycle|exercise|visit|go out|going out|outside|step out|stepping out)\b",
    r"\b(at \d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm)|noon|afternoon|morning|evening|night|now|today|tomorrow)\b",
    r"\b(danger|dangerous|heat stroke|dehydration|sunburn|faint|sick)\b",
    r"\b(for my (child|kid|baby|mother|father|elderly|grandfather|grandmother))\b",
    r"\b(construction|delivery|labor|worker|vendor)\b",
]

DASHBOARD_HELP_PATTERNS = [
    r"\b(how do i|how to use|how to see|how can i find|where is|where do i)\b",
    r"\b(dashboard|ui|button|dropdown|selector|map|layer|choropleth|legend|toggle)\b",
    r"\b(backtest mode|historical mode|test alert|send sms|alert button|click a ward|select a ward)\b",
    r"\b(read the chart|forecast chart|timeline chart|how to read|navigate)\b",
]

GENERAL_SCIENCE_PATTERNS = [
    r"\b(what is|what does|how does|explain|definition of|meaning of|why does)\b",
    r"\b(wbgt|wet bulb|globe temperature|utci|universal thermal|heat index|noaa)\b",
    r"\b(vulnerability|hvi|vulnerability score|how is risk calculated|risk formula|formula)\b",
    r"\b(risk tier|risk tiers|moderate|high|very high|extreme|color code|threshold)\b",
    r"\b(data source|data sources|census|plfs|open-meteo|nasa power|era5|reanalysis)\b",
    r"\b(accuracy|how accurate|forecast accuracy|backtest|validation|bias correction)\b",
]


def classify_intent(message: str, user_context: Optional[Dict[str, Any]] = None) -> CopilotIntent:
    """Classify incoming message into a CopilotIntent enum value.

    Parameters
    ----------
    message : str
        The raw text inquiry from the user.
    user_context : Dict[str, Any], optional
        Contextual metadata (e.g. activity, age_group).

    Returns
    -------
    CopilotIntent
        The classified user intent.
    """
    if not message or not message.strip():
        return CopilotIntent.GENERAL_QUESTION

    msg_clean = message.lower().strip()

    # 1. Check if user_context explicitly signals personal query
    if user_context and any(k in user_context for k in ["activity", "time", "age_group", "duration"]):
        return CopilotIntent.PERSONAL_RISK_QUERY

    # 2. Check Dashboard Help first if explicitly asking about UI features
    dashboard_matches = sum(1 for p in DASHBOARD_HELP_PATTERNS if re.search(p, msg_clean))
    personal_matches = sum(1 for p in PERSONAL_RISK_PATTERNS if re.search(p, msg_clean))
    general_matches = sum(1 for p in GENERAL_SCIENCE_PATTERNS if re.search(p, msg_clean))

    # Priority disambiguation
    if dashboard_matches >= 2:
        return CopilotIntent.DASHBOARD_HELP

    if personal_matches >= 1 and (
        any(k in msg_clean for k in ["safe", "walk", "go", "outside", "pm", "am", "run", "work", "play", "travel", "today", "tomorrow", "now"])
    ):
        return CopilotIntent.PERSONAL_RISK_QUERY

    if general_matches >= 1:
        return CopilotIntent.GENERAL_QUESTION

    if dashboard_matches >= 1:
        return CopilotIntent.DASHBOARD_HELP

    # Fallback heuristic: if mentions "i", "me", "my", "we" -> personal risk; otherwise general
    if re.search(r"\b(i|me|my|we|us|can|safe)\b", msg_clean):
        return CopilotIntent.PERSONAL_RISK_QUERY

    return CopilotIntent.GENERAL_QUESTION
