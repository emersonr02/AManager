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
