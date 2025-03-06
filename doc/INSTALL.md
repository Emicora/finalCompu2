## Requisitos Previos

-   Python 3.7+ (se recomienda la versión 3.8 o superior)
-   Git (para clonar el repositorio)
-   Redis (para que Celery actúe como broker y backend de resultados)

## Clonación del Repositorio

### Para clonar el repositorio, ejecuta en tu terminal:

```
git clone <git@github.com:Emicora/finalCompu2.git>
cd <finalCompu2>
```

### Luego ejecutar:

```
./install.sh
```

Para crear el entorno virtual y descargar las librerías.

## Ejecución de Celery

Utilizar el siguiente comando en el directorio `finalCompu2/server`:

```
celery -A tasks worker --loglevel=info
```

## Ejecución del Servidor

Ejecutar el siguiente comando en el directorio `finalCompu2/server`:

```
python server.py --host "::" --port 8888
```
o
```
python server.py --host 127.0.0.1 --port 8888
```

## Ejecución de Clientes

Ejecutar el siguiente comando en el directorio `finalCompu2/client`:

```
python client.py --host "::1" --port 8888
```
o
```
python client.py --host 127.0.0.1 --port 8888
```
