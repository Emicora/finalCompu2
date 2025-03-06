# Informe de Diseño e Implementación
## 1. Introducción

Este proyecto implementa un sistema de notificaciones en vivo basado en una arquitectura cliente-servidor. El sistema permite que múltiples clientes se conecten mediante sockets TCP para recibir notificaciones en tiempo real y, simultáneamente, se registren sus suscripciones de manera persistente en una base de datos SQLite. Además, se emplea Celery para delegar tareas en segundo plano, como el envío de correos electrónicos, y se utiliza un proceso worker (mediante multiprocessing) para desacoplar las operaciones de I/O intensivas del servidor principal.
## 2. Decisiones de Diseño
### 2.1 Conexión y Concurrencia

    Uso de Sockets TCP con asyncio:
    Se eligió TCP para garantizar la entrega confiable y ordenada de mensajes. La utilización de asyncio permite gestionar múltiples conexiones en un solo proceso de forma eficiente y sin la sobrecarga de hilos o procesos adicionales.

    Dual-Stack (IPv4 e IPv6):
    Se utiliza socket.getaddrinfo con el parámetro AF_UNSPEC para obtener información de dirección, lo que permite que se resuelvan tanto direcciones IPv4 como IPv6. Se utiliza el primer resultado obtenido para crear el socket con la familia de direcciones correspondiente. Si se crea un socket IPv6, se desactiva la opción IPV6_V6ONLY para permitir conexiones tanto IPv6 como IPv4 (modo dual-stack). Esto facilita la interoperabilidad en redes modernas y permite que el sistema se despliegue en diferentes entornos de red sin modificaciones. En cambio, si el servidor se ejecuta con una dirección IPv4, el socket solo aceptará clientes IPv4.

    Multiprocesamiento:
    Se utiliza un proceso independiente para registrar las suscripciones en una base de datos. Esto desacopla el manejo en tiempo real de las conexiones (realizado mediante asyncio) de las operaciones de I/O (registro en la base de datos), mejorando la capacidad de respuesta y escalabilidad del sistema.

### 2.2 Almacenamiento y Modelo de Datos

    Uso de SQLite:
    Se optó por SQLite como base de datos para almacenar las suscripciones (email, evento y timestamp) debido a su sencillez, ligereza y facilidad de integración en proyectos pequeños a medianos.
    Cola de Mensajes:
    Se emplea multiprocessing.Queue para pasar información de suscripciones desde el servidor al proceso worker, permitiendo un registro asíncrono y desacoplado de la base de datos.

### 2.3 Tareas en Segundo Plano con Celery

    Celery para tareas asíncronas:
    Se utiliza Celery para delegar tareas que pueden afectar la latencia del servidor, como el envío de correos electrónicos o el procesamiento de notificaciones. Esto permite que el servidor principal se mantenga ágil y responda en tiempo real, mientras que las tareas intensivas se procesan en segundo plano utilizando un broker (por ejemplo, Redis).

    Desacoplamiento y Escalabilidad:
    Al separar las tareas de envío de correos y procesamiento de notificaciones en workers independientes, el sistema es más escalable y se puede ampliar fácilmente agregando más workers según la demanda.

## 3. Justificación de las Decisiones

    Eficiencia y Rendimiento:
    El uso de asyncio para manejar conexiones concurrentes sin hilos adicionales, combinado con multiprocesamiento para operaciones de I/O, permite que el sistema procese muchas conexiones sin perder capacidad de respuesta.

    Facilidad de Desarrollo y Mantenimiento:
    Utilizar librerías y herramientas maduras (como Celery, SQLite y asyncio) reduce la complejidad en la implementación y facilita el mantenimiento, ya que se aprovechan soluciones probadas en producción.

    Flexibilidad en el Despliegue:
    La implementación dual-stack permite que el sistema se ejecute en redes IPv4 e IPv6. Además, la separación de tareas mediante Celery y un proceso worker facilita la integración en entornos distribuidos y escalables.