import pytest

from database.json_manager import JSONManager
from services.projeto_service import ProjetoService


def test_criar_projeto(arquivo_projetos):
    ProjetoService.criar_projeto("123456", "Projeto A")

    projetos = ProjetoService.obter_todos()
    assert projetos == [{"id": "123456", "nome": "Projeto A", "ativo": True}]


def test_criar_projeto_com_id_duplicado_falha(arquivo_projetos):
    ProjetoService.criar_projeto("123456", "Projeto A")

    with pytest.raises(ValueError):
        ProjetoService.criar_projeto("123456", "Outro Nome")


def test_atualizar_projeto(arquivo_projetos):
    ProjetoService.criar_projeto("123456", "Nome Antigo")

    ProjetoService.atualizar_projeto("123456", "654321", "Nome Novo")

    projetos = ProjetoService.obter_todos()
    assert projetos == [{"id": "654321", "nome": "Nome Novo", "ativo": True}]


def test_definir_ativo_desativa_e_reativa(arquivo_projetos):
    ProjetoService.criar_projeto("123456", "Projeto A")

    ProjetoService.definir_ativo("123456", False)
    assert ProjetoService.obter_todos() == []
    assert ProjetoService.obter_todos(incluir_inativos=True)[0]["ativo"] is False

    ProjetoService.definir_ativo("123456", True)
    assert len(ProjetoService.obter_todos()) == 1


def test_normaliza_entradas_legadas_em_formato_de_string(arquivo_projetos):
    JSONManager.salvar(["257147 - PPS AquaFountain"], arquivo_projetos)

    projetos = ProjetoService.obter_todos()

    assert projetos == [{"id": "257147", "nome": "PPS AquaFountain", "ativo": True}]
