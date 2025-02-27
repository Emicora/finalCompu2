import asyncio
import argparse
import json

async def interactive_client(host, port):
    loop = asyncio.get_event_loop()
    # Pedir al usuario su email al inicio
    email = await loop.run_in_executor(None, input, "Ingresa tu email: ")

    # Conectarse al servidor
    reader, writer = await asyncio.open_connection(host, port)
    print("Conectado al servidor.")
    print("Usa el comando: subscribe <nombre_evento> para suscribirte a un evento.")
    print("Escribe 'exit' para cerrar el cliente.")

    async def listen_server():
        """Tarea que escucha continuamente los mensajes del servidor."""
        while True:
            data = await reader.readline()
            if not data:
                print("El servidor cerró la conexión.")
                break
            print("Mensaje del servidor:", data.decode().strip())

    # Iniciar la tarea para escuchar mensajes del servidor
    asyncio.create_task(listen_server())

    # Bucle para leer comandos del usuario
    while True:
        command = await loop.run_in_executor(None, input, ">> ")
        if command.startswith("subscribe"):
            parts = command.split(" ", 1)
            if len(parts) < 2:
                print("Uso: subscribe <nombre_evento>")
                continue
            event = parts[1].strip()
            # Enviar el JSON de suscripción con email incluido
            msg = {"action": "subscribe", "event": event, "email": email}
            writer.write((json.dumps(msg) + "\n").encode())
            await writer.drain()
        elif command.strip() == "exit":
            print("Cerrando cliente...")
            writer.close()
            await writer.wait_closed()
            break
        else:
            print("Comando no reconocido. Usa 'subscribe <nombre_evento>' o 'exit'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente Interactivo para Notificaciones en Vivo")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host del servidor")
    parser.add_argument("--port", type=int, default=8888, help="Puerto del servidor")
    args = parser.parse_args()
    asyncio.run(interactive_client(args.host, args.port))
