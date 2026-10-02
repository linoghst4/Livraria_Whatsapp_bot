"""Ferramentas que o Gemini pode chamar.

São criadas por cliente (build_tools) para que o número de telefone fique fixo
no código: o modelo nunca escolhe nem vê dados de outro cliente.
Os docstrings são usados pelo Gemini para decidir quando chamar cada ferramenta.
"""
import functools
import logging

import config
from services import catalog, loans, orders
from utils import ServiceError, fmt_date, today

logger = logging.getLogger(__name__)


def _safe(fn):
    """Converte erros em {'error': ...} para o modelo explicar ao cliente."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ServiceError as e:
            return {"error": str(e)}
        except Exception:
            logger.exception("Erro na ferramenta %s", fn.__name__)
            return {"error": "Erro interno ao processar o pedido."}

    return wrapper


def build_tools(phone: str) -> list:
    @_safe
    def search_books(query: str) -> dict:
        """Pesquisa livros no catálogo por título, autor, categoria ou tema.

        Args:
            query: Texto de pesquisa, por exemplo 'Pepetela' ou 'livros de história'.
        """
        return {"results": catalog.search_books(query)}

    @_safe
    def get_book_details(book_id: int) -> dict:
        """Devolve preço, stock para venda e para empréstimo de um livro.

        Args:
            book_id: ID do livro, obtido em search_books.
        """
        return catalog.get_book(int(book_id))

    @_safe
    def buy_book(book_id: int, quantity: int = 1) -> dict:
        """Cria uma encomenda de compra. Só chamar depois de o cliente confirmar
        explicitamente o livro, a quantidade e o total.

        Args:
            book_id: ID do livro.
            quantity: Número de exemplares (1 a 10).
        """
        return orders.create_order(phone, int(book_id), int(quantity))

    @_safe
    def my_orders() -> dict:
        """Lista as encomendas do cliente e o estado de cada uma."""
        return {"orders": orders.list_orders(phone)}

    @_safe
    def cancel_order(order_id: int) -> dict:
        """Cancela uma encomenda do cliente que ainda aguarda pagamento.

        Args:
            order_id: Número da encomenda.
        """
        return orders.cancel_order(phone, int(order_id))

    @_safe
    def borrow_book(book_id: int) -> dict:
        """Regista um empréstimo e devolve a data limite de devolução. Só chamar
        depois de o cliente confirmar que quer pedir o livro emprestado.

        Args:
            book_id: ID do livro.
        """
        return loans.borrow_book(phone, int(book_id))

    @_safe
    def my_loans() -> dict:
        """Mostra os empréstimos ativos do cliente: data de devolução, dias restantes,
        atraso e multa atual, mais multas por pagar de livros já devolvidos."""
        return loans.list_loans(phone)

    @_safe
    def renew_loan(loan_id: int) -> dict:
        """Renova um empréstimo ativo, estendendo a data de devolução.

        Args:
            loan_id: Número do empréstimo, obtido em my_loans.
        """
        return loans.renew_loan(phone, int(loan_id))

    @_safe
    def get_store_info() -> dict:
        """Devolve horário, morada, contacto, formas de pagamento, a data de hoje
        e as regras de empréstimo e multas da loja."""
        return {
            "store": config.STORE_NAME,
            "hours": config.STORE_HOURS,
            "address": config.STORE_ADDRESS,
            "contact": config.STORE_CONTACT,
            "payment": config.PAYMENT_INSTRUCTIONS,
            "today": fmt_date(today()),
            "loan_policies": loans.get_policies(),
        }

    return [
        search_books,
        get_book_details,
        buy_book,
        my_orders,
        cancel_order,
        borrow_book,
        my_loans,
        renew_loan,
        get_store_info,
    ]
