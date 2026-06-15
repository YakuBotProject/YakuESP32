import os
import json
from pywebpush import webpush, WebPushException
from dotenv import load_dotenv

load_dotenv()

def enviar_webpush(subscription_info: dict, title: str, message: str) -> bool | str:
    """Envía una notificación Web Push cifrada usando pywebpush."""
    vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
    vapid_public_key = os.getenv("VAPID_PUBLIC_KEY")
    vapid_claims_email = os.getenv("VAPID_CLAIMS_EMAIL", "soporte@yaku.com")

    if not vapid_private_key or not vapid_public_key:
        print("[WEBPUSH] Advertencia: VAPID_PRIVATE_KEY o VAPID_PUBLIC_KEY no están configuradas en .env. Saltando envío push.")
        return False

    try:
        payload = {
            "title": title,
            "message": message
        }
        
        # Enviar notificación push
        response = webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": f"mailto:{vapid_claims_email}"}
        )
        
        print(f"[WEBPUSH] Notificación push enviada con éxito al endpoint: {subscription_info.get('endpoint')[:45]}...")
        return True
    except WebPushException as ex:
        print(f"[WEBPUSH] Error enviando Web Push: {ex}")
        # 410 o 404 significa que la suscripción caducó o el usuario bloqueó las notificaciones
        if ex.response is not None and ex.response.status_code in [404, 410]:
            print("[WEBPUSH] Suscripción expirada o bloqueada en el dispositivo final.")
            return "EXPIRED"
        return False
    except Exception as e:
        print(f"[WEBPUSH] Error inesperado en envío Web Push: {e}")
        return False
