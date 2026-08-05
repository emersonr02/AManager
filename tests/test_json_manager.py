import os

from database.json_manager import JSONManager


def test_carregar_ficheiro_inexistente_devolve_lista_vazia(json_file):
    assert JSONManager.carregar(json_file) == []


def test_salvar_e_carregar_roundtrip(json_file):
    JSONManager.salvar([{"a": 1}], json_file)
    assert JSONManager.carregar(json_file) == [{"a": 1}]


def test_atualizar_faz_leitura_modificacao_escrita_atomica(json_file):
    JSONManager.salvar([{"a": 1}], json_file)
    resultado = JSONManager.atualizar(json_file, lambda dados: dados + [{"a": 2}])
    assert resultado == [{"a": 1}, {"a": 2}]
    assert JSONManager.carregar(json_file) == [{"a": 1}, {"a": 2}]


def test_ficheiro_corrompido_e_isolado_em_vez_de_perdido(json_file):
    with open(json_file, "w", encoding="utf-8") as f:
        f.write("{isto nao e json valido")

    resultado = JSONManager.carregar(json_file)

    assert resultado == []
    assert os.path.exists(json_file + ".corrompido")
    with open(json_file + ".corrompido", encoding="utf-8") as f:
        assert f.read() == "{isto nao e json valido"


def test_nao_deixa_lock_pendurado_apos_operacoes(json_file):
    JSONManager.salvar([1, 2, 3], json_file)
    JSONManager.carregar(json_file)
    JSONManager.atualizar(json_file, lambda d: d)
    assert not os.path.exists(json_file + ".lock")


def test_escrita_nao_deixa_ficheiro_temporario_para_tras(json_file):
    JSONManager.salvar([1, 2, 3], json_file)
    assert not os.path.exists(json_file + ".tmp")
