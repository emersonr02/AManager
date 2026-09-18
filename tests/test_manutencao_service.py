from datetime import datetime, timedelta

import pytest

from database.json_manager import JSONManager
from services.maquina_service import MaquinaService
from services.producao_service import ProducaoService
from services.manutencao_service import ManutencaoService


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _criar_maquina(mid="M1", nome="Printer 1", modelo="Bambu Lab X1C", estado="Operacional"):
    MaquinaService.salvar_maquina(mid=mid, nome=nome, tech="FDM", estado=estado, manutencao="OK", modelo=modelo)


def _criar_producao(maquina_nome, data_inicio, tempo_estimado="01:00"):
    producao = ProducaoService.criar_producao(
        tecnologia="FDM", maquina=maquina_nome, tempo_estimado=tempo_estimado,
        pedidos_vinculados=[], operador="tester", campos_extra={},
    )
    producao["data_inicio"] = _fmt(data_inicio)
    ProducaoService.atualizar_producao(producao)
    return producao


def _registar_conclusao_em(arquivo_manutencoes, tarefa_id, maquina_id, quando):
    JSONManager.salvar([{
        "id": 1, "tarefa_id": tarefa_id, "maquina_id": maquina_id,
        "data_realizacao": _fmt(quando), "operador": "tester", "notas": "",
    }], arquivo_manutencoes)


# ---------- Tarefas periódicas (CRUD) ----------

def test_criar_tarefa_sem_nenhuma_frequencia_falha(arquivo_tarefas_manutencao):
    with pytest.raises(ValueError):
        ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza")


def test_criar_tarefa_atribui_id_sequencial(arquivo_tarefas_manutencao):
    t1 = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="A", frequencia_dias=30)
    t2 = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="B", frequencia_horas=100)

    assert t1["id"] == 1
    assert t2["id"] == 2


def test_obter_tarefas_filtra_inativas_por_omissao(arquivo_tarefas_manutencao):
    ativa = ManutencaoService.criar_tarefa(modelo="X", nome="Ativa", frequencia_dias=30)
    inativa = ManutencaoService.criar_tarefa(modelo="X", nome="Inativa", frequencia_dias=30)
    ManutencaoService.definir_ativa(inativa["id"], False)

    assert [t["nome"] for t in ManutencaoService.obter_tarefas()] == ["Ativa"]
    assert len(ManutencaoService.obter_tarefas(incluir_inativas=True)) == 2


def test_atualizar_tarefa_substitui_registo(arquivo_tarefas_manutencao):
    t = ManutencaoService.criar_tarefa(modelo="X", nome="Nome Antigo", frequencia_dias=30)
    t["nome"] = "Nome Novo"

    ManutencaoService.atualizar_tarefa(t)

    assert ManutencaoService.obter_tarefas()[0]["nome"] == "Nome Novo"


def test_atualizar_tarefa_sem_frequencia_falha(arquivo_tarefas_manutencao):
    t = ManutencaoService.criar_tarefa(modelo="X", nome="Nome", frequencia_dias=30)
    t["frequencia_dias"] = None

    with pytest.raises(ValueError):
        ManutencaoService.atualizar_tarefa(t)


def test_definir_ativa_desativa_e_reativa(arquivo_tarefas_manutencao):
    t = ManutencaoService.criar_tarefa(modelo="X", nome="Nome", frequencia_dias=30)

    ManutencaoService.definir_ativa(t["id"], False)
    assert ManutencaoService.obter_tarefas() == []

    ManutencaoService.definir_ativa(t["id"], True)
    assert len(ManutencaoService.obter_tarefas()) == 1


# ---------- Histórico ----------

def test_registar_conclusao_atribui_id_e_data(arquivo_manutencoes):
    registo = ManutencaoService.registar_conclusao(tarefa_id=1, maquina_id="M1", operador="jsilva")

    assert registo["id"] == 1
    assert registo["operador"] == "jsilva"
    assert ManutencaoService.obter_historico() == [registo]


def test_obter_historico_filtra_por_maquina_e_tarefa(arquivo_manutencoes):
    ManutencaoService.registar_conclusao(tarefa_id=1, maquina_id="M1", operador="a")
    ManutencaoService.registar_conclusao(tarefa_id=2, maquina_id="M2", operador="b")

    assert len(ManutencaoService.obter_historico(maquina_id="M1")) == 1
    assert len(ManutencaoService.obter_historico(tarefa_id=2)) == 1


def test_obter_historico_ordena_do_mais_recente(arquivo_manutencoes):
    JSONManager.salvar([
        {"id": 1, "tarefa_id": 1, "maquina_id": "M1", "data_realizacao": "2026-01-01 10:00:00", "operador": "a", "notas": ""},
        {"id": 2, "tarefa_id": 1, "maquina_id": "M1", "data_realizacao": "2026-06-01 10:00:00", "operador": "b", "notas": ""},
    ], arquivo_manutencoes)

    historico = ManutencaoService.obter_historico()

    assert [h["id"] for h in historico] == [2, 1]


# ---------- calcular_proximas_tarefas ----------

def test_atrasada_por_dias(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina()
    tarefa = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)
    _registar_conclusao_em(arquivo_manutencoes, tarefa["id"], "M1", datetime.now() - timedelta(days=15))

    linhas = ManutencaoService.calcular_proximas_tarefas()

    assert len(linhas) == 1
    assert linhas[0]["estado"] == "atrasada"
    assert linhas[0]["dias_desde"] == 15


def test_atrasada_por_horas_mesmo_com_dias_recentes(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina(nome="X1C #1")
    tarefa = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Trocar bico", frequencia_horas=5)
    inicio = datetime.now() - timedelta(hours=2)
    _registar_conclusao_em(arquivo_manutencoes, tarefa["id"], "M1", inicio)

    _criar_producao("X1C #1", inicio + timedelta(minutes=10), tempo_estimado="03:00")
    _criar_producao("X1C #1", inicio + timedelta(minutes=30), tempo_estimado="03:00")

    linhas = ManutencaoService.calcular_proximas_tarefas()

    assert linhas[0]["estado"] == "atrasada"
    assert linhas[0]["horas_desde"] == 6.0
    assert linhas[0]["dias_desde"] == 0  # confirma que não foi a data a disparar


def test_nunca_concluida_usa_producao_mais_antiga_como_base(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina(nome="X1C #1")
    ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)

    _criar_producao("X1C #1", datetime.now() - timedelta(days=40))
    _criar_producao("X1C #1", datetime.now() - timedelta(days=1))  # mais recente, não deve ser a base

    linhas = ManutencaoService.calcular_proximas_tarefas()

    assert linhas[0]["estado"] == "atrasada"
    assert linhas[0]["dias_desde"] == 40
    assert linhas[0]["ultima_conclusao"] is None


def test_sem_producoes_e_sem_historico_fica_sem_dados(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina()
    ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)

    linhas = ManutencaoService.calcular_proximas_tarefas()

    assert linhas[0]["estado"] == "sem_dados"
    assert linhas[0]["ratio"] is None


def test_ratio_no_limiar_fica_proxima(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina()
    tarefa = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)
    _registar_conclusao_em(arquivo_manutencoes, tarefa["id"], "M1", datetime.now() - timedelta(days=8))

    linhas = ManutencaoService.calcular_proximas_tarefas()

    assert linhas[0]["ratio"] == 0.8
    assert linhas[0]["estado"] == "proxima"


def test_ignora_maquina_desativada(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina(estado="Desativado")
    ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)

    assert ManutencaoService.calcular_proximas_tarefas() == []


def test_ignora_maquina_sem_modelo(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    MaquinaService.salvar_maquina(mid="M1", nome="Sem Modelo", tech="FDM", estado="Operacional", manutencao="OK")
    ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)

    assert ManutencaoService.calcular_proximas_tarefas() == []


def test_ignora_tarefa_inativa(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina()
    tarefa = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)
    ManutencaoService.definir_ativa(tarefa["id"], False)

    assert ManutencaoService.calcular_proximas_tarefas() == []


def test_ordena_atrasadas_antes_de_proximas_e_ok(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina(mid="M1", nome="X1C #1")
    _criar_maquina(mid="M2", nome="X1C #2")
    t_ok = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="OK", frequencia_dias=30)
    t_atrasada = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Atrasada", frequencia_dias=10)

    JSONManager.salvar([
        {"id": 1, "tarefa_id": t_ok["id"], "maquina_id": "M1", "data_realizacao": _fmt(datetime.now() - timedelta(days=1)), "operador": "a", "notas": ""},
        {"id": 2, "tarefa_id": t_ok["id"], "maquina_id": "M2", "data_realizacao": _fmt(datetime.now() - timedelta(days=1)), "operador": "a", "notas": ""},
        {"id": 3, "tarefa_id": t_atrasada["id"], "maquina_id": "M1", "data_realizacao": _fmt(datetime.now() - timedelta(days=20)), "operador": "a", "notas": ""},
        {"id": 4, "tarefa_id": t_atrasada["id"], "maquina_id": "M2", "data_realizacao": _fmt(datetime.now() - timedelta(days=20)), "operador": "a", "notas": ""},
    ], arquivo_manutencoes)

    linhas = ManutencaoService.calcular_proximas_tarefas()

    assert linhas[0]["estado"] == "atrasada"
    assert linhas[1]["estado"] == "atrasada"
    assert linhas[2]["estado"] == "ok"
    assert linhas[3]["estado"] == "ok"


def test_contar_alertas_resume_atrasadas_e_proximas(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao):
    _criar_maquina()
    t_atrasada = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Atrasada", frequencia_dias=10)
    t_proxima = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Proxima", frequencia_dias=10)
    JSONManager.salvar([
        {"id": 1, "tarefa_id": t_atrasada["id"], "maquina_id": "M1", "data_realizacao": _fmt(datetime.now() - timedelta(days=15)), "operador": "a", "notas": ""},
        {"id": 2, "tarefa_id": t_proxima["id"], "maquina_id": "M1", "data_realizacao": _fmt(datetime.now() - timedelta(days=8)), "operador": "a", "notas": ""},
    ], arquivo_manutencoes)

    resumo = ManutencaoService.contar_alertas()

    assert resumo == {"atrasadas": 1, "proximas": 1}
