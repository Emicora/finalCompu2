import asyncio
import argparse
import json

async def interactive_client(host, port):
    loop = asyncio.get_event_loop()
    # Conectarse al servidor
    reader, writer = await asyncio.open_connection(host, port)
    print("Conectado al servidor.")

    # Esperar el mensaje de bienvenida del servidor (que incluye la lista de eventos y el prompt)
    data = await reader.readline()
    if not data:
        print("El servidor no respondió.")
        return
    welcome = data.decode().strip()
    print("Mensaje del servidor:", welcome)

    # Registro del email: se repite hasta que el servidor confirme el registro exitoso.
    email = None
    while True:
        email = await loop.run_in_executor(None, input, "Ingresa tu email: ")
        reg_msg = {"action": "register", "email": email}
        writer.write((json.dumps(reg_msg) + "\n").encode())
        await writer.drain()
        # Espera la respuesta del servidor al registro
        response = await reader.readline()
        if not response:
            print("El servidor cerró la conexión durante el registro.")
            writer.close()
            await writer.wait_closed()
            return
        response_text = response.decode().strip()
        print("Respuesta del servidor:", response_text)
        # Si la respuesta contiene "Registro exitoso", se acepta el email
        if "Registro exitoso" in response_text:
            break
        else:
            print("El email ingresado ya está en uso o hubo un error. Intenta nuevamente.")

    print("Registro completado. Ahora puedes usar el comando: subscribe <nombre_evento>")
    print("Escribe 'exit' para cerrar el cliente.")

    # Tarea para escuchar mensajes del servidor de forma continua
    async def listen_server():
        while True:
            data = await reader.readline()
            if not data:
                print("El servidor cerró la conexión.")
                break
            print("Mensaje del servidor:", data.decode().strip())

    asyncio.create_task(listen_server())

    # Bucle de comandos del usuario
    while True:
        command = await loop.run_in_executor(None, input, ">> ")
        if command.startswith("subscribe"):
            parts = command.split(" ", 1)
            if len(parts) < 2:
                print("Uso: subscribe <nombre_evento>")
                continue
            event = parts[1].strip()
            # Enviar suscripción con el email registrado
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
