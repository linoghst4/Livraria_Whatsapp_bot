"""Servidor FastAPI que recebe os webhooks da Evolution API.

Executar:  uvicorn main:app --port 8000
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

import agent
import config
import evolution
from database import ensure_customer, init_db

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_seen_ids: dict[str, None] = {}  # evita processar a mesma mensagem duas vezes
UNSUPPORTED = "De momento só consigo ler mensagens de texto. Pode escrever o que precisa? 🙂"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Base de dados pronta. Loja: %s | instância: %s", config.STORE_NAME, config.EVOLUTION_INSTANCE)
    yield


app = FastAPI(title="Agente da Livraria", lifespan=lifespan)


@app.get("/")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def receive_webhook(request: Request, background: BackgroundTasks):
    if not evolution.verify_secret(request.headers.get("X-Webhook-Secret"), request.query_params.get("secret")):
        raise HTTPException(status_code=403, detail="Segredo inválido")

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    background.add_task(handle_payload, payload)  # responde 200 já; processa em segundo plano
    return {"status": "ok"}


# A Evolution também aceita "byEvents": true, que acrescenta o nome do evento ao URL
@app.post("/webhook/{event_name}")
async def receive_webhook_by_event(event_name: str, request: Request, background: BackgroundTasks):
    return await receive_webhook(request, background)


async def handle_payload(payload: dict) -> None:
    incoming = evolution.parse_incoming(payload)
    if not incoming:
        return

    msg_id = incoming["id"]
    if msg_id in _seen_ids:
        return
    _seen_ids[msg_id] = None
    if len(_seen_ids) > 1000:
        _seen_ids.pop(next(iter(_seen_ids)))

    target, phone, name, text = incoming["target"], incoming["phone"], incoming["name"], incoming["text"]

    if not text:
        if incoming["is_media"]:
            await asyncio.to_thread(evolution.send_text, target, UNSUPPORTED)
        return

    logger.info("Mensagem de %s: %s", phone, text[:80])
    await asyncio.to_thread(ensure_customer, phone, name)
    answer = await asyncio.to_thread(agent.reply, phone, text, name)
    await asyncio.to_thread(evolution.send_text, target, answer)
