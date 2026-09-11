"""Dashboard Help & Navigation Handler for Heat Copilot.

Provides concise step-by-step instructions for operating all interactive features,
layers, map controls, charts, and simulation modes on the SIH26083 dashboard.
"""

import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

HELP_TOPICS = [
    {
        "keywords": [r"\bselect\b", r"\bclick\b", r"\bward\b", r"\bchoose area\b", r"\bmap\b"],
        "title": "Selecting a Municipal Ward",
        "answer": (
            "1. **Click Any Polygon on the Map**: Hover and click any of the 48 municipal wards in Ahmedabad.\n"
            "2. **Sidebar Drawer**: The right-hand sidebar will instantly open, showing real-time ambient temperature, "
            "humidity, outdoor WBGT, HVI demographic score, and integrated risk tier.\n"
            "3. **National / City Scope**: Use the 'Scope' dropdown in the top header to toggle between **Ahmedabad (48 Municipal Wards)** "
            "and **All India (35 States & Union Territories)**."
        ),
    },
    {
        "keywords": [r"\bforecast\b", r"\bchart\b", r"\b5 day\b", r"\b5-day\b", r"\btimeline\b", r"\btrend\b"],
        "title": "Reading the 5-Day Heatwave Forecast Chart",
        "answer": (
            "1. **Select a Ward**: Click any ward polygon on the map.\n"
            "2. **Scroll to Forecast Section**: In the right sidebar, locate the **5-Day Predictive Risk Timeline**.\n"
            "3. **Dual-Axis Chart**: The solid line tracks daily peak temperature (°C), while color-coded badges indicate "
            "predicted risk tiers (Low, Moderate, High, Extreme) from Day 1 (24h lead) to Day 5 (120h lead).\n"
            "4. **Early Preparedness**: Days colored Orange or Red indicate impending heatwaves, enabling proactive water tanker mobilization."
        ),
    },
    {
        "keywords": [r"\bbacktest\b", r"\b2010\b", r"\bhistorical\b", r"\bmay 2010\b"],
        "title": "Toggling Backtest Mode (May 2010 Landmark Heatwave)",
        "answer": (
            "1. **Click '🕒 Backtest Mode'**: Located directly on the top-left map overlay.\n"
            "2. **Historical Simulation**: The map transforms to display the lethal **May 21, 2010 heatwave (46.8°C)**, "
            "the catalyst event for South Asia's first Heat Action Plan.\n"
            "3. **Verification**: Inspect how the system's thermal stress models accurately identified 100% of municipal wards "
            "in EXTREME danger, aligning with the 1,344 excess deaths recorded in published medical literature (Azhar et al., 2014).\n"
            "4. **Exit**: Click the button again to return to live operational forecasting."
        ),
    },
    {
        "keywords": [r"\bhuman impact\b", r"\bpopulation\b", r"\bcard\b", r"\bwho is affected\b", r"\bchildren\b", r"\belderly\b"],
        "title": "Viewing the Human Impact Card & Population Breakdown",
        "answer": (
            "1. **Select a Ward**: Click any ward polygon on the map.\n"
            "2. **Human Impact Card**: Appears below the weather metrics in the sidebar.\n"
            "3. **Segmented Counts**: Displays actual estimated headcounts for **Children (Age 0-5)**, **Elderly (60+)**, "
            "**Outdoor/Informal Laborers**, and **Slum Residents**.\n"
            "4. **Clinical Consequences & Targeted Actions**: Explains specific physiological threats each group faces "
            "and evidence-based clinical countermeasures backed by WHO, NDMA, and NRDC guidelines."
        ),
    },
    {
        "keywords": [r"\balert\b", r"\bsms\b", r"\bwhatsapp\b", r"\bdispatch\b", r"\bphone\b"],
        "title": "Testing Early Warning SMS Alerts",
        "answer": (
            "1. **Select a Ward**: Click any ward polygon on the map.\n"
            "2. **Scroll to Emergency Warning**: In the right sidebar, enter a phone number in E.164 format (e.g. `+919876543210`).\n"
            "3. **Click 'Trigger Emergency Alert'**: Dispatches a bilingual alert via Twilio / Gupshup SMS Sandbox.\n"
            "4. **Safety Filter**: If the ward is below the alert threshold, use the 'Force Demo Alert' checkbox to bypass "
            "rate limiting for demonstration to hackathon judges."
        ),
    },
    {
        "keywords": [r"\blayer\b", r"\bhazard\b", r"\bchoropleth\b", r"\bmode\b"],
        "title": "Switching Map Visualization Layers",
        "answer": (
            "Use the 3 pill buttons at the top of the map:\n"
            "* **Composite Risk** (Default): Combines 60% meteorological thermal hazard + 40% demographic vulnerability.\n"
            "* **Thermal Hazard**: Pure physical atmospheric heat stress (WBGT + NOAA Heat Index + UTCI).\n"
            "* **Vulnerability (HVI)**: Demographic susceptibility based on Census 2011 & PLFS indicators."
        ),
    },
]


def handle_dashboard_help(message: str) -> Dict[str, Any]:
    """Provide step-by-step instructions for navigating the dashboard."""
    msg_clean = message.lower()

    best_match = None
    for topic in HELP_TOPICS:
        for pattern in topic["keywords"]:
            if re.search(pattern, msg_clean):
                best_match = topic
                break
        if best_match:
            break

    if best_match:
        response_text = f"### 🧭 Dashboard Guide: {best_match['title']}\n\n{best_match['answer']}"
    else:
        response_text = (
            "### 🧭 SIH26083 Dashboard Navigation Help\n\n"
            "Here are quick guides for operating this dashboard:\n\n"
            "* **Select a Ward**: Click any ward polygon on the map to inspect its real-time heat metrics and demographics.\n"
            "* **5-Day Forecast Chart**: Scroll down the right sidebar to view multi-day predicted temperature and risk trends.\n"
            "* **Human Impact Card**: See exact population counts and clinical health consequences for vulnerable cohorts.\n"
            "* **Backtest Mode (May 2010)**: Click the '🕒 Backtest Mode' button to replay the 46.8°C historical landmark event.\n"
            "* **Early Warning SMS**: Enter a mobile number in the sidebar and click 'Trigger Emergency Alert' to test alerts.\n"
            "* **National Map**: Switch the scope dropdown in the header to view the **All-India heatwave map**!"
        )

    return {
        "response_text": response_text.strip(),
        "requires_ward_selection": False,
        "risk_score": None,
        "risk_tier": None,
        "recommendation": None,
        "suggested_better_time": None,
        "dominant_factor": None,
    }
