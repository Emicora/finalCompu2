import asyncio
import argparse
import json
import sqlite3
import multiprocessing
import time
import socket
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

# Cola de mensajes para registrar suscripciones en la base de datos
subscription_queue = multiprocessing.Queue()


def subscription_worker(queue):
    """
    Worker que consume mensajes de suscripción de la cola e inserta los registros en una base de datos SQLite.
    """
    conn = sqlite3.connect("subscriptions.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            event TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    while True:
        item = queue.get()
        if item == "STOP":
            break
        email = item.get("email")
        event = item.get("event")
        try:
            c.execute("INSERT INTO subscriptions (email, event) VALUES (?, ?)", (email, event))
            conn.commit()
            print(f"[DB] Suscripción registrada: {email} -> {event}")
        except Exception as e:
            print(f"[DB] Error al insertar suscripción: {e}")
    conn.close()


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

    # Si no se registró, se cierra la conexión.
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

                # Registrar la suscripción en memoria para notificaciones en tiempo real
                subscriber = {"writer": writer, "email": client_email}
                subscriptions.setdefault(event, []).append(subscriber)
                writer.write(f"Suscripción al evento '{event}' exitosa.\n".encode())
                await writer.drain()
                print(f"{addr} se suscribió al evento '{event}' con email: {client_email}")

                # Enviar el registro a la cola para guardarlo en la base de datos
                subscription_queue.put({"email": client_email, "event": event})
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
            # Cerrar todas las conexiones activas
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

    # Crear un socket IPv6 y desactivar IPV6_V6ONLY para aceptar conexiones IPv4 también
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen()
    sock.setblocking(False)

    server = await asyncio.start_server(handle_client, sock=sock)
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
    # Iniciar el worker de suscripciones en un proceso separado
    worker_process = multiprocessing.Process(target=subscription_worker, args=(subscription_queue,))
    worker_process.start()

    parser = argparse.ArgumentParser(description="Servidor de Notificaciones en Vivo")
    parser.add_argument("--host", type=str, default="::", help="Host del servidor (dual-stack: '::' para IPv6 y IPv4)")
    parser.add_argument("--port", type=int, default=8888, help="Puerto del servidor")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.host, args.port))
    finally:
        # Parar el worker y esperar a que finalice
        subscription_queue.put("STOP")
        worker_process.join()
