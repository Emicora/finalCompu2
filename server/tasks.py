from celery import Celery
import time

# Configuración de Celery usando Redis como broker y backend.
app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@app.task
def process_notification(event, message):
    # Simula una tarea costosa (por ejemplo, procesamiento, logging, etc.)
    time.sleep(2)  # Simula un retardo en el procesamiento
    return f"Notificación procesada para el evento '{event}': {message}"
