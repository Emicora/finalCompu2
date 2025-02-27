import time
import smtplib
from email.mime.text import MIMEText
from celery import Celery

# Configuración de Celery (usa Redis como broker y backend)
app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

# Configuración del servidor SMTP para envío de correos con Gmail
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # Puerto para TLS
FROM_ADDRESS = "alaskaa2501@gmail.com"       # Cambia esto por tu correo
SMTP_USER = "alaskaa2501@gmail.com"            # Tu usuario, generalmente tu correo
SMTP_PASSWORD = "jbge fjhq gqzj mbtm"          # La contraseña de aplicación que generaste

@app.task
def process_notification(event, message):
    # Simula procesamiento costoso o validaciones
    time.sleep(2)
    return f"Notificación procesada para el evento '{event}': {message}"

@app.task
def send_email_notification(subscriber_email, event, message):
    subject = f"Notificación para el evento {event}"
    body = (
        f"Hola,\n\n"
        f"Se ha generado la siguiente notificación para el evento '{event}':\n"
        f"{message}\n\n"
        f"Saludos."
    )
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = FROM_ADDRESS
    msg['To'] = subscriber_email

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()            # Saludo inicial
            server.starttls()        # Inicia conexión segura TLS
            server.ehlo()            # Saludo tras iniciar TLS
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return f"Email enviado a {subscriber_email} para el evento '{event}'"
    except Exception as e:
        return f"Error al enviar email a {subscriber_email}: {e}"
