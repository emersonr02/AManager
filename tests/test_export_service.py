import csv

from services.export_service import ExportService


def _pedido(id_, requerente="a@x.com", nr_projeto="123", nome_projeto="Projeto A", material="PLA"):
    return {
        "id": id_,
        "requerente_email": requerente,
        "nr_projeto": nr_projeto,
        "nome_projeto": nome_projeto,
        "pecas": [{"pn": "P1", "material": material, "qtd_solicitada": 1, "qtd_produzida": 0}],
    }


def _producao(id_=1, **overrides):
    dados = dict(
        id=id_,
        tecnologia="FDM",
        maquina="X1C-1",
        operador="joao",
        data_inicio="2026-08-01 10:00:00",
        pedidos_vinculados=[1],
        estado="Concluída",
        quantidade_consumida="150",
        tempo_estimado="02:00",
        tempo_real="02:10",
        quantidade_real="145",
        verificado_por="maria",
        data_fecho="2026-08-01 12:30:00",
        checklist_seguranca={"nivelamento_mesa": True, "analise_gcode": True, "qualidade_filamento": False},
        controlo_qualidade={"inspecao_visual": True, "controlo_dimensional": False, "conformidade": True},
        nc_codigo="COD001",
    )
    dados.update(overrides)
    return dados


def test_exportar_historico_csv_gera_linha_de_auditoria_completa(tmp_path, monkeypatch, arquivos_nc):
    from database.json_manager import JSONManager
    caminho_falhas, caminho_acoes = arquivos_nc
    JSONManager.salvar([{"cod": "COD001", "descricao": "Obstrução do bico", "tecnologia": "FDM"}], caminho_falhas)
    JSONManager.salvar([{"acao": "Limpeza do nozzle", "codigos_aplicaveis": ["COD001"]}], caminho_acoes)

    caminho_csv = tmp_path / "auditoria.csv"
    ok = ExportService.exportar_historico_csv(str(caminho_csv), [_producao()], [_pedido(1)])

    assert ok is True

    with open(caminho_csv, newline='', encoding='utf-8-sig') as f:
        linhas = list(csv.reader(f, delimiter=';'))

    cabecalho, linha = linhas[0], linhas[1]
    dados = dict(zip(cabecalho, linha))

    assert dados["Nº PRODUÇÃO"] == "PRD000001"
    assert dados["OPERADOR (INÍCIO)"] == "joao"
    assert dados["VERIFICADO POR (FECHO)"] == "maria"
    assert dados["DATA FECHO"] == "2026-08-01 12:30:00"
    assert dados["PEDIDOS VINCULADOS"] == "PED000001"
    assert dados["PROJETOS"] == "123 - Projeto A"
    assert dados["REQUERENTES"] == "a@x.com"
    assert dados["MATERIAL"] == "PLA"
    assert dados["QUANTIDADE ESTIMADA"] == "150"
    assert dados["QUANTIDADE REAL"] == "145"
    assert dados["CHECKLIST COMPLETO"] == "Não"
    assert "qualidade_filamento: NOK" in dados["CHECKLIST SEGURANÇA"]
    assert dados["INSPEÇÃO VISUAL"] == "Sim"
    assert dados["CONTROLO DIMENSIONAL"] == "Não"
    assert dados["CÓDIGO NC"] == "COD001"
    assert dados["DESCRIÇÃO NC"] == "Obstrução do bico"
    assert dados["AÇÕES CORRETIVAS SUGERIDAS"] == "Limpeza do nozzle"


def test_exportar_historico_csv_inclui_resumos_pareto(tmp_path):
    caminho_csv = tmp_path / "auditoria.csv"
    producoes = [
        _producao(id_=1, maquina="X1C-1", tempo_real="01:00", quantidade_real="100"),
        _producao(id_=2, maquina="X1C-1", tempo_real="02:00", quantidade_real="50"),
    ]
    ExportService.exportar_historico_csv(str(caminho_csv), producoes, [_pedido(1), _pedido(2)])

    conteudo = caminho_csv.read_text(encoding="utf-8-sig")

    assert "RESUMO POR MATERIAL" in conteudo
    assert "RESUMO POR MÁQUINA" in conteudo
    assert "X1C-1;03:00" in conteudo.replace("\r\n", "\n")


def test_exportar_historico_csv_devolve_false_em_caminho_invalido():
    ok = ExportService.exportar_historico_csv("/caminho/inexistente/auditoria.csv", [], [])
    assert ok is False
