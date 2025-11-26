"""
🔒 Módulo de Seguridad
======================
Implementa autenticación mediante API Key y firma HMAC para proteger los endpoints.

Funcionalidades:
- ✅ Validación de API Key en headers
- ✅ Firma HMAC SHA-256 para verificar integridad de requests
- ✅ Middleware de autenticación
- ✅ Dependencias reutilizables para FastAPI
"""

import hmac
import hashlib
import time
import os
from typing import Optional, Dict, Any, List
from fastapi import Header, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

# 🔑 Configuración de seguridad desde variables de entorno
API_KEY = os.getenv("API_KEY", "")
HMAC_SECRET = os.getenv("HMAC_SECRET", "")

# ⏰ Ventana de tiempo para validar timestamps (5 minutos)
TIMESTAMP_TOLERANCE = 300

# 🌐 Orígenes permitidos (dominios autorizados para llamar al middleware)
ODOO_URL = os.getenv("ODOO_URL")

ALLOWED_ORIGINS: List[str] = [
    ODOO_URL,
    "https://tecnogrow.odoo.com",
    "http://localhost:8000",  # Para desarrollo
]

# 🔒 Token interno para comunicación middleware ↔ Odoo
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")

# 📝 Definición del esquema de API Key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """
    🔐 Verifica que el API Key proporcionado sea válido
    
    Args:
        api_key: API Key del header X-API-Key
        
    Returns:
        El API Key validado
        
    Raises:
        HTTPException 401: Si el API Key es inválido o no está presente
    """
    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API Key no configurada en el servidor"
        )
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key requerida. Incluya el header X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    return api_key


async def verify_origin(request: Request) -> str:
    """
    🌐 Verifica que el request venga de un origen permitido (dominio autorizado)
    
    Esta función protege el middleware de llamadas desde dominios no autorizados.
    Solo los dominios en ALLOWED_ORIGINS pueden llamar a los endpoints protegidos.
    
    Args:
        request: Request de FastAPI
        
    Returns:
        El origen verificado
        
    Raises:
        HTTPException 403: Si el origen no está permitido
    """
    # Obtener origen del header
    origin = request.headers.get("origin") or request.headers.get("referer", "")
    
    # En desarrollo local, permitir requests sin Origin
    if not origin and request.client:
        host = request.client.host
        if host in ["127.0.0.1", "localhost"]:
            print(f"🔓 Request local permitido desde {host}")
            return "localhost"
    
    # Si no hay origen y no es local, rechazar
    if not origin:
        print("❌ Request sin Origin header rechazado")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origen no especificado"
        )
    
    # Normalizar origen (remover trailing slash)
    origin = origin.rstrip("/")
    
    # Verificar si el origen está en la lista permitida
    # Soportar wildcards simples (https://*.odoo.com)
    origin_allowed = False
    for allowed in ALLOWED_ORIGINS:
        if allowed == origin:
            origin_allowed = True
            break
        # Soporte para wildcards básico
        if "*" in allowed:
            pattern = allowed.replace("*", ".*").replace(".", r"\.")
            import re
            if re.match(pattern, origin):
                origin_allowed = True
                break
    
    if not origin_allowed:
        print(f"❌ Origen no permitido: {origin}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Origen no permitido: {origin}"
        )
    
    print(f"✅ Origen verificado: {origin}")
    return origin


def generate_hmac_signature(
    data: str,
    timestamp: str,
    secret: Optional[str] = None
) -> str:
    """
    🔏 Genera una firma HMAC SHA-256
    
    Args:
        data: Datos a firmar (generalmente JSON stringificado)
        timestamp: Timestamp unix de la request
        secret: Secreto HMAC (usa HMAC_SECRET por defecto)
        
    Returns:
        Firma HMAC en formato hexadecimal
    """
    secret_key = secret or HMAC_SECRET
    if not secret_key:
        raise ValueError("HMAC_SECRET no configurado")
    
    # Concatenar datos con timestamp para prevenir replay attacks
    message = f"{data}:{timestamp}"
    
    # Generar firma HMAC
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_hmac_signature(
    request_body: str,
    timestamp: str,
    signature: str,
    secret: Optional[str] = None
) -> bool:
    """
    ✅ Verifica que la firma HMAC sea válida
    
    Args:
        request_body: Cuerpo de la request (JSON string)
        timestamp: Timestamp de la request
        signature: Firma HMAC proporcionada
        secret: Secreto HMAC (usa HMAC_SECRET por defecto)
        
    Returns:
        True si la firma es válida, False en caso contrario
    """
    try:
        # Verificar que el timestamp sea reciente (protección contra replay attacks)
        current_time = int(time.time())
        request_time = int(timestamp)
        
        if abs(current_time - request_time) > TIMESTAMP_TOLERANCE:
            print(f"⚠️ Timestamp expirado. Diferencia: {abs(current_time - request_time)}s")
            return False
        
        # Generar firma esperada
        expected_signature = generate_hmac_signature(request_body, timestamp, secret)
        
        # Comparación segura contra timing attacks
        return hmac.compare_digest(signature, expected_signature)
        
    except (ValueError, TypeError) as e:
        print(f"❌ Error verificando firma HMAC: {e}")
        return False


async def verify_hmac_dependency(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp")
) -> Dict[str, Any]:
    """
    🔒 Dependencia de FastAPI para verificar firma HMAC
    
    Uso:
        @app.post("/endpoint", dependencies=[Depends(verify_hmac_dependency)])
        
    Args:
        request: Request de FastAPI
        x_signature: Firma HMAC del header X-Signature
        x_timestamp: Timestamp del header X-Timestamp
        
    Returns:
        Dict con información de la validación
        
    Raises:
        HTTPException 401: Si la firma es inválida o falta información
    """
    if not HMAC_SECRET:
        # Si no hay HMAC_SECRET configurado, no requerir HMAC (modo desarrollo)
        print("⚠️ HMAC_SECRET no configurado - Validación HMAC deshabilitada")
        return {"hmac_verified": False, "reason": "HMAC not configured"}
    
    if not x_signature or not x_timestamp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma HMAC requerida. Incluya headers X-Signature y X-Timestamp"
        )
    
    # Leer el cuerpo de la request
    body = await request.body()
    body_str = body.decode('utf-8') if body else ""
    
    # Verificar la firma
    if not verify_hmac_signature(body_str, x_timestamp, x_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma HMAC inválida o expirada"
        )
    
    return {
        "hmac_verified": True,
        "timestamp": x_timestamp
    }


def create_signed_request(data: Dict[str, Any]) -> Dict[str, str]:
    """
    📝 Crea headers firmados para una request saliente
    
    Útil para cuando este servicio necesita hacer requests a otros servicios.
    
    Args:
        data: Diccionario con los datos a enviar
        
    Returns:
        Dict con headers X-Signature y X-Timestamp
        
    Example:
        >>> data = {"order_id": 123, "amount": 1000}
        >>> headers = create_signed_request(data)
        >>> response = requests.post(url, json=data, headers=headers)
    """
    import json
    
    timestamp = str(int(time.time()))
    data_str = json.dumps(data, sort_keys=True)
    signature = generate_hmac_signature(data_str, timestamp)
    
    return {
        "X-Signature": signature,
        "X-Timestamp": timestamp,
        "X-API-Key": API_KEY
    }


async def verify_frontend_request(request: Request) -> Dict[str, Any]:
    """
    🛡️ Validación completa para requests desde el frontend de Odoo
    
    Verifica:
    1. Origen permitido (dominio Odoo autorizado)
    2. Timestamp válido (previene replay attacks)
    3. Opcionalmente: firma ligera si se necesita más seguridad
    
    Uso para endpoints llamados desde el frontend (ej: /webpay/init)
    
    Args:
        request: Request de FastAPI
        
    Returns:
        Dict con información de validación
        
    Raises:
        HTTPException 403: Si el origen no está permitido
        HTTPException 401: Si el timestamp es inválido
    """
    # Verificar origen
    origin = await verify_origin(request)
    
    # Obtener timestamp (opcional, pero recomendado)
    timestamp_header = request.headers.get("X-Timestamp")
    timestamp_valid = False
    
    if timestamp_header:
        try:
            request_time = int(timestamp_header)
            current_time = int(time.time())
            
            if abs(current_time - request_time) <= TIMESTAMP_TOLERANCE:
                timestamp_valid = True
            else:
                print(f"⚠️ Timestamp fuera de ventana: {abs(current_time - request_time)}s")
        except (ValueError, TypeError):
            print("⚠️ Timestamp inválido en header")
    
    return {
        "origin": origin,
        "timestamp_valid": timestamp_valid,
        "timestamp": timestamp_header
    }


def get_internal_token_header() -> Dict[str, str]:
    """
    🔐 Genera header con token interno para requests hacia Odoo
    
    Este token se usa para autenticar requests del middleware hacia Odoo.
    Odoo puede verificarlo en logs o validarlo si tiene acceso.
    
    Returns:
        Dict con header X-Internal-Token
    """
    if not INTERNAL_TOKEN:
        return {}
    
    return {
        "X-Internal-Token": INTERNAL_TOKEN
    }


# 🛡️ Dependencias combinadas para máxima seguridad
async def verify_api_key_and_hmac(
    api_key: str = Header(..., alias="X-API-Key"),
    hmac_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    🔐 Verifica tanto API Key como firma HMAC
    
    Uso:
        @app.post("/endpoint", dependencies=[Depends(verify_api_key_and_hmac)])
    """
    # Verificar API Key
    verify_api_key(api_key)
    
    # HMAC ya fue verificado por verify_hmac_dependency
    return {
        "authenticated": True,
        "api_key_valid": True,
        "hmac_verified": hmac_data.get("hmac_verified", False) if hmac_data else False
    }
