import asyncio
import argparse
import json
from tasks import process_notification, send_email_notification  # Importamos tareas de Celery

# Lista de eventos predefinidos
VALID_EVENTS = {"Natacion", "Pilates", "Yoga", "Boxeo", "Tenis"}

# Diccionario para almacenar las suscripciones:
# { "evento": [ {"writer": writer, "email": email}, ... ], ... }
subscriptions = {}

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"Conexión establecida con {addr}")

    # Enviar la lista de eventos disponibles al cliente al conectarse
    welcome_msg = {
        "message": "Bienvenido. Estos son los eventos disponibles:",
        "events": list(VALID_EVENTS)
    }
    writer.write((json.dumps(welcome_msg) + "\n").encode())
    await writer.drain()

    try:
        while True:
            data = await reader.readline()
            if not data:
                break  # El cliente cerró la conexión

            message = data.decode().strip()
            try:
                msg = json.loads(message)
            except json.JSONDecodeError:
                writer.write("Mensaje inválido. Se esperaba formato JSON.\n".encode())
                await writer.drain()
                continue

            # Se espera el formato: 
            # {"action": "subscribe", "event": "nombre_evento", "email": "usuario@example.com"}
            if msg.get("action") == "subscribe":
                event = msg.get("event")
                email = msg.get("email")  # Se puede enviar opcionalmente
                if event:
                    # Validar que el evento esté en la lista predefinida
                    if event not in VALID_EVENTS:
                        writer.write(
                            f"El evento '{event}' no es válido. Eventos permitidos: {', '.join(VALID_EVENTS)}\n".encode()
                        )
                        await writer.drain()
                        continue
                    # Guardamos el writer y el email (o None si no se envió)
                    subscriber = {"writer": writer, "email": email}
                    subscriptions.setdefault(event, []).append(subscriber)
                    print(f"{addr} se suscribió al evento '{event}' con email: {email}")
                    writer.write(f"Suscripción al evento '{event}' exitosa.\n".encode())
                    await writer.drain()
                else:
                    writer.write("No se especificó el nombre del evento.\n".encode())
                    await writer.drain()
            else:
                writer.write("Acción desconocida.\n".encode())
                await writer.drain()
    except Exception as e:
        print(f"Error al manejar a {addr}: {e}")
    finally:
        print(f"Cerrando conexión con {addr}")
        writer.close()
        await writer.wait_closed()

async def console_handler(shutdown_event):
    """Lee comandos desde la consola del servidor y envía notificaciones."""
    loop = asyncio.get_event_loop()
    while not shutdown_event.is_set():
        command = await loop.run_in_executor(None, input, ">> ")
        if command.startswith("send"):
            parts = command.split(" ", 2)
            if len(parts) < 3:
                print("Formato inválido. Uso: send <evento> <mensaje>")
                continue
            event = parts[1]
            message = parts[2]
            print("Procesando notificación mediante Celery...")
            try:
                result = await loop.run_in_executor(
                    None, lambda: process_notification.delay(event, message).get(timeout=10)
                )
                print("Resultado del procesamiento:", result)
            except Exception as e:
                print("Error en el procesamiento distribuido:", e)
                continue

            # Envío de notificación vía socket y por email a los suscriptores
            if event in subscriptions:
                for subscriber in subscriptions[event]:
                    # Enviar notificación vía socket
                    subscriber["writer"].write((f"Notificación de {event}: {message}\n").encode())
                    try:
                        await subscriber["writer"].drain()
                    except Exception as e:
                        print(f"Error al enviar a un suscriptor vía socket: {e}")

                    # Enviar email si se proporcionó
                    if subscriber["email"]:
                        try:
                            email_result = await loop.run_in_executor(
                                None, lambda: send_email_notification.delay(subscriber["email"], event, message).get(timeout=15)
                            )
                            print(f"Email enviado a {subscriber['email']}: {email_result}")
                        except Exception as e:
                            print(f"Error al enviar email a {subscriber['email']}: {e}")
                print(f"Notificación enviada a los suscriptores del evento '{event}'")
            else:
                print(f"No hay suscriptores para el evento '{event}'")
        elif command.strip() == "exit":
            print("Saliendo del servidor...")
            shutdown_event.set()
            # Cerrar conexiones de clientes
            for event, subscribers in subscriptions.items():
                for subscriber in subscribers:
                    subscriber["writer"].close()
            break
        else:
            print("Comando no reconocido. Usa 'send <evento> <mensaje>' o 'exit'.")

async def main(host, port):
    shutdown_event = asyncio.Event()
    server = await asyncio.start_server(handle_client, host, port)
    addr = server.sockets[0].getsockname()
    print(f"Servidor corriendo en {addr}")

    console_task = asyncio.create_task(console_handler(shutdown_event))
    server_task = asyncio.create_task(server.serve_forever())

    await shutdown_event.wait()

    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        print("Servidor cerrado correctamente.")

    await console_task

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor de Notificaciones en Vivo")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host del servidor")
    parser.add_argument("--port", type=int, default=8888, help="Puerto del servidor")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
