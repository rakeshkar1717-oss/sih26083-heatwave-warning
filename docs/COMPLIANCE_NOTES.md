# Public Safety Messaging & Telecommunications Compliance Notes

This document details the regulatory compliance architecture, opt-in/opt-out protocols, and known telecom limitations for the **SIH26083 Extreme Heatwave Early Warning & Human Thermal Stress Index** alerting subsystem.

---

## 1. Regulatory Context & System Classification

The SIH26083 alerting platform is categorized strictly as a **Public Health & Civil Safety Emergency Notification Service**. Its exclusive objective is to transmit life-safety biometeorological hazard warnings (e.g. wet-bulb globe temperature danger spikes, physiological heat exhaustion thresholds, and municipal cooling shelter notices) to residents in affected urban wards. It transmits **no commercial, marketing, or promotional messages**.

---

## 2. Opt-In & Consent Architecture (Double Opt-In Standard)

To safeguard citizen privacy and prevent unauthorized phone number registration, SIH26083 enforces a **Double Opt-In** pattern:

1. **Explicit Web Initiation**:
   - The user explicitly types their mobile number into the dashboard signup widget, selects their home or work ward, chooses their preferred delivery channel (SMS or WhatsApp), and reviews the statutory notice:  
     > *"By subscribing, you agree to receive heat safety alerts for your area. Reply STOP anytime to unsubscribe."*
2. **Immediate Confirmation Message**:
   - Immediately upon form submission, the system dispatches a single transactional confirmation text via the configured carrier gateway:
     > *"You're subscribed to heat alerts for [Ward Name]. Reply STOP anytime to unsubscribe. - SIH26083 Heat Warning System"*
3. **Immutable Audit Trail (`consent_logs`)**:
   - The confirmation dispatch is logged in the `consent_logs` table with the subscriber's E.164 phone number, target municipal ward, action (`SUBSCRIBE_OPT_IN`), channel (`sms` or `whatsapp`), and exact UTC timestamp.

---

## 3. Opt-Out & Carrier Compliance (`STOP` Protocol)

In accordance with international carrier guidelines (CTIA, FCC, and TCPA recommendations) and standard mobile industry practices:

1. **Universal STOP Keyword Recognition**:
   - Any inbound SMS or WhatsApp reply matching `STOP`, `UNSUBSCRIBE`, `CANCEL`, `END`, or `QUIT` (case-insensitive) is automatically routed to `/api/webhook/inbound-message`.
   - The system immediately deactivates the subscriber record (`is_active = False`) across all municipal wards.
2. **Immediate Opt-Out Confirmation**:
   - The gateway replies with a final opt-out receipt:
     > *"You've been unsubscribed from SIH26083 Heat Warning alerts. Reply START anytime to resubscribe."*
3. **Web-Based Unsubscription**:
   - Citizens who no longer possess mobile reply capability can click **"Manage my subscription"** on the dashboard and enter their phone number to deactivate subscriptions immediately.

---

## 4. Abuse & Spam Prevention Safety Limits

To guarantee that bugs or malicious actors cannot spam real citizens' mobile devices, two strict limits are hardcoded in `backend/config.py`:

| Parameter | Default Limit | Purpose |
| :--- | :---: | :--- |
| `MAX_SUBSCRIPTION_ATTEMPTS_PER_HOUR` | `3` attempts / hr | Prevents automated bots from repeatedly subscribing or harassing a specific phone number. |
| `MAX_ALERTS_PER_SUBSCRIBER_PER_DAY` | `3` alerts / day | Caps the maximum volume of emergency notifications a subscriber can receive in a 24-hour window, preventing loop triggers during extended severe heatwaves. |

---

## 5. Known Limitations & Production Telecommunications Requirements in India

> [!WARNING]
> **Prototype Scope vs. Production Reality**:  
> The current SIH26083 implementation is an operational **engineering prototype** utilizing Twilio and Gupshup developer sandbox gateways. While the system implements industry-standard double opt-in and STOP compliance logic, deploying this system to millions of Indian citizens in a real-world municipal production environment requires formal telecom registrations described below.

### Indian Regulatory Mandates (TRAI & DLT)

For live production deployment across Indian telecommunications networks (Airtel, Reliance Jio, Vodafone Idea, BSNL), the following regulatory steps are legally required:

1. **TRAI Commercial Communications Customer Preference Regulations (TCCCPR, 2018)**:
   - **DLT (Distributed Ledger Technology) Registration**: Municipal authorities must register as a Principal Entity (PE) on telecom operator DLT portals (e.g. Jio DLT, Vilpower, Airtel DLT).
   - **Header / Sender ID Approval**: Registration of alphanumeric Sender IDs (e.g. `AMC-HEAT`, `NDMA-ALERT`, or `GSDMA-WARN`).
   - **Content Template Registration**: Every SMS format (confirmation notice, heat caution, extreme heat alert, unsubscribe notice) must be pre-approved with defined variable placeholders (e.g. `{#var#}`) to prevent telecom network blocking.
2. **Service / Transactional Category vs. DND**:
   - Because heat warnings protect human life, they should be classified as **"Service Implicit"** or **"Service Explicit"** rather than "Promotional".
   - Service category approval ensures alerts are delivered even to numbers registered on the National Do Not Call (NDNC / DND) Registry, which is critical for disaster management.
3. **160 / 140 Series Dedicated Prefixes**:
   - Recent TRAI directives mandate that government and transactional service notifications migrate to standardized `160` series number prefixes to distinguish authentic civic alerts from spoofed commercial traffic.
4. **WhatsApp Business API (Meta) Guidelines**:
   - Sending WhatsApp notifications at scale requires verified Meta Business Manager accounts and pre-approved Message Templates (Utility category).

---

## 6. Message Delivery Architecture: Sandbox Simulation vs. Live Gateway

| Mode | Trigger Condition | Delivery Mechanism | How Citizen Receives |
| :--- | :--- | :--- | :--- |
| **🟡 Sandbox Simulation (Default)** | No Twilio API keys set, or test environment | Backend registers subscriber in database, generates tracking SID (`SM...` or `WA...`), logs consent audit, and displays the exact message bubble on the web UI. | **On-Screen Message Bubble + 1-Click WhatsApp Link** (`https://api.whatsapp.com/send?...`) allowing the user to open or forward the exact alert in WhatsApp or SMS immediately, plus native browser notifications. |
| **🟢 Live Carrier Dispatch** | `TWILIO_ACCOUNT_SID` & `TWILIO_AUTH_TOKEN` set | Transmitted via Twilio REST API to telecom operators or WhatsApp servers. | Delivered directly to physical phone. *(Note: For Twilio WhatsApp Sandbox, user must first send `join <keyword>` to `+1 415 523 8886` as required by Meta policy).* |

---

## 7. Summary Checklist

- [x] Double opt-in confirmation message dispatched immediately upon signup.
- [x] Automated webhook handler for `STOP` / `UNSUBSCRIBE` keyword deactivation.
- [x] Immutable `consent_logs` table tracking opt-in and opt-out timestamps.
- [x] Rate limiting: Max 3 subscription attempts per phone per hour.
- [x] Daily cap: Max 3 alerts per subscriber per day.
- [x] On-screen message bubble & 1-click WhatsApp web dispatch for sandbox mode.
- [x] Documented roadmap for TRAI DLT registration and DND compliance.
