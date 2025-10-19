from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType 

app = FastAPI()

# 🔹 Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tecnogrow-webpay.odoo.com",  # Tu dominio de Odoo específico
        "https://*.odoo.com",  # Cualquier subdominio de odoo.com
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 🔹 Configuración de prueba (sandbox)
commerce_code = IntegrationCommerceCodes.WEBPAY_PLUS
api_key = IntegrationApiKeys.WEBPAY
integration_type = IntegrationType.TEST

options = WebpayOptions(commerce_code, api_key, integration_type)

@app.get("/")
def index():
    return {"msg": "Servidor Webpay operativo 🚀 1.0.0"}

@app.post("/webpay/init")
async def webpay_init(request: Request):
    data = await request.json()
    amount = data.get("amount", 1000)
    buy_order = f"O-{abs(hash(amount)) % 1000000}"
    session_id = f"S-{abs(hash(buy_order)) % 1000000}"
    # 🔹 URL de retorno debe apuntar a tu servidor público, no localhost
    # return_url = "https://webpay-service.onrender.com/webpay/commit"
    return_url = "https://tecnogrow-webpay.odoo.com/shop/confirmation"

    tx = Transaction(options)
    response = tx.create(buy_order, session_id, amount, return_url)
    print("🔸 Transacción creada:", response)
    return response

@app.post("/webpay/commit")
async def webpay_commit(request: Request):
    try:
        form = await request.form()
        token = form.get("token_ws")
        
        # Si no hay token, significa que el usuario canceló
        if not token:
            print("❌ Usuario canceló la transacción - Sin token")
            return RedirectResponse(url="https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled")
        
        tx = Transaction(options)
        result = tx.commit(token)
        print("✅ Resultado commit:", result)
        
        # Verificar el estado de la transacción
        if result.get("status") == "AUTHORIZED":
            print("✅ Transacción autorizada exitosamente")
            return RedirectResponse(url=f"https://tecnogrow-webpay.odoo.com/shop/confirmation?status=success&order={result['buy_order']}")
        else:
            print(f"❌ Transacción rechazada. Estado: {result.get('status')}")
            return RedirectResponse(url="https://tecnogrow-webpay.odoo.com/shop/payment?status=failed")
            
    except Exception as e:
        print(f"❌ Error en commit: {str(e)}")
        return RedirectResponse(url="https://tecnogrow-webpay.odoo.com/shop/payment?status=error")

@app.get("/webpay/cancel")
async def webpay_cancel():
    """Endpoint para manejar cancelaciones del usuario"""
    print("❌ Usuario canceló la transacción desde Webpay")
    return RedirectResponse(url="https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled")

@app.post("/webpay/cancel")
async def webpay_cancel_post():
    """Endpoint POST para manejar cancelaciones del usuario"""
    print("❌ Usuario canceló la transacción desde Webpay (POST)")
    return RedirectResponse(url="https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled")

