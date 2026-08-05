import pytest

from services.producao_service import ProducaoService


@pytest.mark.parametrize("valor,esperado", [
    ("01:30", True),
    ("1:30", False),
    ("01:3", False),
    ("", False),
    ("99:99", True),
    ("abcd", False),
])
def test_validar_formato_tempo(valor, esperado):
    assert ProducaoService.validar_formato_tempo(valor) == esperado


@pytest.mark.parametrize("valor,esperado", [
    ("50", True),
    ("0", False),
    ("-5", False),
    ("abc", False),
    ("", False),
    ("3,5", True),
    ("  7.2  ", True),
])
def test_validar_numero_positivo(valor, esperado):
    assert ProducaoService.validar_numero_positivo(valor) == esperado


def test_converter_para_horas():
    assert ProducaoService.converter_para_horas("01:30") == 1.5
    assert ProducaoService.converter_para_horas("00:00") == 0.0
    assert ProducaoService.converter_para_horas("invalido") == 0.0


def test_converter_para_string():
    assert ProducaoService.converter_para_string(1.5) == "01:30"
    assert ProducaoService.converter_para_string(0.0) == "00:00"


def test_calcular_consumo_sls_usa_formula_oficial():
    # Fórmula: ((largura*profundidade*altura)/1_000_000) * densidade * perc
    resultado = ProducaoService.calcular_consumo_sls(altura_mm=5.0, perc_po_novo=0.3)
    esperado = round(((381 * 330 * 5.0) / 1_000_000) * 0.45 * 0.3, 4)
    assert resultado == esperado


def _criar(arquivo_producoes, **overrides):
    dados = dict(
        tecnologia="FDM",
        maquina="X1C-1",
        tempo_estimado="02:30",
        pedidos_vinculados=[1],
        operador="tester",
        campos_extra={"quantidade_consumida": "150"},
    )
    dados.update(overrides)
    return ProducaoService.criar_producao(**dados)


def test_criar_producao_atribui_ids_sequenciais(arquivo_producoes):
    p1 = _criar(arquivo_producoes)
    p2 = _criar(arquivo_producoes)

    assert p1["id"] == 1
    assert p2["id"] == 2


def test_criar_producao_usa_esquema_canonico(arquivo_producoes):
    producao = _criar(arquivo_producoes)

    assert producao["estado"] == "A Imprimir"
    assert producao["pedidos_vinculados"] == [1]
    assert producao["quantidade_consumida"] == "150"


def test_obter_todos_ordena_do_mais_recente_para_o_mais_antigo(arquivo_producoes):
    _criar(arquivo_producoes)
    _criar(arquivo_producoes)

    todos = ProducaoService.obter_todos()

    assert [p["id"] for p in todos] == [2, 1]


def test_obter_por_id(arquivo_producoes):
    p1 = _criar(arquivo_producoes)

    assert ProducaoService.obter_por_id(p1["id"])["id"] == p1["id"]
    assert ProducaoService.obter_por_id(999) is None


def test_atualizar_producao_substitui_registo_existente(arquivo_producoes):
    p1 = _criar(arquivo_producoes)
    p1["estado"] = "Concluída"

    ProducaoService.atualizar_producao(p1)

    assert ProducaoService.obter_por_id(p1["id"])["estado"] == "Concluída"


def test_clonar_producao_gera_novo_id_e_reseta_estado(arquivo_producoes):
    p1 = _criar(arquivo_producoes)
    ProducaoService.atualizar_producao({**p1, "estado": "Concluída", "tempo_real": "02:45", "quantidade_real": "140"})

    clone = ProducaoService.clonar_producao(p1["id"])

    assert clone["id"] == 2
    assert clone["estado"] == "Em Andamento"
    assert "tempo_real" not in clone
    assert "quantidade_real" not in clone


def test_clonar_producao_inexistente_retorna_none(arquivo_producoes):
    assert ProducaoService.clonar_producao(999) is None


def test_remover_producao(arquivo_producoes):
    p1 = _criar(arquivo_producoes)

    ProducaoService.remover_producao(p1["id"])

    assert ProducaoService.obter_todos() == []
