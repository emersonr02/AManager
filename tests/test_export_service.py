import csv

from services.export_service import ExportService


def test_exportar_historico_csv_gera_ficheiro_com_secoes_esperadas(tmp_path):
    caminho = str(tmp_path / "historico.csv")
    dados_principais = [
        ["1", "2026-01-01", "Projeto A", "Maquina 1", "PA12", "10", "01:30", "Concluido"],
    ]
    consumo_materiais = {"PA12": 10.5}
    horas_maquinas = {"Maquina 1": 1.5}

    resultado = ExportService.exportar_historico_csv(
        caminho, dados_principais, consumo_materiais, horas_maquinas
    )

    assert resultado is True
    with open(caminho, encoding="utf-8-sig") as f:
        linhas = list(csv.reader(f, delimiter=";"))

    assert linhas[0] == ["ID", "DATA", "PROJETO", "MAQUINA", "MATERIAL", "QUANTIDADE", "TEMPO", "ESTADO"]
    assert linhas[1] == dados_principais[0]
    assert ["RESUMO POR MATERIAL", "QUANTIDADE TOTAL"] in linhas
    assert ["PA12", "10.50"] in linhas
    assert ["RESUMO POR MÁQUINA", "HORAS TOTAIS"] in linhas


def test_exportar_historico_csv_sem_dados_ainda_escreve_cabecalhos(tmp_path):
    caminho = str(tmp_path / "vazio.csv")

    resultado = ExportService.exportar_historico_csv(caminho, [], {}, {})

    assert resultado is True
    with open(caminho, encoding="utf-8-sig") as f:
        linhas = list(csv.reader(f, delimiter=";"))
    assert linhas[0] == ["ID", "DATA", "PROJETO", "MAQUINA", "MATERIAL", "QUANTIDADE", "TEMPO", "ESTADO"]


def test_exportar_historico_csv_caminho_invalido_devolve_false():
    resultado = ExportService.exportar_historico_csv(
        "Z:/pasta_inexistente_xyz/ficheiro.csv", [], {}, {}
    )

    assert resultado is False
