import pytest

from database import json_manager
from services import pedido_service, maquina_service, nc_service


@pytest.fixture
def arquivo_pedidos(tmp_path, monkeypatch):
    caminho = tmp_path / "pedidos.json"
    monkeypatch.setattr(pedido_service, "ARQUIVO_PEDIDOS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_maquinas(tmp_path, monkeypatch):
    caminho = tmp_path / "parque_maquinas.json"
    monkeypatch.setattr(maquina_service, "ARQUIVO_MAQUINAS", str(caminho))
    return str(caminho)


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
