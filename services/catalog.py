"""Catálogo: pesquisa e detalhes de livros."""
import unicodedata

from database import get_conn
from utils import ServiceError, fmt_money


def _norm(text: str) -> str:
    """Minúsculas e sem acentos, para pesquisar 'atomicos' e achar 'Atómicos'."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def book_to_dict(row) -> dict:
    return {
        "book_id": row["id"],
        "title": row["title"],
        "author": row["author"],
        "category": row["category"],
        "description": row["description"],
        "price": row["price"],
        "price_formatted": fmt_money(row["price"]),
        "copies_for_sale": row["stock_sale"],
        "copies_for_loan": row["stock_loan"],
    }


def search_books(query: str, limit: int = 5) -> list[dict]:
    terms = [t for t in _norm(query).split() if len(t) > 2] or _norm(query).split()
    if not terms:
        return []

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM books").fetchall()

    scored = []
    for row in rows:
        haystack = _norm(f"{row['title']} {row['author']} {row['category'] or ''} {row['description'] or ''}")
        score = sum(1 for t in terms if t in haystack)
        if score:
            scored.append((score, row))

    scored.sort(key=lambda s: (-s[0], s[1]["title"]))
    return [book_to_dict(row) for _, row in scored[:limit]]


def get_book(book_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not row:
        raise ServiceError("Livro não encontrado.")
    return book_to_dict(row)
