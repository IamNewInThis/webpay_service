from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType 

app = FastAPI()

# 🔹 Configuración de prueba (sandbox)
commerce_code = IntegrationCommerceCodes.WEBPAY_PLUS
api_key = IntegrationApiKeys.WEBPAY
integration_type = IntegrationType.TEST

options = WebpayOptions(commerce_code, api_key, integration_type)

@app.get("/")
def index():
    return {"msg": "Servidor Webpay operativo 🚀"}

@app.post("/webpay/init")
async def webpay_init(request: Request):
    data = await request.json()
    amount = data.get("amount", 1000)
    buy_order = f"O-{abs(hash(amount)) % 1000000}"
    session_id = f"S-{abs(hash(buy_order)) % 1000000}"
    return_url = "http://localhost:8000/webpay/commit"

    tx = Transaction(options)
    response = tx.create(buy_order, session_id, amount, return_url)
    print("🔸 Transacción creada:", response)
    return response

@app.post("/webpay/commit")
async def webpay_commit(request: Request):
    form = await request.form()
    token = form.get("token_ws")

    tx = Transaction(options)
    result = tx.commit(token)
    print("✅ Resultado commit:", result)
    return JSONResponse(content=result)
