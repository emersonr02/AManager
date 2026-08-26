import pytest

from database import json_manager
from database import sqlite_manager


@pytest.fixture
def db_sqlite(tmp_path, monkeypatch):
    """Isola uma base de dados SQLite temporária, com o esquema já criado.
    Todos os services usam agora SQLite, por isso esta é a fixture base de
    isolamento para praticamente toda a suite."""
    caminho_db = tmp_path / "amanager_teste.db"
    monkeypatch.setattr(sqlite_manager, "ARQUIVO_DB", str(caminho_db))
    sqlite_manager.SQLiteManager.garantir_esquema()
    return str(caminho_db)


# As fixtures abaixo mantêm os nomes originais (usados por dezenas de testes)
# mas todas partilham a mesma BD SQLite isolada. Já não devolvem caminhos de
# ficheiros JSON — os testes usam-nas como dependência de isolamento e
# semeiam dados através dos próprios services ou de SQL direto.

@pytest.fixture
def arquivo_pedidos(db_sqlite):
    return db_sqlite


@pytest.fixture
def arquivo_projetos(db_sqlite):
    return db_sqlite


@pytest.fixture
def arquivo_materiais(db_sqlite):
    return db_sqlite


@pytest.fixture
def arquivo_producoes(db_sqlite):
    return db_sqlite


@pytest.fixture
def arquivo_maquinas(db_sqlite):
    return db_sqlite


@pytest.fixture
def arquivos_nc(db_sqlite):
    """Devolve (db, db) para manter a assinatura de desempacotamento que os
    testes existentes usam: `caminho_falhas, caminho_acoes = arquivos_nc`.
    Ambos apontam para a mesma BD, já que nc_falhas e acoes_corretivas são
    agora tabelas na mesma base de dados."""
    return db_sqlite, db_sqlite


@pytest.fixture
def json_file(tmp_path):
    """Ainda usada pelos testes do JSONManager, que continua a existir
    (é usado pelo script de migração para ler os ficheiros de origem)."""
    return str(tmp_path / "dados.json")


# ── Helpers de seeding partilhados ─────────────────────────────────────────
# Com os catálogos NC agora em SQLite, vários ficheiros de teste precisam de
# semear os mesmos dados. Centraliza-se aqui para não repetir SQL por todo o
# lado nem cada teste ter de saber o esquema de cor.

def seed_nc_falhas(entradas):
    """entradas: lista de dicts com cod/descricao/tecnologia (e opcionalmente
    categoria/impacto)."""
    from database.sqlite_manager import SQLiteManager
    with SQLiteManager.conectar() as con:
        for nc in entradas:
            con.execute(
                "INSERT OR REPLACE INTO nc_falhas (cod, descricao, categoria, tecnologia, impacto) "
                "VALUES (?, ?, ?, ?, ?)",
                (nc.get("cod"), nc.get("descricao", ""), nc.get("categoria", ""),
                 nc.get("tecnologia", ""), nc.get("impacto", "")),
            )


def seed_acoes_corretivas(entradas):
    """entradas: lista de dicts com act/acao/tecnologia/codigos_aplicaveis/etapas.
    Cria também as ligações N:N para os códigos aplicáveis."""
    import json
    from database.sqlite_manager import SQLiteManager
    with SQLiteManager.conectar() as con:
        for a in entradas:
            act = a.get("act")
            con.execute(
                "INSERT OR REPLACE INTO acoes_corretivas (act, acao, tecnologia, etapas) VALUES (?, ?, ?, ?)",
                (act, a.get("acao", ""), a.get("tecnologia", ""),
                 json.dumps(a.get("etapas", []), ensure_ascii=False)),
            )
            for cod in a.get("codigos_aplicaveis", []):
                con.execute(
                    "INSERT OR IGNORE INTO acoes_codigos_aplicaveis (act, nc_cod) VALUES (?, ?)",
                    (act, cod),
                )
