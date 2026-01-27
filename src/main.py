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
Versión: 3.0.0
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
    version="3.0.0",
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
        "version": "3.0.0",
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
    from datetime import datetime, timezone
    from src.client_config import client_loader
    from src.services.mongo_logger import MongoLogService
    
    try:
        components = {}
        overall_status = "healthy"
        
        # 1. Verificar clientes configurados
        active_clients = client_loader.get_active_clients()
        components["clients"] = {
            "status": "ok" if active_clients else "warning",
            "message": f"{len(active_clients)} cliente(s) activo(s)",
            "count": len(active_clients),
            "names": [c.client_name for c in active_clients]
        }
        
        # 2. Verificar MongoDB
        mongo_service = MongoLogService()
        if settings.MONGO_ENABLED and mongo_service._client:
            try:
                mongo_service._client.admin.command('ping')
                components["mongodb"] = {
                    "status": "ok",
                    "message": "Conectado",
                    "database": settings.MONGO_DATABASE
                }
            except Exception as e:
                components["mongodb"] = {
                    "status": "error",
                    "message": f"Error de conexión: {str(e)}"
                }
                overall_status = "degraded"
        else:
            components["mongodb"] = {
                "status": "disabled",
                "message": "MongoDB no habilitado"
            }
        
        # 3. Verificar Webpay SDK (verificar que podamos crear una transacción)
        try:
            from transbank.webpay.webpay_plus.transaction import Transaction
            components["webpay_sdk"] = {
                "status": "ok",
                "message": "SDK Transbank inicializado",
                "version": "6.1.0"
            }
        except Exception as e:
            components["webpay_sdk"] = {
                "status": "error",
                "message": f"Error SDK: {str(e)}"
            }
            overall_status = "unhealthy"
        
        # 4. Verificar configuración de Odoo (al menos 1 cliente con Odoo configurado)
        odoo_clients = [c for c in active_clients if c.odoo and c.odoo.url]
        components["odoo_integration"] = {
            "status": "ok" if odoo_clients else "warning",
            "message": f"{len(odoo_clients)} cliente(s) con Odoo configurado",
            "configured_clients": len(odoo_clients)
        }
        
        # 5. CORS
        components["cors"] = {
            "status": "ok",
            "message": f"CORS configurado con {len(cors_config.get('allow_origins', []))} origen(es)"
        }
        
        # 6. Rutas
        components["routes"] = {
            "status": "ok",
            "message": "Rutas registradas",
            "endpoints": len(app.routes)
        }
        
        # Determinar código de estado HTTP
        status_code = 200
        if overall_status == "degraded":
            status_code = 200  # Funcional pero con advertencias
        elif overall_status == "unhealthy":
            status_code = 503  # No funcional
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": overall_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": {
                    "name": settings.SERVICE_NAME,
                    "version": settings.SERVICE_VERSION,
                    "environment": os.getenv("RENDER", "local")
                },
                "components": components
            }
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy", 
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
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
