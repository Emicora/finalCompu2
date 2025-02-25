import asyncio
import argparse
import json
from tasks import process_notification  # Importamos la tarea de Celery

# Diccionario para almacenar las suscripciones: { "evento": [writer1, writer2, ...], ... }
subscriptions = {}

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"Conexión establecida con {addr}")

    while True:
        try:
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

            # Se espera el formato: {"action": "subscribe", "event": "nombre_evento"}
            if msg.get("action") == "subscribe":
                event = msg.get("event")
                if event:
                    subscriptions.setdefault(event, []).append(writer)
                    print(f"{addr} se suscribió al evento '{event}'")
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
            break

    print(f"Cerrando conexión con {addr}")
    writer.close()
    await writer.wait_closed()

async def console_handler():
    """Lee comandos desde la consola del servidor y envía notificaciones."""
    loop = asyncio.get_event_loop()
    while True:
        # run_in_executor evita bloquear el loop principal con input()
        command = await loop.run_in_executor(None, input, ">> ")
        if command.startswith("send"):
            parts = command.split(" ", 2)
            if len(parts) < 3:
                print("Formato inválido. Uso: send <evento> <mensaje>")
                continue
            event = parts[1]
            message = parts[2]
            # Llamamos a la tarea de Celery para procesar la notificación
            print("Procesando notificación mediante Celery...")
            try:
                # Se utiliza run_in_executor para no bloquear el loop al esperar el resultado
                result = await loop.run_in_executor(None, lambda: process_notification.delay(event, message).get(timeout=10))
                print("Resultado del procesamiento:", result)
            except Exception as e:
                print("Error en el procesamiento distribuido:", e)
                continue

            # Envío de notificación a clientes suscritos
            if event in subscriptions:
                for writer in subscriptions[event]:
                    writer.write((f"Notificación: {message}\n").encode())
                    try:
                        await writer.drain()
                    except Exception as e:
                        print(f"Error al enviar a un suscriptor: {e}")
                print(f"Notificación enviada a los suscriptores del evento '{event}'")
            else:
                print(f"No hay suscriptores para el evento '{event}'")
        elif command.strip() == "exit":
            print("Saliendo del servidor...")
            # Aquí se podría implementar un cierre ordenado de conexiones y del servidor
            for event, writers in subscriptions.items():
                for writer in writers:
                    writer.close()
            break
        else:
            print("Comando no reconocido. Usa 'send <evento> <mensaje>' o 'exit'.")

async def main(host, port):
    server = await asyncio.start_server(handle_client, host, port)
    addr = server.sockets[0].getsockname()
    print(f"Servidor corriendo en {addr}")

    # Iniciar el handler de comandos de consola en una tarea concurrente
    asyncio.create_task(console_handler())

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor de Notificaciones en Vivo")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host del servidor")
    parser.add_argument("--port", type=int, default=8888, help="Puerto del servidor")
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
