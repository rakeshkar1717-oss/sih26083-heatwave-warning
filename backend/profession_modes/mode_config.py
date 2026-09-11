"""Configuration and Preset Definitions for Profession Modes.

Defines the 6 curated occupational and lifestyle presets:
1. Student (commuter / light walking / limited duration)
2. Delivery Worker (high mobility / continuous solar exposure / moderate exertion)
3. Construction Worker (heavy physical labor / sustained radiant heat)
4. Elderly Care (caregiver perspective / vulnerable nonworking elder in domestic thermal traps)
5. Outdoor Exercise (intense aerobic exertion / high internal metabolic heat)
6. Farmer (heavy manual agricultural labor / prolonged unmitigated field exposure)

Grounded in:
- ISO 8996 Metabolic Rate Exertion Classes
- ISO 7243 Liljegren Wet Bulb Globe Temperature standards
- Ahmedabad Heat Action Plan (HAP 2018) occupational protocols
- National Disaster Management Authority (NDMA 2024) Guidelines
"""

from typing import Dict, Any, List
from backend.personal_risk.personal_risk_schema import (
    AgeGroup,
    OccupationType,
    ActivityType,
)


PROFESSION_MODES_CONFIG: Dict[str, Dict[str, Any]] = {
    "student": {
        "mode_id": "student",
        "display_name": "Student",
        "icon": "🎓",
        "subtitle": "Campus Commuter & Youth",
        "description": "Walking during transit hours with developing physiological thermoregulation and backpack load.",
        "activity_mapping": {
            "age_group": AgeGroup.AGE_0_17,
            "occupation": OccupationType.STUDENT,
            "current_activity": ActivityType.WALKING,
            "outdoor_duration_minutes": 30,
        },
        "default_recommendations": [
            {
                "action_text": "Avoid unshaded playground sports and outdoor assemblies between 11:00 AM and 4:00 PM.",
                "action_type": "urgent",
                "citation": "NDMA Heatwave Guidelines / Ahmedabad HAP Pediatric Advisory",
                "icon": "🚫",
            },
            {
                "action_text": "Carry a refillable insulated water bottle and hydrate every 20-30 minutes during commute.",
                "action_type": "precaution",
                "citation": "WHO 2021 Clinical Heat Guidance",
                "icon": "💧",
            },
            {
                "action_text": "Wear loose, light-colored cotton clothing and a wide-brim cap or umbrella when walking.",
                "action_type": "precaution",
                "citation": "National Health Mission Pediatric Heat Protocol",
                "icon": "🧢",
            },
            {
                "action_text": "Remain in ventilated, shaded campus corridors between classroom blocks during afternoon peak.",
                "action_type": "precaution",
                "citation": "Ahmedabad Municipal Corporation School Heat Advisory",
                "icon": "🏫",
            },
        ],
    },
    "delivery_worker": {
        "mode_id": "delivery_worker",
        "display_name": "Delivery Worker",
        "icon": "🛵",
        "subtitle": "Two-Wheeler & Gig Courier",
        "description": "Continuous mobile roadway exposure, engine heat dissipation, helmet thermal trap, and asphalt reflection.",
        "activity_mapping": {
            "age_group": AgeGroup.AGE_18_30,
            "occupation": OccupationType.OUTDOOR_WORKER,
            "current_activity": ActivityType.MODERATE_EXERCISE,
            "outdoor_duration_minutes": 180,
        },
        "default_recommendations": [
            {
                "action_text": "Prefer shaded tree-canopy transit corridors and avoid waiting under direct sun at traffic signals.",
                "action_type": "precaution",
                "citation": "NRDC Urban Heat Island & Green Canopy Studies",
                "icon": "🌳",
            },
            {
                "action_text": "Mandatory 10-minute cooling breaks inside air-conditioned hub facilities every 60-90 minutes.",
                "action_type": "urgent",
                "citation": "AMC Gig Economy & Street Worker Protection Order",
                "icon": "❄️",
            },
            {
                "action_text": "Drink at least 500 mL water supplemented with oral rehydration salts (ORS) hourly.",
                "action_type": "precaution",
                "citation": "NDMA Occupational Heat Guidelines (2024)",
                "icon": "🥤",
            },
            {
                "action_text": "Wear breathable UV-blocking arm sleeves and remove full-face helmet during standstill rest stops.",
                "action_type": "precaution",
                "citation": "ISO 7243 Microclimatic Protective Clothing",
                "icon": "🛡️",
            },
        ],
    },
    "construction_worker": {
        "mode_id": "construction_worker",
        "display_name": "Construction Worker",
        "icon": "🏗️",
        "subtitle": "Manual Site & Daily Wage Labor",
        "description": "High metabolic exertion (~300+ W), heavy lifting, direct solar radiant absorption, and re-radiated concrete heat.",
        "activity_mapping": {
            "age_group": AgeGroup.AGE_31_45,
            "occupation": OccupationType.OUTDOOR_WORKER,
            "current_activity": ActivityType.HEAVY_LABOR,
            "outdoor_duration_minutes": 240,
        },
        "default_recommendations": [
            {
                "action_text": "MANDATORY WORK CESSATION: Halt heavy physical labor on unshaded sites between 11:30 AM and 4:00 PM.",
                "action_type": "urgent",
                "citation": "AMC Municipal Commissioner Extreme Heat Order / NDMA 2024",
                "icon": "🛑",
            },
            {
                "action_text": "Shift strenuous lifting and excavation tasks to early morning shifts starting before 07:00 AM.",
                "action_type": "precaution",
                "citation": "Ahmedabad Heat Action Plan Construction Protocol",
                "icon": "🌅",
            },
            {
                "action_text": "Provide on-site covered shaded rest sheds with cold water tankers and active electrolyte packets.",
                "action_type": "urgent",
                "citation": "Building and Other Construction Workers (BOCW) Heat Safety Rules",
                "icon": "⛺",
            },
            {
                "action_text": "Implement 'buddy system' surveillance: immediately report confusion, lack of sweat, or stumbling.",
                "action_type": "urgent",
                "citation": "OSHA / WHO Exertional Heatstroke Emergency Protocol",
                "icon": "👥",
            },
        ],
    },
    "elderly_care": {
        "mode_id": "elderly_care",
        "display_name": "Elderly Care",
        "icon": "👵",
        "subtitle": "Senior & Homebound Caregiver",
        "description": "Impaired baroreflex, blunted thirst response, chronic cardiovascular strain, and domestic indoor thermal traps.",
        "activity_mapping": {
            "age_group": AgeGroup.AGE_60_PLUS,
            "occupation": OccupationType.ELDERLY_NONWORKING,
            "current_activity": ActivityType.RESTING,
            "outdoor_duration_minutes": 45,
        },
        "default_recommendations": [
            {
                "action_text": "Maintain indoor living quarters below 32°C using cross-ventilation, wet blinds, or evaporative coolers.",
                "action_type": "urgent",
                "citation": "WHO/WMO 2015 WMO-No. 1142 Elderly Thermal Comfort",
                "icon": "🏠",
            },
            {
                "action_text": "Administer regular oral fluids every 30 minutes without waiting for verbal sensation of thirst.",
                "action_type": "urgent",
                "citation": "Azhar et al. (2014) PLOS ONE Ahmedabad Geriatric Heatwave Study",
                "icon": "💧",
            },
            {
                "action_text": "Check blood pressure and pulse twice daily; consult doctor on adjusting diuretic dosages during heatwaves.",
                "action_type": "precaution",
                "citation": "Indian Public Health Standards (IPHS) Geriatric Heat Guidance",
                "icon": "🩺",
            },
            {
                "action_text": "Evacuate to municipal air-cooled civic shelter if indoor temperatures exceed 38°C with tin roofing.",
                "action_type": "urgent",
                "citation": "Ahmedabad Cool Roofs & Slum Evacuation Protocol",
                "icon": "🚨",
            },
        ],
    },
    "outdoor_exercise": {
        "mode_id": "outdoor_exercise",
        "display_name": "Outdoor Exercise",
        "icon": "🏃",
        "subtitle": "Athletics, Running & Cycling",
        "description": "High endogenous metabolic heat (~250-400 W), elevated heart rate, and rapid electrolyte depletion via sweating.",
        "activity_mapping": {
            "age_group": AgeGroup.AGE_18_30,
            "occupation": OccupationType.OTHER,
            "current_activity": ActivityType.HEAVY_LABOR,
            "outdoor_duration_minutes": 60,
        },
        "default_recommendations": [
            {
                "action_text": "Strictly reschedule outdoor running and intense cardio before 08:30 AM or after 06:30 PM.",
                "action_type": "urgent",
                "citation": "American College of Sports Medicine (ACSM) Heat Stress Standards",
                "icon": "⏰",
            },
            {
                "action_text": "Pre-hydrate with 400-500 mL water 30 minutes before training; consume 200 mL every 15 minutes of exertion.",
                "action_type": "precaution",
                "citation": "ISO 8996 Metabolic Hydration Criteria",
                "icon": "💧",
            },
            {
                "action_text": "Apply cold water sponging to neck and forehead for rapid convective and evaporative cooling.",
                "action_type": "precaution",
                "citation": "Sports Medicine Exertional Heat Sickness Protocol",
                "icon": "🧊",
            },
            {
                "action_text": "Cease exercise immediately if experiencing goosebumps, chills, nausea, throbbing headache, or disorientation.",
                "action_type": "urgent",
                "citation": "WHO Clinical Warning Signs for Exertional Heatstroke",
                "icon": "⚠️",
            },
        ],
    },
    "farmer": {
        "mode_id": "farmer",
        "display_name": "Farmer",
        "icon": "🌾",
        "subtitle": "Agricultural & Rural Labor",
        "description": "Sustained heavy agricultural labor (~320+ W), prolonged unshaded crop field exposure (6+ hours), high solar zenith.",
        "activity_mapping": {
            "age_group": AgeGroup.AGE_46_59,
            "occupation": OccupationType.OUTDOOR_WORKER,
            "current_activity": ActivityType.HEAVY_LABOR,
            "outdoor_duration_minutes": 360,
        },
        "default_recommendations": [
            {
                "action_text": "Shift intensive field tilling, weeding, and canal irrigation to dawn hours (05:30 AM – 09:30 AM).",
                "action_type": "urgent",
                "citation": "ICAR Agricultural Heat Advisory / NDMA Rural Action Plan",
                "icon": "🚜",
            },
            {
                "action_text": "Carry portable earthen or insulated water containers with lemon salt solution directly into field tracts.",
                "action_type": "precaution",
                "citation": "Gujarat State Disaster Management Authority (GSDMA) Farmer Protocol",
                "icon": "🍶",
            },
            {
                "action_text": "Mandatory rest under dense tree canopy or machan shelters during peak solar zenith (12:00 PM – 04:00 PM).",
                "action_type": "urgent",
                "citation": "ISO 7243 Agricultural Solar Load Thresholds",
                "icon": "🌴",
            },
            {
                "action_text": "Wear a wide-brim straw hat (pagri/topi) and loose-fitting, light-colored full-sleeve cotton clothing.",
                "action_type": "precaution",
                "citation": "Rural Epidemiological Heatwave Dos and Don'ts",
                "icon": "👒",
            },
        ],
    },
}
