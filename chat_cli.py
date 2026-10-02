"""Testar o agente no terminal, sem WhatsApp.   python chat_cli.py [telefone]"""
import sys

import agent
from database import ensure_customer, init_db

if __name__ == "__main__":
    init_db()
    phone = sys.argv[1] if len(sys.argv) > 1 else "244900000000"
    ensure_customer(phone, "Cliente Teste")
    print(f"Chat de teste ({phone}). Escreve 'sair' para terminar.\n")
    while True:
        text = input("Tu: ").strip()
        if text.lower() in {"sair", "exit", "quit"}:
            break
        if text:
            print(f"\nBot: {agent.reply(phone, text, 'Cliente Teste')}\n")
