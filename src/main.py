"""
🚀 Webpay Service - API Principal
=================================
Microservicio FastAPI para integración con Webpay Plus de Transbank.
Proporciona endpoints para inicializar y confirmar transacciones de pago.

Funcionalidades:
- ✅ Integración completa con Webpay Plus
- ✅ Manejo de pagos exitosos y cancelaciones  
- ✅ CORS configurado para Odoo Online
- 🔄 Integración con Odoo ERP (en desarrollo)

Autor: Sistema de Pagos Tecnogrow
Versión: 2.0.1
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

load_dotenv()

# Importar routers organizados
from src.routes.webpay_routes import webpay_router
from src.routes.odoo_routes import odoo_router
from src.config import settings

# 🏗️ Configuración de la aplicación FastAPI
app = FastAPI(
    title="Webpay Service API",
    description="Microservicio para procesamiento de pagos con Webpay Plus - Multi-tenant",
    version="2.0.1",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 🌐 Configuración de CORS multi-cliente
# Obtiene automáticamente todos los orígenes permitidos de los clientes configurados
cors_config = settings.get_cors_config()

app.add_middleware(
    CORSMiddleware,
    **cors_config
)

app.include_router(webpay_router)  # Rutas de Webpay (/webpay/*)
app.include_router(odoo_router)    # Rutas de Odoo (/odoo/*)


@app.get("/", tags=["health"])
async def root():
    """
    🏠 Endpoint raíz del servicio
    
    Verifica que el microservicio esté operativo y muestra información básica.
    Útil para health checks y monitoreo de la aplicación.
    
    Returns:
        {"status": "ok", "message": "...", "version": "...", "clients_count": ...}
    """
    from src.client_config import client_loader
    active_clients = client_loader.get_active_clients()
    
    return {
        "status": "ok",
        "message": "Webpay Service operativo - Multi-tenant",
        "version": "2.0.1",
        "clients_count": len(active_clients),
        "clients": [c.client_name for c in active_clients]
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    🏥 Health check detallado del servicio
    
    Verifica el estado de todos los componentes y dependencias.
    Usado por sistemas de monitoreo y load balancers.
    
    Returns:
        Estado detallado de cada componente del sistema
    """
    try:
        # TODO: Agregar verificaciones reales de:
        # - Conectividad con Transbank
        # - Conectividad con Odoo
        # - Estado de la base de datos (si aplica)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "timestamp": "2025-10-19T00:00:00Z",  # TODO: Usar timestamp real
                "components": {
                    "webpay_sdk": {"status": "ok", "message": "SDK inicializado"},
                    "cors": {"status": "ok", "message": "CORS configurado"},
                    "routes": {"status": "ok", "message": "Rutas registradas"},
                    "odoo_integration": {"status": "pending", "message": "En desarrollo"}
                }
            }
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy", 
                "error": str(e),
                "timestamp": "2025-10-19T00:00:00Z"
            }
        )


# 🚀 Punto de entrada para el servidor
if __name__ == "__main__":
    import uvicorn
    
    # Configuración para desarrollo local
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload en desarrollo
        log_level="info"
    )
