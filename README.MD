# Webpay Service

Microservicio basado en FastAPI que expone endpoints de integracion con Webpay Plus de Transbank. El servicio permite iniciar transacciones de prueba y recibir el commit de Webpay para completar el flujo de pago.

## Requisitos previos

- Python 3.10 o superior (`python3 --version`)
- `pip` actualizado (`python3 -m pip install --upgrade pip`)
- Acceso a internet para instalar dependencias

## Creacion del entorno

1. Clonar o descargar este repositorio dentro de tu workspace.
2. Crear un entorno virtual: `python3 -m venv venv`
3. Activar el entorno:
   - macOS/Linux: `source venv/bin/activate`
   - Windows PowerShell: `.\venv\Scripts\activate.bat`
   - Windows CMD: `venv\Scripts\activate.bat`
   - Si tienes permisos de PowerShell: `.\venv\Scripts\Activate.ps1`
4. Opcional: actualizar herramientas base dentro del entorno activado.

Para desactivar el entorno basta con ejecutar `deactivate`.

## Instalacion de dependencias

Con el entorno activo instala los paquetes necesarios:

```bash
pip install -r requirements.txt
```

Puedes congelar la lista para despliegues posteriores:

```bash
pip freeze > requirements.txt
```

## Ejecutar el microservicio

1. Asegurate de tener el entorno virtual activo.
2. Inicia el servidor de desarrollo:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

3. Abre `http://localhost:8000` para verificar el estado (`{"msg": "Servidor Webpay operativo"}`).
4. La documentacion interactiva de FastAPI queda disponible en `http://localhost:8000/docs`.

## Endpoints principales

| Metodo | Ruta             | Descripcion                                                |
|--------|------------------|------------------------------------------------------------|
| GET    | `/`              | Verifica que el microservicio este vivo.                   |
| POST   | `/webpay/init`   | Crea un token de transaccion contra el ambiente de prueba. |
| POST   | `/webpay/commit` | Recibe el callback de Webpay y confirma la transaccion.    |

### Flujo recomendado

1. Invoca `POST /webpay/init` enviando un JSON con `amount` (opcional, valor por defecto 1000).
2. Utiliza el `token` y la `url` que entrega Transbank para redirigir al cliente al formulario Webpay.
3. Configura Webpay para que haga POST al endpoint `/webpay/commit` de este servicio con el campo `token_ws`.
4. Revisa la respuesta JSON retornada por `commit` para obtener el estado final de la transaccion.

## Comprension del proyecto

La logica principal vive en `src/main.py`, donde se instancia `FastAPI` y se configura la clase `Transaction` del SDK de Transbank con los codigos y llaves de integracion. El proyecto actualmente usa el ambiente de prueba de Transbank (`https://webpay3gint.transbank.cl`) y genera ordenes de compra y sesiones de manera simplificada para demostracion.

## Estructura del repositorio

```
.
├── README.MD
├── src
│   ├── __init__.py
│   └── main.py
└── venv/              # Entorno virtual sugerido (no se versiona)
```

## Pasos siguientes sugeridos

- Agregar manejo de variables de entorno para los codigos/llaves productivos.
- Implementar almacenamiento persistente del estado de las transacciones.
- Escribir pruebas automaticas que cubran los flujos principales.

## url de prueba
https://webpay3gint.transbank.cl/webpayserver/initTransaction?token_ws=01ab3321e3f70dedc382e6a09d54a9665bd6422d4eedf6bcf407a43b00a0a3e1

## Tarjeta de Prueba
4051 8856 0044 6623 - 05/28 - 123

## Cuenta de prueba 
11.111.111-1
123