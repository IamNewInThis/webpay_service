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
    return {"msg": "Servidor Webpay operativo 🚀 1.0.3"}


@app.post("/webpay/init")
async def webpay_init(request: Request):
    data = await request.json()
    amount = data.get("amount", 1000)
    buy_order = f"O-{abs(hash(amount)) % 1000000}"
    session_id = f"S-{abs(hash(buy_order)) % 1000000}"
    return_url = "https://webpay-service.onrender.com/webpay/commit"

    tx = Transaction(options)
    response = tx.create(buy_order, session_id, amount, return_url)
    print("🔸 Transacción creada:", response)
    return response


@app.api_route("/webpay/commit", methods=["GET", "POST"])
async def webpay_commit(request: Request):
    """
    Maneja tanto éxito (POST con token_ws) como cancelación (GET con TBK_TOKEN)
    """
    params = dict(request.query_params)
    form = await request.form()
    token = form.get("token_ws") or params.get("token_ws")
    tbk_token = params.get("TBK_TOKEN")

    tx = Transaction(options)

    # 🚫 Caso 1: Anulación desde Webpay (no hay token_ws)
    if tbk_token or not token:
        print("❌ Transacción anulada o cancelada:", params)
        return RedirectResponse("https://tecnogrow-webpay.odoo.com/shop/payment?status=cancelled")

    try:
        result = tx.commit(token)
        print("✅ Resultado commit recibido:", result)

        # ✅ Caso 2: Pago exitoso
        if result.get("response_code") == 0:
            redirect_url = (
                f"https://tecnogrow-webpay.odoo.com/shop/confirmation"
                f"?status=success&order={result['buy_order']}"
            )
        else:
            # ❌ Caso 3: Pago rechazado por el banco
            redirect_url = "https://tecnogrow-webpay.odoo.com/shop/payment?status=rejected"

        print("➡️ Redirigiendo a:", redirect_url)
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        print("⚠️ Error al procesar commit:", e)
        return RedirectResponse("https://tecnogrow-webpay.odoo.com/shop/payment?status=error")
