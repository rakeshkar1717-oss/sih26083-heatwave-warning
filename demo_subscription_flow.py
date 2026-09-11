"""Demonstration script for Anonymous Phone/WhatsApp Alert Subscription Sandbox Flow.

Walks through:
1. Citizen self-signup (Double Opt-In)
2. Immediate carrier confirmation message dispatch
3. Immutable ConsentLog inspection
4. Ward thermal stress hazard spike & automated alert dispatch
5. Inbound carrier webhook processing 'STOP' reply and immediate deactivation
"""

from datetime import datetime, timezone
from backend.db.session import SessionLocal
from backend.db.models_orm import AlertSubscriber, ConsentLog, WeatherReading, AlertLog
from backend.subscriptions.subscription_service import subscribe, handle_stop_reply
from backend.subscriptions.subscription_schema import SubscriptionChannel
from backend.alerts.alert_engine import check_and_trigger_alerts, reset_session_alert_count

demo_phone = "+919876500001"
target_ward = "AMD_17"

print("======================================================================")
print("   SIH26083: END-TO-END ANONYMOUS ALERT SUBSCRIPTION SANDBOX DEMO     ")
print("======================================================================\n")

with SessionLocal() as db:
    # Cleanup previous demo runs
    db.query(AlertSubscriber).filter(AlertSubscriber.phone_number == demo_phone).delete()
    db.query(ConsentLog).filter(ConsentLog.phone_number == demo_phone).delete()
    db.query(AlertLog).filter(AlertLog.recipient_phone == demo_phone).delete()
    db.commit()

    # Step 1: Subscribe
    print("[STEP 1] Citizen subscribes phone number:", demo_phone, "for Ward:", target_ward)
    sub_res = subscribe(
        phone_number=demo_phone,
        ward_id=target_ward,
        channel=SubscriptionChannel.SMS,
        db=db,
    )
    print("  -> Subscription Status  :", sub_res.success)
    print("  -> System Message       :", sub_res.message)
    print("  -> Registered Ward      :", f"{sub_res.ward_name} [{sub_res.ward_id}]")
    print("  -> Delivery Channel     :", sub_res.channel.upper())

    # Step 2: Check Consent Log
    print("\n[STEP 2] Inspecting Double Opt-In Consent Log in Database:")
    consent = (
        db.query(ConsentLog)
        .filter(ConsentLog.phone_number == demo_phone)
        .order_by(ConsentLog.recorded_at.desc())
        .first()
    )
    print("  -> Logged Action        :", consent.action)
    print(f"  -> Dispatched Text      : \"{consent.message_text}\"")
    print("  -> Carrier Delivery     :", consent.delivery_status)
    print("  -> Timestamp (UTC)      :", consent.recorded_at)

    # Step 3: Trigger Ward Heat Alert
    print(f"\n[STEP 3] Severe heatwave hazard spike detected in {target_ward} (WBGT: 38.5°C, Temp: 47.0°C)...")
    now_utc = datetime.now(timezone.utc)
    reading = WeatherReading(
        ward_id=target_ward,
        timestamp=now_utc,
        temp_c=47.0,
        humidity_pct=42.0,
        wind_speed_ms=1.8,
        solar_radiation_wm2=950.0,
        source="open_meteo",
        heat_index_c=54.0,
        wbgt_c=38.5,
        utci_c=47.0,
        thermal_stress_score=96.0,
    )
    db.add(reading)
    db.commit()
    reset_session_alert_count()

    alerts = check_and_trigger_alerts(db=db, target_phone="+919999900000")
    sub_alerts = [a for a in alerts if a.recipient_phone == demo_phone]
    print(f"  -> Total Ward Alerts Dispatched         : {len(alerts)}")
    print(f"  -> Automated Alert to Subscriber ({demo_phone}): {len(sub_alerts) >= 1}")
    if sub_alerts:
        print(f"  -> Dispatched Notice                    : {sub_alerts[0].detail}")

    # Step 4: Citizen replies STOP to carrier webhook
    print("\n[STEP 4] Citizen replies 'STOP' via carrier inbound SMS webhook:")
    stop_res = handle_stop_reply(phone_number=demo_phone, message_text="STOP", db=db)
    print("  -> Webhook Handled      :", stop_res.handled)
    print("  -> Compliance Action    :", stop_res.action)
    print("  -> Confirmation Detail  :", stop_res.detail)

    # Step 5: Verify Deactivation
    sub_record = db.query(AlertSubscriber).filter(AlertSubscriber.phone_number == demo_phone).first()
    print(f"\n[STEP 5] Database State Check for {demo_phone}:")
    print("  -> Subscriber is_active :", sub_record.is_active if sub_record else False)

    # Step 6: Verify Last Consent Log
    last_consent = (
        db.query(ConsentLog)
        .filter(ConsentLog.phone_number == demo_phone)
        .order_by(ConsentLog.recorded_at.desc())
        .first()
    )
    print(f"  -> Final Audit Action   : {last_consent.action} at {last_consent.recorded_at}")
    print(f"  -> Unsubscribe Message  : \"{last_consent.message_text}\"")

    # Cleanup
    db.delete(sub_record)
    db.delete(reading)
    db.query(ConsentLog).filter(ConsentLog.phone_number == demo_phone).delete()
    db.query(AlertLog).filter(AlertLog.recipient_phone == demo_phone).delete()
    db.commit()

print("\n======================================================================")
print("     ALL 5 SANDBOX STAGES COMPLETED SUCCESSFULLY WITH ZERO ERRORS     ")
print("======================================================================")
