import pytest

from database.json_manager import JSONManager
from services.material_service import MaterialService


def test_criar_material(arquivo_materiais):
    MaterialService.criar_material("TPU", "Generic")

    materiais = MaterialService.obter_todos()
    assert materiais == [{"nome": "TPU", "fabricante": "Generic", "ativo": True}]


def test_criar_material_duplicado_falha(arquivo_materiais):
    MaterialService.criar_material("TPU", "Generic")

    with pytest.raises(ValueError):
        MaterialService.criar_material("TPU", "Generic")


def test_mesmo_nome_fabricante_diferente_nao_e_duplicado(arquivo_materiais):
    MaterialService.criar_material("TPU", "Generic")
    MaterialService.criar_material("TPU", "Bambu Lab")

    assert len(MaterialService.obter_todos()) == 2


def test_atualizar_material(arquivo_materiais):
    MaterialService.criar_material("TPU", "Generic")

    MaterialService.atualizar_material("TPU", "Generic", "TPU 95A", "Generic")

    materiais = MaterialService.obter_todos()
    assert materiais == [{"nome": "TPU 95A", "fabricante": "Generic", "ativo": True}]


def test_definir_ativo_desativa_e_reativa(arquivo_materiais):
    MaterialService.criar_material("TPU", "Generic")

    MaterialService.definir_ativo("TPU", "Generic", False)
    assert MaterialService.obter_todos() == []
    assert MaterialService.obter_todos(incluir_inativos=True)[0]["ativo"] is False

    MaterialService.definir_ativo("TPU", "Generic", True)
    assert len(MaterialService.obter_todos()) == 1


def test_normaliza_entradas_legadas_em_formato_de_string(arquivo_materiais):
    JSONManager.salvar(["PA12 - 3DSystems"], arquivo_materiais)

    materiais = MaterialService.obter_todos()

    assert materiais == [{"nome": "PA12", "fabricante": "3DSystems", "ativo": True}]
