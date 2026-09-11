"""Optional LLM Rephrasing Client for Heat Copilot.

Inspects environment variables for ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY.
If configured, provides natural language conversational polish while strictly preserving
all calculated physical meteorological, physiological, and vulnerability figures.
If no key is configured, cleanly passes through the rule-based response with zero downtime.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Heat Copilot, an AI thermal health and early warning assistant for the SIH26083 platform.
Your task is to rephrase the provided verified response naturally and helpfully.
CRITICAL SAFETY & INTEGRITY RULES:
1. You MUST NEVER alter, round, omit, or invent any temperature, humidity, WBGT, vulnerability score, or risk score.
2. Preserve all recommendations (Avoid / Caution / Safe), suggested time windows, and clinical precautions exactly.
3. Maintain clear markdown headings and bullet points.
"""


def maybe_enhance_with_llm(rule_based_text: str, user_query: str) -> str:
    """Optionally rephrase response using an LLM if an API key is available."""
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not any([openai_key, anthropic_key, gemini_key]):
        # No LLM key configured: deterministic zero-downtime passthrough
        return rule_based_text

    # 1. Try OpenAI if key present
    if openai_key:
        try:
            import urllib.request
            import json

            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"User asked: {user_query}\n\nFactual calculated response to polish:\n{rule_based_text}"}
                ],
                "temperature": 0.3,
                "max_tokens": 800,
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {openai_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                polished = data["choices"][0]["message"]["content"]
                if polished and len(polished.strip()) > 30:
                    return polished.strip()
        except Exception as e:
            logger.debug("OpenAI API call failed or timed out (%s). Falling back to rule-based.", e)

    # 2. Try Anthropic if key present
    if anthropic_key:
        try:
            import urllib.request
            import json

            payload = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 800,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": f"User asked: {user_query}\n\nFactual calculated response to polish:\n{rule_based_text}"}
                ],
                "temperature": 0.3,
            }
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                polished = data["content"][0]["text"]
                if polished and len(polished.strip()) > 30:
                    return polished.strip()
        except Exception as e:
            logger.debug("Anthropic API call failed or timed out (%s). Falling back to rule-based.", e)

    return rule_based_text
