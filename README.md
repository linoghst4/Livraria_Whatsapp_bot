# Agente de IA para Livraria (WhatsApp)

Atende clientes pelo WhatsApp: pesquisa e compra de livros, empréstimos com data de devolução,
multa por atraso e perguntas gerais. Usa Gemini com chamada de funções e SQLite.

## Estrutura

```
livraria_agent/
├── main.py            # Servidor FastAPI + webhook que recebe da Evolution API
├── evolution.py       # Cliente da Evolution API (ler webhook, enviar texto, registar webhook)
├── setup_evolution.py # Regista o webhook na instância
├── docker-compose.yml # Evolution API + PostgreSQL + Redis
├── agent.py           # Agente Gemini (prompt, memória da conversa por cliente)
├── tools.py           # Ferramentas que o agente pode chamar (ligadas ao telefone do cliente)
├── services/
│   ├── catalog.py     # Pesquisa de livros
│   ├── orders.py      # Compras / encomendas
│   └── loans.py       # Empréstimos, renovação e cálculo de multa
├── database.py        # SQLite: tabelas e ligação
├── seed_data.py       # Livros de exemplo (substitui pelos reais)
├── config.py          # Configuração (.env)
├── utils.py           # Datas, dinheiro, erros
├── admin.py           # Comandos para a equipa (devoluções, pagamentos, novos livros)
└── chat_cli.py        # Testar no terminal, sem WhatsApp
```

## Instalação (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy env.example .env      # preenche o GEMINI_API_KEY e os dados da loja
```

## 1. Testar sem WhatsApp

```powershell
python chat_cli.py
```

## 2. Ligar ao WhatsApp (Evolution API)

A Evolution API é um servidor próprio (Docker) que liga ao WhatsApp lendo um QR code, tal como o WhatsApp Web.

1. Preenche o `.env` (`EVOLUTION_API_KEY`, `POSTGRES_PASSWORD`, `WEBHOOK_SECRET`) e sobe a Evolution:
   ```powershell
   docker compose up -d
   ```
   A Evolution v2 precisa de PostgreSQL (o compose já o inclui). Sem `DATABASE_PROVIDER` o contentor
   falha com "Database provider invalid".
2. Abre http://localhost:8081/manager, entra com a `EVOLUTION_API_KEY`, cria uma instância
   (ex.: `livraria`, canal Baileys) e lê o QR code com o telemóvel da loja
   (WhatsApp > Dispositivos ligados).
3. Confirma no `.env`: `EVOLUTION_API_URL=http://localhost:8081` e `EVOLUTION_INSTANCE=livraria`.
4. Arranca o bot:
   ```powershell
   uvicorn main:app --port 8000
   ```
5. Regista o webhook (o URL depende de onde corre a Evolution):
   ```powershell
   # Evolution em Docker no mesmo PC:
   python setup_evolution.py http://host.docker.internal:8000/webhook
   # Tudo fora do Docker:
   python setup_evolution.py http://localhost:8000/webhook
   ```
   Se a Evolution estiver noutro servidor, usa o URL público do bot.
   Podes também configurar o webhook à mão no Evolution Manager: evento `MESSAGES_UPSERT`
   e o header `X-Webhook-Secret` com o mesmo valor do `WEBHOOK_SECRET`.
6. Envia uma mensagem de outro número para o WhatsApp da loja.

Não precisas de conta Meta nem de tunnel se tudo correr na mesma máquina.

Aviso: a Evolution (modo Baileys) não é oficial. O WhatsApp pode restringir ou banir o número
se detetar comportamento de spam. Usa um número dedicado à loja, responde só a quem te escreve primeiro
e evita envios em massa.

## Regras (editáveis no .env)

| Regra | Padrão |
|---|---|
| Prazo de empréstimo | 14 dias |
| Máx. empréstimos ativos | 3 |
| Renovações por livro | 1 (não se estiver em atraso) |
| Multa por dia de atraso | 100 Kz |
| Teto da multa | 100% do preço do livro |
| Bloqueio | Sem novos empréstimos com atraso ou multa por pagar |

## Operação diária (equipa)

```powershell
python admin.py loans             # empréstimos ativos e atrasos
python admin.py return 3          # regista devolução (calcula multa)
python admin.py orders            # encomendas a aguardar pagamento
python admin.py pay-order 5       # confirma pagamento
python admin.py pay-fee 3         # multa paga
python admin.py add-book "Título" "Autor" 7500 --sale 5 --loan 2
```

## Segurança

- O telefone do cliente é fixado no código das ferramentas: o modelo não consegue ver dados de outros clientes.
- Devoluções, pagamentos e perdão de multas só pela equipa (`admin.py`), nunca pelo chat.
- As ferramentas de compra e empréstimo só são chamadas após confirmação do cliente (instrução do prompt).
- O webhook só aceita pedidos com o `WEBHOOK_SECRET` (header `X-Webhook-Secret` ou `?secret=`). Define-o sempre.
- Ignora grupos, status e mensagens enviadas por ti (`fromMe`), para o bot não responder a si próprio.
- O `.env` está no `.gitignore`. Nunca o publiques.
