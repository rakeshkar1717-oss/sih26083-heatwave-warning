"""Unit and integration tests for Heat Copilot chatbot."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.models import CopilotIntent, CopilotChatRequest, CopilotChatResponse
from backend.copilot.intent_router import classify_intent
from backend.copilot.personal_risk_handler import handle_personal_risk_query, extract_entities
from backend.copilot.general_qa_handler import handle_general_question
from backend.copilot.dashboard_help_handler import handle_dashboard_help
from backend.copilot import process_copilot_chat

client = TestClient(app)


def test_intent_router_classification():
    """Verify that intent router classifies user inquiries correctly."""
    # Personal risk queries
    assert classify_intent("is it safe to walk to college at 2pm") == CopilotIntent.PERSONAL_RISK_QUERY
    assert classify_intent("can I go for a run right now in Navrangpura?") == CopilotIntent.PERSONAL_RISK_QUERY
    assert classify_intent("should my grandmother go out at noon?") == CopilotIntent.PERSONAL_RISK_QUERY

    # General scientific / FAQ questions
    assert classify_intent("what does WBGT mean?") == CopilotIntent.GENERAL_QUESTION
    assert classify_intent("explain how the vulnerability score is calculated") == CopilotIntent.GENERAL_QUESTION
    assert classify_intent("how accurate is this 5-day forecast?") == CopilotIntent.GENERAL_QUESTION

    # Dashboard navigation help
    assert classify_intent("how do I see the forecast for my area?") == CopilotIntent.DASHBOARD_HELP
    assert classify_intent("how to use backtest mode on the map?") == CopilotIntent.DASHBOARD_HELP
    assert classify_intent("where is the button to send SMS alerts?") == CopilotIntent.DASHBOARD_HELP


def test_personal_risk_entity_extraction():
    """Verify entity extraction from natural language query."""
    entities = extract_entities("Can I do construction work outside at 2pm for 3 hours?")
    assert entities["time_str"] == "2PM" or "2" in entities["time_str"]
    assert "Construction" in entities["activity"]
    assert "3 hours" in entities["duration"]


def test_personal_risk_ward_auto_detection():
    """Verify that ward name mentioned in message is automatically resolved."""
    entities = extract_entities("Is it safe to jog in Navrangpura at 4pm?")
    assert entities["detected_ward_id"] == "AMD_01"


def test_personal_risk_missing_ward_prompts_user():
    """Verify that personal risk query without a ward asks user for their area."""
    res = handle_personal_risk_query("Is it safe to go cycling at 2pm?")
    assert res["requires_ward_selection"] is True
    assert "which area or" in res["response_text"].lower()


def test_personal_risk_thermoguard_response_structure():
    """Verify ThermoGuard-compliant structure when ward is specified."""
    res = handle_personal_risk_query("Is it safe to walk at 2pm?", ward_id="AMD_01")
    assert res["requires_ward_selection"] is False
    assert res["risk_score"] is not None
    assert 0.0 <= res["risk_score"] <= 1.0
    assert res["risk_tier"] in ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME"]
    assert res["recommendation"] is not None
    assert res["suggested_better_time"] is not None

    text = res["response_text"]
    assert "ThermoGuard" in text
    assert "Current Microclimate" in text
    assert "Why Is This Risk Level Triggered?" in text
    assert "Clear Recommendation" in text


def test_general_qa_handler():
    """Verify verified answers for core platform science."""
    res_wbgt = handle_general_question("What does WBGT mean?")
    assert "Wet Bulb Globe Temperature" in res_wbgt["response_text"]

    res_acc = handle_general_question("How accurate is this forecast?")
    assert "85.43%" in res_acc["response_text"] or "Accuracy" in res_acc["response_text"]


def test_dashboard_help_handler():
    """Verify step-by-step guidance for dashboard features."""
    res_map = handle_dashboard_help("How do I select a ward?")
    assert "Click Any Polygon on the Map" in res_map["response_text"]

    res_bt = handle_dashboard_help("How does backtest mode work?")
    assert "2010" in res_bt["response_text"]


def test_api_copilot_chat_personal_risk():
    """Test POST /api/copilot/chat with personal risk inquiry."""
    payload = {
        "message": "Is it safe to walk to college at 2pm?",
        "ward_id": "AMD_01",
        "user_context": {"activity": "walking"},
    }
    response = client.post("/api/copilot/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "personal_risk_query"
    assert data["risk_score"] is not None
    assert "ThermoGuard" in data["response_text"]


def test_api_copilot_chat_general_question():
    """Test POST /api/copilot/chat with scientific inquiry."""
    payload = {
        "message": "What is WBGT and why is it important?",
    }
    response = client.post("/api/copilot/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "general_question"
    assert "Wet Bulb Globe Temperature" in data["response_text"]
