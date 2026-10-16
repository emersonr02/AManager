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
    assert ProducaoService.converter_para_horas("ab:cd") == 0.0


def test_converter_para_string():
    assert ProducaoService.converter_para_string(1.5) == "01:30"
    assert ProducaoService.converter_para_string(0.0) == "00:00"


def test_converter_para_string_arredonda_minutos_com_transporte_de_hora():
    # 1.999h -> 59.94min arredonda para 60min, que deve transportar para a hora seguinte
    assert ProducaoService.converter_para_string(1.999) == "02:00"


@pytest.mark.parametrize("id_producao,esperado", [
    (12, "PRD000012"),
    ("12", "PRD000012"),
    (0, "PRD000000"),
    ("abc", "abc"),
    (None, "None"),
])
def test_formatar_codigo(id_producao, esperado):
    assert ProducaoService.formatar_codigo(id_producao) == esperado


@pytest.mark.parametrize("codigo,esperado", [
    ("PRD000012", 12),
    ("12", 12),
    (12, 12),
    ("PRD-000-045", 45),
    ("sem digitos", None),
    ("", None),
])
def test_extrair_id(codigo, esperado):
    assert ProducaoService.extrair_id(codigo) == esperado


def test_formatar_codigo_e_extrair_id_sao_inversos():
    codigo = ProducaoService.formatar_codigo(7)
    assert ProducaoService.extrair_id(codigo) == 7


def test_calcular_consumo_sls_usa_formula_oficial():
    # Fórmula: ((largura*profundidade*altura)/1_000_000) * densidade * perc
    resultado = ProducaoService.calcular_consumo_sls(altura_mm=5.0, perc_po_novo=0.3)
    esperado = round(((381 * 330 * 5.0) / 1_000_000) * 0.45 * 0.3, 4)
    assert resultado == esperado


def test_estimar_quantidade_fdm_sla_le_quantidade_consumida():
    assert ProducaoService.estimar_quantidade({"tecnologia": "FDM", "quantidade_consumida": "150"}) == "150"


def test_estimar_quantidade_sls_deriva_de_altura_e_percentagem():
    producao = {"tecnologia": "SLS", "altura_cuba": "5.0", "percentagem_po_novo": "0.3"}
    esperado = f"{ProducaoService.calcular_consumo_sls(5.0, 0.3):.2f}"
    assert ProducaoService.estimar_quantidade(producao) == esperado


def test_estimar_quantidade_sls_aceita_percentagem_em_formato_inteiro():
    producao_fracao = {"tecnologia": "SLS", "altura_cuba": "5.0", "percentagem_po_novo": "0.3"}
    producao_inteiro = {"tecnologia": "SLS", "altura_cuba": "5.0", "percentagem_po_novo": "30"}
    assert ProducaoService.estimar_quantidade(producao_inteiro) == ProducaoService.estimar_quantidade(producao_fracao)


def test_estimar_quantidade_sls_invalida_devolve_vazio():
    assert ProducaoService.estimar_quantidade({"tecnologia": "SLS", "altura_cuba": "abc", "percentagem_po_novo": "0.3"}) == ""


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


def test_obter_ultimo_lote_sls_sem_registos_devolve_vazio(arquivo_producoes):
    assert ProducaoService.obter_ultimo_lote_sls() == ""


def test_obter_ultimo_lote_sls_devolve_lote_mais_recente_preenchido(arquivo_producoes):
    _criar(arquivo_producoes, tecnologia="SLS", campos_extra={"lote_po": "LOTE-A"})
    _criar(arquivo_producoes, tecnologia="SLS", campos_extra={})
    _criar(arquivo_producoes, tecnologia="SLS", campos_extra={"lote_po": "LOTE-C"})

    assert ProducaoService.obter_ultimo_lote_sls() == "LOTE-C"


# ---------- Anular (em vez de apagar) ----------

def test_anular_producao_esconde_da_lista_mas_mantem_no_ficheiro(arquivo_producoes, tmp_path, monkeypatch):
    from services import audit_service
    from services.audit_service import AuditService
    monkeypatch.setattr(audit_service, "ARQUIVO_AUDIT_LOG", str(tmp_path / "audit.json"))
    p = ProducaoService.criar_producao(tecnologia="FDM", maquina="X1", tempo_estimado="01:00",
                                       pedidos_vinculados=[], operador="t")

    assert ProducaoService.anular_producao(p["id"], "duplicada", utilizador="qa") is True

    assert ProducaoService.obter_todos() == []
    guardada = ProducaoService.obter_todos(incluir_anuladas=True)[0]
    assert (guardada["anulada"], guardada["anulada_por"], guardada["motivo_anulacao"]) == (True, "qa", "duplicada")
    assert {e["campo"] for e in AuditService.obter_historico("producao", p["id"])} == {"anulada", "motivo_anulacao"}


def test_anular_producao_inexistente_devolve_false(arquivo_producoes):
    assert ProducaoService.anular_producao(999, "x") is False


# ---------- Peças de uma ordem ----------

def test_pecas_da_producao_usa_pecas_escolhidas():
    producao = {"pecas_producao": [{"pedido_id": 3, "indice": 1, "pn": "B", "material": "PLA", "qtd": 5}]}
    pecas = ProducaoService.pecas_da_producao(producao, pedidos=[])
    assert pecas == [{"pedido_id": 3, "indice": 1, "pn": "B", "material": "PLA", "qtd": 5, "chave": "3:B:1"}]


def test_pecas_da_producao_legacy_usa_o_que_faltava_do_pedido():
    pedidos = [{"id": 3, "pecas": [{"pn": "A", "material": "PLA", "qtd_solicitada": 10, "qtd_produzida": 4},
                                   {"pn": "B", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 2}]}]
    pecas = ProducaoService.pecas_da_producao({"pedidos_vinculados": [3]}, pedidos)
    assert [(p["pn"], p["qtd"]) for p in pecas] == [("A", 6), ("B", 2)]


def test_ncs_da_producao_junta_ordem_e_pecas_sem_repetir():
    producao = {"nc_codigo": "COD001", "qa_por_peca": {
        "1:A:0": {"nc_codigo": "COD003"}, "1:B:1": {"nc_codigo": "COD001"}, "1:C:2": {"nc_codigo": ""}}}
    assert ProducaoService.ncs_da_producao(producao) == ["COD001", "COD003"]


def test_qtd_em_producao_por_peca_so_conta_ordens_abertas(arquivo_producoes):
    for estado in ("Em Andamento", "Concluída"):
        p = ProducaoService.criar_producao(tecnologia="FDM", maquina="X1", tempo_estimado="01:00", pedidos_vinculados=[1],
                                           operador="t", campos_extra={"pecas_producao": [
                                               {"pedido_id": 1, "indice": 0, "pn": "A", "material": "PLA", "qtd": 3}]})
        p["estado"] = estado
        ProducaoService.atualizar_producao(p)

    assert ProducaoService.qtd_em_producao_por_peca() == {(1, 0): 3}


# ---------- Retrocompatibilidade: registos de versões anteriores ----------

@pytest.mark.parametrize("vinculos, esperado", [
    ([3, "4", "x", None, 3], [3, 4]),   # IDs como texto, lixo e repetidos
    ("7", [7]),                          # valor solto em vez de lista
    (None, []),
    ([], []),
])
def test_ids_pedidos_vinculados_normaliza_registos_antigos(vinculos, esperado):
    assert ProducaoService.ids_pedidos_vinculados({"pedidos_vinculados": vinculos}) == esperado


def test_pecas_da_producao_legacy_aceita_ids_como_texto():
    pedidos = [{"id": 3, "pecas": [{"pn": "A", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}]}]
    pecas = ProducaoService.pecas_da_producao({"pedidos_vinculados": ["3"]}, pedidos)
    assert [(p["pedido_id"], p["chave"]) for p in pecas] == [(3, "3:A:0")]


def test_pecas_da_producao_sem_pedidos_nao_le_o_ficheiro_de_pedidos(monkeypatch):
    # Ordens muito antigas (projeto/material direto na ordem) não têm pedidos
    from services.pedido_service import PedidoService
    monkeypatch.setattr(PedidoService, "obter_todos", lambda: pytest.fail("não devia ler pedidos"))
    assert ProducaoService.pecas_da_producao({"nr_projeto": "123", "material": "PLA"}) == []


def test_unidades_aprovadas_le_fechos_antigos_e_novos():
    pedidos = [{"id": 1, "pecas": [{"pn": "A", "material": "PLA", "qtd_solicitada": 4, "qtd_produzida": 0},
                                   {"pn": "B", "material": "PLA", "qtd_solicitada": 3, "qtd_produzida": 0},
                                   {"pn": "C", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}]}]
    antigo = {"estado": "Concluída", "pedidos_vinculados": [1], "qa_por_peca": {
        "1:A:0": {"conformidade": True}, "1:B:1": {"conformidade": False}}}   # C sem registo de QA
    assert ProducaoService.unidades_aprovadas(antigo, pedidos) == {"1:A:0": 4, "1:C:2": 2}

    novo = {"estado": "Concluída", "pecas_producao": [{"pedido_id": 1, "indice": 0, "pn": "A", "material": "PLA", "qtd": 4}],
            "qa_por_peca": {"1:A:0": {"qtd_aprovada": 3, "qtd_rejeitada": 1}}}
    assert ProducaoService.unidades_aprovadas(novo) == {"1:A:0": 3}

    assert ProducaoService.unidades_aprovadas({**antigo, "estado": "Cancelada"}, pedidos) == {}


def test_ordem_fechada_por_versao_anterior_conta_como_ja_creditada(arquivo_pedidos):
    from services.pedido_service import PedidoService
    pedido = PedidoService.criar_pedido(requerente_email="a@x.com", nr_projeto="1", nome_projeto="P", tecnologia="FDM",
                                        data_entrega="2026-09-01", link_arquivos="", observacoes="",
                                        pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 4, "qtd_produzida": 4}])
    chave = f"{pedido['id']}:A:0"
    antiga = {"estado": "Concluída", "pedidos_vinculados": [pedido["id"]], "qa_por_peca": {chave: {"conformidade": True}}}
    assert ProducaoService.unidades_ja_creditadas(antiga) == {chave: 4}
    assert ProducaoService.unidades_ja_creditadas({**antiga, "pecas_creditadas": {chave: "2"}}) == {chave: 2}
    assert ProducaoService.unidades_ja_creditadas({**antiga, "estado": "Em Andamento"}) == {}


def test_qtd_em_producao_por_peca_conta_ordens_abertas_antigas(arquivo_producoes, arquivo_pedidos):
    from services.pedido_service import PedidoService
    pedido = PedidoService.criar_pedido(requerente_email="a@x.com", nr_projeto="1", nome_projeto="P", tecnologia="FDM",
                                        data_entrega="2026-09-01", link_arquivos="", observacoes="",
                                        pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 10, "qtd_produzida": 4}])
    # Ordem aberta de uma versão anterior: cobre o pedido inteiro (ID como texto)
    ProducaoService.criar_producao(tecnologia="FDM", maquina="X1", tempo_estimado="01:00",
                                   pedidos_vinculados=[str(pedido["id"])], operador="t")

    assert ProducaoService.qtd_em_producao_por_peca() == {(pedido["id"], 0): 6}


def test_clonar_nao_herda_o_credito_da_ordem_original(arquivo_producoes):
    p1 = _criar(arquivo_producoes)
    ProducaoService.atualizar_producao({**p1, "estado": "Concluída", "pecas_creditadas": {"1:A:0": 3}})

    clone = ProducaoService.clonar_producao(p1["id"])

    assert "pecas_creditadas" not in clone
