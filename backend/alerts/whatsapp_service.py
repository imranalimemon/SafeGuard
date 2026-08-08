from config import settings

async def send_whatsapp_alert(violation_data):
    if not settings.ENABLE_WHATSAPP_ALERTS:
        return False
        
    try:
        from twilio.rest import Client
        
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        missing = violation_data.get('missing_ppe', 'Unknown')
        time_str = violation_data.get('timestamp', 'Unknown')
        
        message_body = f"SafeGuard AI - PPE VIOLATION DETECTED\nTimestamp: {time_str}\nMissing PPE: {missing}\nWorker Count: {violation_data.get('person_count', 1)}"
        
        message = client.messages.create(
            from_=f"whatsapp:{settings.TWILIO_WHATSAPP_FROM}",
            body=message_body,
            to=f"whatsapp:{settings.ALERT_WHATSAPP_TO}"
        )
        return True
    except ImportError:
        return False
    except Exception as e:
        return False
