"""Empréstimos: prazo de devolução, renovação e multa por atraso."""
from datetime import date, timedelta

import config
from database import get_conn
from utils import ServiceError, fmt_date, fmt_money, now, parse_date, today


def calc_late_fee(due: date, price: float, until: date | None = None) -> tuple[int, int]:
    """Devolve (dias_de_atraso, multa). Multa = dias x taxa diária, limitada a % do preço."""
    end = until or today()
    days_late = max(0, (end - due).days)
    cap = price * config.LATE_FEE_CAP_PERCENT / 100
    fee = min(days_late * config.LATE_FEE_PER_DAY, cap)
    return days_late, round(fee)


def get_policies() -> dict:
    return {
        "loan_days": config.LOAN_DAYS,
        "max_active_loans": config.MAX_ACTIVE_LOANS,
        "max_renewals": config.MAX_RENEWALS,
        "late_fee_per_day": fmt_money(config.LATE_FEE_PER_DAY),
        "late_fee_cap": f"{config.LATE_FEE_CAP_PERCENT:.0f}% do preço do livro",
        "returns": "A devolução é feita na loja; a equipa regista-a no sistema.",
        "blocking_rule": "Com empréstimo em atraso ou multa por pagar não é possível pedir novos empréstimos.",
    }


def _active_query() -> str:
    return (
        "SELECT l.*, b.title, b.author, b.price FROM loans l "
        "JOIN books b ON b.id = l.book_id "
    )


def _loan_view(row) -> dict:
    due = parse_date(row["due_date"])
    days_late, fee = calc_late_fee(due, row["price"])
    return {
        "loan_id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "loaned_at": fmt_date(parse_date(row["loaned_at"])),
        "due_date": fmt_date(due),
        "days_left": max((due - today()).days, 0),
        "overdue": days_late > 0,
        "days_late": days_late,
        "current_late_fee": fee,
        "current_late_fee_formatted": fmt_money(fee),
        "renewals_used": row["renewals"],
        "can_renew": days_late == 0 and row["renewals"] < config.MAX_RENEWALS,
    }


def _unpaid_fees(conn, phone: str) -> list:
    return conn.execute(
        _active_query() + "WHERE l.phone = ? AND l.returned_at IS NOT NULL "
        "AND l.fee_amount > 0 AND l.fee_paid = 0",
        (phone,),
    ).fetchall()


def borrow_book(phone: str, book_id: int) -> dict:
    with get_conn() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            raise ServiceError("Livro não encontrado.")

        active = conn.execute(
            _active_query() + "WHERE l.phone = ? AND l.returned_at IS NULL", (phone,)
        ).fetchall()

        if len(active) >= config.MAX_ACTIVE_LOANS:
            raise ServiceError(f"Limite de {config.MAX_ACTIVE_LOANS} empréstimos em simultâneo atingido.")
        for loan in active:
            if loan["book_id"] == book_id:
                raise ServiceError("Já tem este livro emprestado.")
            if parse_date(loan["due_date"]) < today():
                raise ServiceError("Tem um empréstimo em atraso. Devolva-o antes de pedir outro.")
        if _unpaid_fees(conn, phone):
            raise ServiceError("Tem multas por pagar. Regularize-as na loja antes de pedir outro empréstimo.")

        cur = conn.execute(
            "UPDATE books SET stock_loan = stock_loan - 1 WHERE id = ? AND stock_loan > 0", (book_id,)
        )
        if cur.rowcount == 0:
            raise ServiceError("Não há exemplares disponíveis para empréstimo neste momento.")

        start = today()
        due = start + timedelta(days=config.LOAN_DAYS)
        cur = conn.execute(
            "INSERT INTO loans (phone, book_id, loaned_at, due_date) VALUES (?, ?, ?, ?)",
            (phone, book_id, start.isoformat(), due.isoformat()),
        )

    return {
        "loan_id": cur.lastrowid,
        "title": book["title"],
        "loaned_at": fmt_date(start),
        "due_date": fmt_date(due),
        "loan_days": config.LOAN_DAYS,
        "late_fee_per_day": fmt_money(config.LATE_FEE_PER_DAY),
    }


def list_loans(phone: str) -> dict:
    with get_conn() as conn:
        active = conn.execute(
            _active_query() + "WHERE l.phone = ? AND l.returned_at IS NULL ORDER BY l.due_date",
            (phone,),
        ).fetchall()
        unpaid = _unpaid_fees(conn, phone)

    active_views = [_loan_view(r) for r in active]
    unpaid_views = [
        {"loan_id": r["id"], "title": r["title"], "fee": fmt_money(r["fee_amount"])} for r in unpaid
    ]
    total = sum(v["current_late_fee"] for v in active_views) + sum(r["fee_amount"] for r in unpaid)
    return {
        "active_loans": active_views,
        "unpaid_fees_from_returned_books": unpaid_views,
        "total_fees_due": fmt_money(total),
    }


def renew_loan(phone: str, loan_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            _active_query() + "WHERE l.id = ? AND l.phone = ? AND l.returned_at IS NULL",
            (loan_id, phone),
        ).fetchone()
        if not row:
            raise ServiceError("Empréstimo ativo não encontrado.")
        view = _loan_view(row)
        if view["overdue"]:
            raise ServiceError("Não é possível renovar um empréstimo em atraso.")
        if row["renewals"] >= config.MAX_RENEWALS:
            raise ServiceError("Já utilizou o número máximo de renovações para este livro.")

        new_due = parse_date(row["due_date"]) + timedelta(days=config.LOAN_DAYS)
        conn.execute(
            "UPDATE loans SET due_date = ?, renewals = renewals + 1 WHERE id = ?",
            (new_due.isoformat(), loan_id),
        )
    return {"loan_id": loan_id, "title": row["title"], "new_due_date": fmt_date(new_due)}


# ----------------------- Funções internas (admin / loja) -----------------------
def register_return(loan_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            _active_query() + "WHERE l.id = ? AND l.returned_at IS NULL", (loan_id,)
        ).fetchone()
        if not row:
            raise ServiceError("Empréstimo ativo não encontrado.")

        days_late, fee = calc_late_fee(parse_date(row["due_date"]), row["price"])
        conn.execute(
            "UPDATE loans SET returned_at = ?, fee_amount = ? WHERE id = ?",
            (today().isoformat(), fee, loan_id),
        )
        conn.execute("UPDATE books SET stock_loan = stock_loan + 1 WHERE id = ?", (row["book_id"],))
    return {"title": row["title"], "phone": row["phone"], "days_late": days_late, "fee": fee}


def mark_fee_paid(loan_id: int) -> None:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE loans SET fee_paid = 1 WHERE id = ? AND returned_at IS NOT NULL AND fee_amount > 0",
            (loan_id,),
        )
        if cur.rowcount == 0:
            raise ServiceError("Empréstimo sem multa pendente.")
