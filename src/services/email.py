import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

def enviar_correo_alerta(destinatario: str, asunto: str, mensaje: str) -> bool:
    """Envía un correo electrónico de alerta de forma síncrona usando SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[EMAIL] Advertencia: SMTP_USER o SMTP_PASSWORD no están configurados en el archivo .env. Saltando envío de correo.")
        return False
    
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = destinatario
        msg["Subject"] = asunto

        msg.attach(MIMEText(mensaje, "plain", "utf-8"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, destinatario, msg.as_string())
        server.quit()
        
        print(f"[EMAIL] Correo enviado con éxito a {destinatario}")
        return True
    except Exception as e:
        print(f"[EMAIL] Falló el envío de correo a {destinatario}: {e}")
        return False
