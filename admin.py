"""Ferramentas da equipa da loja (linha de comandos).

Exemplos:
  python admin.py loans                 # empréstimos ativos
  python admin.py orders                # encomendas a aguardar pagamento
  python admin.py return 3              # registar devolução do empréstimo 3 (calcula multa)
  python admin.py pay-order 5           # confirmar pagamento da encomenda 5
  python admin.py pay-fee 3             # marcar multa do empréstimo 3 como paga
  python admin.py add-book "Título" "Autor" 7500 --sale 5 --loan 2 --category Romance
"""
import argparse

from database import get_conn, init_db
from services import loans, orders
from utils import ServiceError, fmt_money, parse_date


def cmd_loans(_):
    with get_conn() as c:
        rows = c.execute(
            "SELECT l.*, b.title, b.price FROM loans l JOIN books b ON b.id = l.book_id "
            "WHERE l.returned_at IS NULL ORDER BY l.due_date"
        ).fetchall()
    for r in rows:
        days_late, fee = loans.calc_late_fee(parse_date(r["due_date"]), r["price"])
        late = f" | ATRASO {days_late}d, multa {fmt_money(fee)}" if days_late else ""
        print(f"#{r['id']} {r['title']} | {r['phone']} | devolver até {r['due_date']}{late}")
    if not rows:
        print("Sem empréstimos ativos.")


def cmd_orders(_):
    with get_conn() as c:
        rows = c.execute(
            "SELECT o.*, b.title FROM orders o JOIN books b ON b.id = o.book_id "
            "WHERE o.status = 'pending_payment' ORDER BY o.id"
        ).fetchall()
    for r in rows:
        print(f"#{r['id']} {r['title']} x{r['quantity']} | {fmt_money(r['total'])} | {r['phone']}")
    if not rows:
        print("Sem encomendas pendentes.")


def cmd_return(a):
    r = loans.register_return(a.id)
    msg = f"Devolvido: {r['title']}."
    if r["fee"]:
        msg += f" Atraso de {r['days_late']} dias, multa a cobrar: {fmt_money(r['fee'])} (cliente {r['phone']})."
    print(msg)


def cmd_pay_order(a):
    orders.mark_paid(a.id)
    print("Pagamento confirmado.")


def cmd_pay_fee(a):
    loans.mark_fee_paid(a.id)
    print("Multa marcada como paga.")


def cmd_add_book(a):
    with get_conn() as c:
        c.execute(
            "INSERT INTO books (title, author, category, description, price, stock_sale, stock_loan) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (a.title, a.author, a.category, a.description, a.price, a.sale, a.loan),
        )
    print("Livro adicionado.")


def main():
    init_db()
    p = argparse.ArgumentParser(description="Administração da livraria")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("loans").set_defaults(fn=cmd_loans)
    sub.add_parser("orders").set_defaults(fn=cmd_orders)
    for name, fn in (("return", cmd_return), ("pay-order", cmd_pay_order), ("pay-fee", cmd_pay_fee)):
        s = sub.add_parser(name)
        s.add_argument("id", type=int)
        s.set_defaults(fn=fn)

    s = sub.add_parser("add-book")
    s.add_argument("title")
    s.add_argument("author")
    s.add_argument("price", type=float)
    s.add_argument("--sale", type=int, default=0)
    s.add_argument("--loan", type=int, default=0)
    s.add_argument("--category", default=None)
    s.add_argument("--description", default=None)
    s.set_defaults(fn=cmd_add_book)

    args = p.parse_args()
    try:
        args.fn(args)
    except ServiceError as e:
        print(f"Erro: {e}")


if __name__ == "__main__":
    main()
