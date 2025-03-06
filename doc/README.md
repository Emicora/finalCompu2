# Sistema de Notificaciones en Vivo

Este proyecto implementa un sistema de notificaciones en vivo basado en una arquitectura cliente-servidor. El servidor utiliza `asyncio` para manejar múltiples conexiones de clientes, registra las suscripciones en una base de datos SQLite mediante un worker de multiprocesamiento, y delega tareas pesadas (como el envío de correos electrónicos) a Celery.

---

## Características Principales

- **Conexiones Concurrentes:**  
  El servidor utiliza `asyncio` para gestionar múltiples clientes de manera asíncrona en un solo proceso.

- **Dual-Stack (IPv4 e IPv6):**  
  El servidor se puede iniciar en modo dual-stack para aceptar conexiones tanto de IPv4 como de IPv6 mediante la configuración manual de un socket.

- **Registro de Suscripciones en Base de Datos:**  
  Las suscripciones se registran en una base de datos SQLite a través de un proceso worker que consume mensajes de una cola de multiprocesamiento.

- **Tareas en Segundo Plano con Celery:**  
  Se delegan tareas costosas (como el envío de correos electrónicos) a Celery, permitiendo que el servidor se mantenga ágil.

- **Interfaz de Consola:**  
  El servidor permite enviar notificaciones y administrar el sistema desde una consola interactiva.

---

## Uso Básico

### Servidor

1. **Instalación y Configuración:**  
   Consulta el archivo `INSTALL.md` para instrucciones sobre cómo clonar el repositorio, crear el entorno virtual e instalar las dependencias.

2. **Iniciar el Servidor:**  
   - **Dual-Stack (IPv4 e IPv6):**
     ```bash
     python server.py --host "::" --port 8888
     ```
   - **Solo IPv4:**
     ```bash
     python server.py --host "127.0.0.1" --port 8888
     ```
   El servidor mostrará un mensaje indicando en qué dirección y puerto está corriendo.

3. **Comandos de la Consola del Servidor:**  
   - `send <evento> <mensaje>`: Envía una notificación a todos los clientes suscritos al evento especificado.
   - `exit`: Cierra el servidor y todas las conexiones activas.

### Cliente

1. **Iniciar el Cliente:**  
   Activa el entorno virtual y ejecuta uno de los siguientes comandos, según el protocolo deseado:
   - **IPv6:**
     ```bash
     python client.py --host "::1" --port 8888
     ```
   - **IPv4:**
     ```bash
     python client.py --host "127.0.0.1" --port 8888
     ```

2. **Registro y Suscripción:**  
   Al conectarse, el cliente recibe la lista de eventos disponibles y debe registrarse enviando su email. Luego puede suscribirse a uno o varios eventos mediante comandos interactivos.

3. **Recepción de Notificaciones:**  
   El cliente recibe notificaciones en tiempo real enviadas por el servidor.

4. **Cerrar el Cliente:**  
   Escribe `exit` en la consola del cliente para finalizar la conexión.

---

## Consideraciones Adicionales

- **Base de Datos:**  
  Las suscripciones se registran en la base de datos SQLite (`subscriptions.db`) a través de un worker independiente.

- **Celery y Redis:**  
  Las tareas que pueden afectar la latencia del servidor, como el envío de correos electrónicos, se delegan a Celery. Asegúrate de tener un broker (como Redis) corriendo y de iniciar el worker de Celery según las instrucciones del `INSTALL.md`.

- **Dual-Stack:**  
  Iniciar el servidor con una dirección IPv6 (por ejemplo, `"::"`) y con la opción dual-stack desactivada (IPV6_V6ONLY = 0) permite que acepte conexiones tanto de IPv4 como de IPv6. Si se inicia con una dirección IPv4, solo aceptará clientes IPv4.

---


