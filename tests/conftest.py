import pytest

from database import json_manager
from database import sqlite_manager
from services import pedido_service, nc_service, projeto_service, material_service


@pytest.fixture
def db_sqlite(tmp_path, monkeypatch):
    """Isola uma base de dados SQLite temporária, com o esquema já criado.
    Usada por MaquinaService e ProducaoService (já migrados) — os outros
    services ainda usam ficheiros JSON e as suas próprias fixtures."""
    caminho_db = tmp_path / "amanager_teste.db"
    monkeypatch.setattr(sqlite_manager, "ARQUIVO_DB", str(caminho_db))
    sqlite_manager.SQLiteManager.garantir_esquema()
    return str(caminho_db)


@pytest.fixture
def arquivo_pedidos(tmp_path, monkeypatch):
    caminho = tmp_path / "pedidos.json"
    monkeypatch.setattr(pedido_service, "ARQUIVO_PEDIDOS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_projetos(tmp_path, monkeypatch):
    caminho = tmp_path / "projetos.json"
    monkeypatch.setattr(projeto_service, "ARQUIVO_PROJETOS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_materiais(tmp_path, monkeypatch):
    caminho = tmp_path / "materiais.json"
    monkeypatch.setattr(material_service, "ARQUIVO_MATERIAIS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_producoes(db_sqlite):
    """ProducaoService já foi migrado para SQLite — esta fixture agora só
    garante isolamento (uma BD nova por teste), não devolve um caminho de
    ficheiro JSON. Mantém o mesmo nome por compatibilidade com os testes
    existentes, que a usam apenas como dependência de isolamento (nunca
    escrevem diretamente no valor devolvido)."""
    return db_sqlite


@pytest.fixture
def arquivo_maquinas(db_sqlite):
    """Idem — MaquinaService também já está em SQLite, partilha a mesma BD."""
    return db_sqlite


@pytest.fixture
def arquivos_nc(tmp_path, monkeypatch):
    falhas = tmp_path / "nc_falhas.json"
    acoes = tmp_path / "acoes_corretivas.json"
    monkeypatch.setattr(nc_service, "ARQUIVO_NC_FALHAS", str(falhas))
    monkeypatch.setattr(nc_service, "ARQUIVO_ACOES", str(acoes))
    return str(falhas), str(acoes)


@pytest.fixture
def json_file(tmp_path):
    return str(tmp_path / "dados.json")
