"""
SQLiteManager — gestão de ligação e esquema da base de dados.

Substitui o JSONManager e o seu locking de ficheiro por pasta de rede.
O SQLite trata a concorrência nativamente (WAL mode permite leituras
concorrentes com uma escrita em curso), por isso desaparece toda a
lógica de _adquirir_lock/_libertar_lock que tínhamos de manter à mão.

Uso típico num service:

    from database.sqlite_manager import SQLiteManager

    with SQLiteManager.conectar() as con:
        cur = con.execute("SELECT * FROM maquinas WHERE tech = ?", (tech,))
        return [dict(row) for row in cur.fetchall()]
"""
import os
import sqlite3
from contextlib import contextmanager

from config.paths import DATA_DIR

ARQUIVO_DB = os.path.join(DATA_DIR, "amanager.db")
_CAMINHO_SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


class SQLiteManager:

    @staticmethod
    def _nova_ligacao() -> sqlite3.Connection:
        con = sqlite3.connect(ARQUIVO_DB, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        # WAL: leituras não bloqueiam escritas nem vice-versa — é isto que
        # substitui o mecanismo de lock de ficheiro do JSONManager, sem
        # precisar de código nosso para o gerir.
        con.execute("PRAGMA journal_mode = WAL")
        return con

    @staticmethod
    @contextmanager
    def conectar():
        """Context manager: abre ligação, faz commit no sucesso, rollback
        em exceção, fecha sempre. Uso: `with SQLiteManager.conectar() as con:`"""
        con = SQLiteManager._nova_ligacao()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def garantir_esquema():
        """Cria todas as tabelas se ainda não existirem. Idempotente —
        seguro chamar em todos os arranques da app."""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(_CAMINHO_SCHEMA, "r", encoding="utf-8") as f:
            sql_schema = f.read()
        with SQLiteManager.conectar() as con:
            con.executescript(sql_schema)

    @staticmethod
    def dict_de_linha(row: sqlite3.Row) -> dict:
        """Converte uma sqlite3.Row num dict normal."""
        return dict(row) if row is not None else None

    @staticmethod
    def dicts_de_linhas(rows) -> list:
        return [dict(r) for r in rows]
