import os
import time

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


def test_lock_preso_e_quebrado_apos_timeout(json_file, monkeypatch):
    lock_file = json_file + ".lock"
    fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)

    tempos = iter([0, 0, 6, 6])  # start_time, 1a checagem (dentro do timeout), 2a checagem (expirou)
    monkeypatch.setattr(time, "time", lambda: next(tempos, 6))
    monkeypatch.setattr(time, "sleep", lambda _: None)

    JSONManager._adquirir_lock(json_file, timeout=5)

    assert os.path.exists(lock_file)
    JSONManager._libertar_lock(json_file)


def test_libertar_lock_sem_ficheiro_nao_gera_erro(json_file):
    JSONManager._libertar_lock(json_file)
