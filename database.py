"""Ligação SQLite, criação das tabelas e dados iniciais."""
import sqlite3
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    category TEXT,
    description TEXT,
    price REAL NOT NULL,
    stock_sale INTEGER NOT NULL DEFAULT 0,
    stock_loan INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS customers (
    phone TEXT PRIMARY KEY,
    name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    book_id INTEGER NOT NULL REFERENCES books(id),
    quantity INTEGER NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_payment',  -- pending_payment | paid | cancelled
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    book_id INTEGER NOT NULL REFERENCES books(id),
    loaned_at TEXT NOT NULL,
    due_date TEXT NOT NULL,
    returned_at TEXT,
    renewals INTEGER NOT NULL DEFAULT 0,
    fee_amount REAL NOT NULL DEFAULT 0,
    fee_paid INTEGER NOT NULL DEFAULT 0
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(seed: bool = True) -> None:
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        if seed and conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
            from seed_data import BOOKS

            conn.executemany(
                "INSERT INTO books (title, author, category, description, price, stock_sale, stock_loan) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                BOOKS,
            )


def ensure_customer(phone: str, name: str | None = None) -> None:
    from utils import now

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO customers (phone, name, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(phone) DO UPDATE SET name = COALESCE(excluded.name, customers.name)",
            (phone, name, now().isoformat()),
        )
