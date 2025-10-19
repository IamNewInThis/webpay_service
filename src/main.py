from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tecnogrow-webpay.odoo.com",
        "https://*.odoo.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔧 Configuración Webpay
commerce_code = IntegrationCommerceCodes.WEBPAY_PLUS
api_key = IntegrationApiKeys.WEBPAY
integration_type = IntegrationType.TEST
options = WebpayOptions(commerce_code, api_key, integration_type)


@app.get("/")
def index():
    return {"msg": "Servidor Webpay operativo 🚀 1.0.5"}


@app.post("/webpay/init")
async def webpay_init(request: Request):
    data = await request.json()
    amount = data.get("amount", 1000)
    buy_order = f"O-{abs(hash(amount)) % 1000000}"
    session_id = f"S-{abs(hash(buy_order)) % 1000000}"

    # 🔹 Importante: retorno SIEMPRE a tu backend
    return_url = "https://webpay-service.onrender.com/webpay/commit"

    tx = Transaction(options)
    response = tx.create(buy_order, session_id, amount, return_url)
    print("🔸 Transacción creada:", response)
    return response


@app.post("/webpay/commit")
async def webpay_commit(request: Request):
    """Caso normal: retorno con token_ws (pago exitoso o rechazado)."""
    form = await request.form()
    token = form.get("token_ws")
    tx = Transaction(options)

    if not token:
        print("⚠️ No se recibió token_ws (probablemente anulación o expiración)")
        return RedirectResponse("https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled")

    try:
        result = tx.commit(token)
        print("✅ Resultado commit:", result)
        print("🔍 Status de la transacción:", result.get("status"))
        print("🔍 Response code:", result.get("response_code"))

        # Verificar AMBOS campos por si acaso
        status = result.get("status")
        response_code = result.get("response_code")
        
        if status == "AUTHORIZED" or response_code == 0:
            # Éxito - Pago autorizado
            redirect_url = (
                f"https://tecnogrow-webpay.odoo.com/shop/confirmation"
                f"?status=success&order={result['buy_order']}"
            )
            print("✅ Redirigiendo a confirmación exitosa:", redirect_url)
        else:
            # Rechazado o fallido
            redirect_url = "https://tecnogrow-webpay.odoo.com/shop/payment?status=rejected"
            print("❌ Pago rechazado, redirigiendo a payment:", redirect_url)

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        print("❌ Error en commit:", e)
        return RedirectResponse("https://tecnogrow-webpay.odoo.com/shop/payment?status=error")


@app.get("/webpay/commit")
async def webpay_commit_get(request: Request):
    """Maneja tanto cancelaciones como pagos exitosos que llegan via GET."""
    params = dict(request.query_params)
    print("📥 GET /webpay/commit recibido con params:", params)
    
    # Verificar si hay token_ws en los parámetros
    token = params.get("token_ws")
    
    if not token:
        # Si hay TBK_TOKEN pero no token_ws, es una cancelación
        if "TBK_TOKEN" in params:
            print("❌ Transacción anulada por el usuario (TBK_TOKEN presente)")
            return RedirectResponse("https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled")
        else:
            print("⚠️ GET sin token válido")
            return RedirectResponse("https://tecnogrow-webpay.odoo.com/shop/payment?status=error")
    
    # Si hay token_ws, intentar procesar la transacción
    try:
        tx = Transaction(options)
        result = tx.commit(token)
        print("✅ Resultado commit (GET):", result)
        print("🔍 Status de la transacción:", result.get("status"))
        print("🔍 Response code:", result.get("response_code"))

        # Verificar AMBOS campos por si acaso
        status = result.get("status")
        response_code = result.get("response_code")
        
        if status == "AUTHORIZED" or response_code == 0:
            # Éxito - Pago autorizado
            redirect_url = (
                f"https://tecnogrow-webpay.odoo.com/shop/confirmation"
                f"?status=success&order={result['buy_order']}"
            )
            print("✅ Redirigiendo a confirmación exitosa (GET):", redirect_url)
        else:
            # Rechazado o fallido
            redirect_url = "https://tecnogrow-webpay.odoo.com/shop/payment?status=rejected"
            print("❌ Pago rechazado, redirigiendo a payment (GET):", redirect_url)

        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        print("❌ Error en commit (GET):", e)
        return RedirectResponse("https://tecnogrow-webpay.odoo.com/shop/payment?status=error")
