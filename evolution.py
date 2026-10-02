"""Cliente da Evolution API (v2): receber webhooks, enviar mensagens e configurar o webhook."""
import hmac
import logging

import httpx

import config

logger = logging.getLogger(__name__)
MAX_LEN = 3500  # limite do WhatsApp: 4096 caracteres

# Tipos de mensagem a que vale a pena responder "só leio texto"
_MEDIA_TYPES = {"imageMessage", "audioMessage", "videoMessage", "documentMessage", "locationMessage", "contactMessage"}


def _headers() -> dict:
    return {"apikey": config.EVOLUTION_API_KEY, "Content-Type": "application/json"}


def _url(path: str) -> str:
    return f"{config.EVOLUTION_API_URL.rstrip('/')}{path}"


# ------------------------------ Receber ------------------------------
def verify_secret(header_value: str | None, query_value: str | None) -> bool:
    """A Evolution não assina os webhooks; usamos um segredo partilhado (header ou ?secret=)."""
    if not config.WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET não definido: o webhook aceita qualquer pedido!")
        return True
    candidate = (header_value or query_value or "").encode()
    return hmac.compare_digest(candidate, config.WEBHOOK_SECRET.encode())


def parse_incoming(payload: dict) -> dict | None:
    """Extrai a mensagem de um evento messages.upsert. Devolve None se for para ignorar."""
    event = str(payload.get("event", "")).lower().replace("_", ".")
    if event != "messages.upsert":
        return None
    if payload.get("instance") and payload["instance"] != config.EVOLUTION_INSTANCE:
        return None

    data = payload.get("data") or {}
    if isinstance(data, list):
        data = data[0] if data else {}

    key = data.get("key") or {}
    if key.get("fromMe"):
        return None

    jid = key.get("remoteJid") or ""
    if not jid or jid.endswith("@g.us") or jid.startswith("status@") or "@broadcast" in jid:
        return None  # ignora grupos, status e listas de difusão

    # Versões recentes podem usar @lid; nesse caso o número real vem em remoteJidAlt
    target = key.get("remoteJidAlt") or jid
    if target.endswith("@s.whatsapp.net"):
        target = target.split("@")[0]  # só os dígitos

    message = data.get("message") or {}
    text = message.get("conversation") or (message.get("extendedTextMessage") or {}).get("text")

    return {
        "id": key.get("id", ""),
        "phone": target.split("@")[0],
        "target": target,
        "name": data.get("pushName"),
        "text": text.strip() if text else None,
        "is_media": data.get("messageType") in _MEDIA_TYPES,
    }


# ------------------------------ Enviar ------------------------------
def _split(text: str) -> list[str]:
    chunks, current = [], ""
    for paragraph in text.split("\n\n"):
        if current and len(current) + len(paragraph) + 2 > MAX_LEN:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return [c[:MAX_LEN] for c in chunks]


def send_text(target: str, body: str) -> None:
    url = _url(f"/message/sendText/{config.EVOLUTION_INSTANCE}")
    for chunk in _split(body):
        payload = {"number": target, "text": chunk, "delay": config.SEND_DELAY_MS}
        try:
            r = httpx.post(url, json=payload, headers=_headers(), timeout=30)
            if r.status_code >= 400:
                logger.error("Evolution API recusou o envio (%s): %s", r.status_code, r.text)
        except httpx.HTTPError:
            logger.exception("Falha de rede ao falar com a Evolution API")


# ------------------------------ Configurar ------------------------------
def set_webhook(webhook_url: str) -> httpx.Response:
    """Regista o nosso webhook na instância (evento MESSAGES_UPSERT)."""
    webhook = {
        "enabled": True,
        "url": webhook_url,
        "byEvents": False,
        "base64": False,
        "events": ["MESSAGES_UPSERT"],
    }
    if config.WEBHOOK_SECRET:
        webhook["headers"] = {"X-Webhook-Secret": config.WEBHOOK_SECRET}
    return httpx.post(
        _url(f"/webhook/set/{config.EVOLUTION_INSTANCE}"),
        json={"webhook": webhook},
        headers=_headers(),
        timeout=30,
    )
