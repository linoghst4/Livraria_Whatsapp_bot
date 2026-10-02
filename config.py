"""Configuração central (lida do .env)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


# --- IA ---
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash")

# --- WhatsApp via Evolution API ---
EVOLUTION_API_URL = _env("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = _env("EVOLUTION_API_KEY")        # chave da instância (ou global)
EVOLUTION_INSTANCE = _env("EVOLUTION_INSTANCE", "livraria")
WEBHOOK_SECRET = _env("WEBHOOK_SECRET")              # segredo enviado pela Evolution no webhook
SEND_DELAY_MS = int(_env("SEND_DELAY_MS", "1200"))   # mostra "a escrever..." antes de enviar

# --- Loja ---
STORE_NAME = _env("STORE_NAME", "Livraria Exemplo")
STORE_HOURS = _env("STORE_HOURS", "Seg-Sex 9h-18h, Sáb 9h-13h")
STORE_ADDRESS = _env("STORE_ADDRESS", "Rua Exemplo, 123")
STORE_CONTACT = _env("STORE_CONTACT", "")
PAYMENT_INSTRUCTIONS = _env(
    "PAYMENT_INSTRUCTIONS",
    "Pague na loja ou por transferência bancária e envie o comprovativo; a equipa confirma e avisa.",
)
CURRENCY = _env("CURRENCY", "Kz")
TIMEZONE = _env("TIMEZONE", "Africa/Luanda")

# --- Regras de empréstimo e multa ---
LOAN_DAYS = int(_env("LOAN_DAYS", "14"))
MAX_ACTIVE_LOANS = int(_env("MAX_ACTIVE_LOANS", "3"))
MAX_RENEWALS = int(_env("MAX_RENEWALS", "1"))
LATE_FEE_PER_DAY = float(_env("LATE_FEE_PER_DAY", "100"))
LATE_FEE_CAP_PERCENT = float(_env("LATE_FEE_CAP_PERCENT", "100"))  # multa máx. = % do preço

# --- Base de dados ---
DB_PATH = _env("DB_PATH", "livraria.db")
