import asyncio
import argparse
import json
from tasks import process_notification, send_email_notification  # Importamos tareas de Celery

# Lista de eventos predefinidos
VALID_EVENTS = {"Natacion", "Pilates", "Yoga", "Boxeo", "Tenis"}

# Diccionario para almacenar las suscripciones:
# { "evento": [ {"writer": writer, "email": email}, ... ], ... }
subscriptions = {}

# Conjunto global para rastrear emails registrados entre clientes conectados
registered_emails = set()

# Conjunto global para rastrear todas las conexiones activas
active_clients = set()

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"Conexión establecida con {addr}")
    active_clients.add(writer)

    # Enviar mensaje de bienvenida, lista de eventos
    welcome_msg = {
        "message": "Bienvenido. Estos son los eventos disponibles:",
        "events": list(VALID_EVENTS)
    }
    writer.write((json.dumps(welcome_msg) + "\n").encode())
    await writer.drain()

    client_email = None
    # Bucle para gestionar el registro de email
    while True:
        data = await reader.readline()
        if not data:
            break  # El cliente cerró la conexión
        try:
            msg = json.loads(data.decode().strip())
        except json.JSONDecodeError:
            writer.write("Mensaje inválido. Se esperaba formato JSON.\n".encode())
            await writer.drain()
            continue

        if msg.get("action") == "register":
            email = msg.get("email")
            if not email:
                writer.write("No se proporcionó email. Intenta de nuevo.\n".encode())
                await writer.drain()
                continue
            if email in registered_emails:
                writer.write(f"El email '{email}' ya está en uso. Por favor, ingresa otro email.\n".encode())
                await writer.drain()
            else:
                registered_emails.add(email)
                client_email = email
                writer.write(f"Registro exitoso con el email '{email}'.\n".encode())
                await writer.drain()
                break
        else:
            writer.write("Debes registrarte primero. Usa: {\"action\": \"register\", \"email\": \"tu_email\"}\n".encode())
            await writer.drain()

    if not client_email:
        writer.close()
        await writer.wait_closed()
        active_clients.discard(writer)
        return

    # Procesar solicitudes de suscripción y otras acciones
    try:
        while True:
            data = await reader.readline()
            if not data:
                break  # El cliente cerró la conexión
            try:
                msg = json.loads(data.decode().strip())
            except json.JSONDecodeError:
                writer.write("Mensaje inválido. Se esperaba formato JSON.\n".encode())
                await writer.drain()
                continue

            # Se espera el formato: {"action": "subscribe", "event": "nombre_evento"}
            if msg.get("action") == "subscribe":
                event = msg.get("event")
                if not event:
                    writer.write("No se especificó el nombre del evento.\n".encode())
                    await writer.drain()
                    continue
                if event not in VALID_EVENTS:
                    writer.write(f"El evento '{event}' no es válido. Eventos permitidos: {', '.join(VALID_EVENTS)}\n".encode())
                    await writer.drain()
                    continue

                # Verificar si ya está suscrito al evento
                current_subs = subscriptions.get(event, [])
                if any(subscriber["email"] == client_email for subscriber in current_subs):
                    writer.write(f"Ya estás suscrito al evento '{event}'.\n".encode())
                    await writer.drain()
                    continue

                subscriber = {"writer": writer, "email": client_email}
                subscriptions.setdefault(event, []).append(subscriber)
                print(f"{addr} se suscribió al evento '{event}' con email: {client_email}")
                writer.write(f"Suscripción al evento '{event}' exitosa.\n".encode())
                await writer.drain()
            else:
                writer.write("Acción desconocida.\n".encode())
                await writer.drain()
    except Exception as e:
        print(f"Error al manejar a {addr}: {e}")
    finally:
        print(f"Cerrando conexión con {addr}")
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        active_clients.discard(writer)
        if client_email in registered_emails:
            registered_emails.remove(client_email)

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

            if event in subscriptions:
                for subscriber in subscriptions[event]:
                    subscriber["writer"].write((f"Notificación de {event}: {message}\n").encode())
                    try:
                        await subscriber["writer"].drain()
                    except Exception as e:
                        print(f"Error al enviar a un suscriptor vía socket: {e}")
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
            for writer in list(active_clients):
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
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
