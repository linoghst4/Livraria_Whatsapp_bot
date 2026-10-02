"""Compras: criar, consultar e cancelar encomendas."""
import config
from database import get_conn
from utils import ServiceError, fmt_money, now

MAX_QTY = 10


def create_order(phone: str, book_id: int, quantity: int = 1) -> dict:
    if not 1 <= quantity <= MAX_QTY:
        raise ServiceError(f"Quantidade inválida (de 1 a {MAX_QTY}).")

    with get_conn() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            raise ServiceError("Livro não encontrado.")

        # Reserva o stock de forma atómica (evita vender a mesma cópia duas vezes)
        cur = conn.execute(
            "UPDATE books SET stock_sale = stock_sale - ? WHERE id = ? AND stock_sale >= ?",
            (quantity, book_id, quantity),
        )
        if cur.rowcount == 0:
            raise ServiceError(f"Stock insuficiente. Exemplares à venda: {book['stock_sale']}.")

        total = book["price"] * quantity
        cur = conn.execute(
            "INSERT INTO orders (phone, book_id, quantity, total, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending_payment', ?)",
            (phone, book_id, quantity, total, now().isoformat()),
        )
        order_id = cur.lastrowid

    return {
        "order_id": order_id,
        "title": book["title"],
        "quantity": quantity,
        "total": total,
        "total_formatted": fmt_money(total),
        "status": "pending_payment",
        "payment_instructions": config.PAYMENT_INSTRUCTIONS,
    }


def list_orders(phone: str, limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT o.*, b.title FROM orders o JOIN books b ON b.id = o.book_id "
            "WHERE o.phone = ? ORDER BY o.id DESC LIMIT ?",
            (phone, limit),
        ).fetchall()
    labels = {"pending_payment": "a aguardar pagamento", "paid": "pago", "cancelled": "cancelado"}
    return [
        {
            "order_id": r["id"],
            "title": r["title"],
            "quantity": r["quantity"],
            "total_formatted": fmt_money(r["total"]),
            "status": labels.get(r["status"], r["status"]),
        }
        for r in rows
    ]


def cancel_order(phone: str, order_id: int) -> dict:
    with get_conn() as conn:
        order = conn.execute(
            "SELECT * FROM orders WHERE id = ? AND phone = ?", (order_id, phone)
        ).fetchone()
        if not order:
            raise ServiceError("Encomenda não encontrada.")
        if order["status"] != "pending_payment":
            raise ServiceError("Só é possível cancelar encomendas que ainda aguardam pagamento.")

        conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        conn.execute(
            "UPDATE books SET stock_sale = stock_sale + ? WHERE id = ?",
            (order["quantity"], order["book_id"]),
        )
    return {"order_id": order_id, "status": "cancelado"}


def mark_paid(order_id: int) -> None:
    """Uso interno (admin): confirma o pagamento."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE orders SET status = 'paid' WHERE id = ? AND status = 'pending_payment'", (order_id,)
        )
        if cur.rowcount == 0:
            raise ServiceError("Encomenda não encontrada ou já processada.")
