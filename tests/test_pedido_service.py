from datetime import datetime

import pytest

from services.pedido_service import PedidoService


@pytest.mark.parametrize("id_pedido,esperado", [
    (7, "PED000007"),
    ("7", "PED000007"),
    (0, "PED000000"),
    ("abc", "abc"),
    (None, "None"),
])
def test_formatar_codigo(id_pedido, esperado):
    assert PedidoService.formatar_codigo(id_pedido) == esperado


@pytest.mark.parametrize("codigo,esperado", [
    ("PED000007", 7),
    ("7", 7),
    (7, 7),
    ("PED-000-045", 45),
    ("sem digitos", None),
    ("", None),
])
def test_extrair_id(codigo, esperado):
    assert PedidoService.extrair_id(codigo) == esperado


def _criar(arquivo_pedidos, **overrides):
    dados = dict(
        requerente_email="a@x.com",
        nr_projeto="123",
        nome_projeto="Projeto A",
        tecnologia="FDM",
        data_entrega="2026-09-01",
        link_arquivos="",
        observacoes="",
        pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}],
    )
    dados.update(overrides)
    return PedidoService.criar_pedido(**dados)


def test_criar_pedido_atribui_ids_sequenciais(arquivo_pedidos):
    p1 = _criar(arquivo_pedidos)
    p2 = _criar(arquivo_pedidos)

    assert p1["id"] == 1
    assert p2["id"] == 2


def test_criar_pedido_usa_esquema_canonico(arquivo_pedidos):
    pedido = _criar(arquivo_pedidos)

    assert pedido["nr_projeto"] == "123"
    assert pedido["estado"] == "Pendente"
    assert pedido["producoes_vinculadas"] == []
    assert "status" not in pedido
    assert "projeto" not in pedido


def test_atualizar_pedido_substitui_registo_existente(arquivo_pedidos):
    pedido = _criar(arquivo_pedidos)
    pedido["estado"] = "Concluído"

    PedidoService.atualizar_pedido(pedido)

    todos = PedidoService.obter_todos()
    assert len(todos) == 1
    assert todos[0]["estado"] == "Concluído"


def test_obter_todos_ordena_do_mais_recente_para_o_mais_antigo(arquivo_pedidos):
    _criar(arquivo_pedidos, nr_projeto="1")
    _criar(arquivo_pedidos, nr_projeto="2")

    todos = PedidoService.obter_todos()

    assert [p["id"] for p in todos] == [2, 1]


def test_alterar_estado_atualiza_estado_e_data(arquivo_pedidos):
    pedido = _criar(arquivo_pedidos)

    PedidoService.alterar_estado(pedido["id"], "Em Andamento")

    encontrado = PedidoService.obter_todos()[0]
    assert encontrado["estado"] == "Em Andamento"
    assert encontrado["data_atualizacao"] == datetime.now().strftime("%Y-%m-%d")


def test_eliminar_pedido_faz_soft_delete(arquivo_pedidos):
    pedido = _criar(arquivo_pedidos)

    PedidoService.eliminar_pedido(pedido["id"])

    encontrado = PedidoService.obter_todos()[0]
    assert encontrado["ativo"] is False
    assert encontrado["estado"] == "Cancelado"


def test_vincular_producao_regista_link_inverso_e_estado(arquivo_pedidos):
    p1 = _criar(arquivo_pedidos)
    p2 = _criar(arquivo_pedidos)

    PedidoService.vincular_producao([p1["id"], p2["id"]], 10)

    todos = {p["id"]: p for p in PedidoService.obter_todos()}
    assert todos[p1["id"]]["producoes_vinculadas"] == [10]
    assert todos[p1["id"]]["estado"] == "Em Andamento"
    assert todos[p2["id"]]["producoes_vinculadas"] == [10]


def test_vincular_producao_nao_duplica_id_ja_presente(arquivo_pedidos):
    p1 = _criar(arquivo_pedidos)

    PedidoService.vincular_producao([p1["id"]], 10)
    PedidoService.vincular_producao([p1["id"]], 10)

    encontrado = PedidoService.obter_todos()[0]
    assert encontrado["producoes_vinculadas"] == [10]


# ---------- Validação de pedidos (partilhada por Novo e Editar Pedido) ----------

def _peca(pn="P1", material="PLA", qtd="2"):
    return {"pn": pn, "material": material, "qtd": qtd}


@pytest.mark.parametrize("entrada,esperado", [
    ("2026-09-20", "2026-09-20"),
    ("20/09/2026", "2026-09-20"),
    ("20-09-2026", "2026-09-20"),
    (" 2026-09-20 ", "2026-09-20"),
    ("2026-13-01", None),
    ("amanhã", None),
    ("", None),
    (None, None),
])
def test_normalizar_data_entrega(entrada, esperado):
    assert PedidoService.normalizar_data_entrega(entrada) == esperado


def test_validar_dados_pedido_completo_nao_tem_erros():
    assert PedidoService.validar_dados_pedido("a@x.com", "111 - P", "FDM", "2026-09-20", [_peca()]) == []


@pytest.mark.parametrize("tecnologia", ["", "fdm", "Outra"])
def test_validar_dados_pedido_exige_tecnologia_conhecida(tecnologia):
    erros = PedidoService.validar_dados_pedido("a@x.com", "111 - P", tecnologia, "2026-09-20", [_peca()])
    assert any("tecnologia" in e for e in erros)


def test_validar_dados_pedido_exige_projeto_e_requerente():
    erros = PedidoService.validar_dados_pedido("  ", "", "FDM", "2026-09-20", [_peca()])
    assert any("requerente" in e for e in erros)
    assert any("projeto" in e for e in erros)


def test_validar_dados_pedido_rejeita_data_invalida():
    erros = PedidoService.validar_dados_pedido("a@x.com", "111 - P", "FDM", "31/02/2026", [_peca()])
    assert any("Data de entrega inválida" in e for e in erros)


def test_validar_dados_pedido_exige_pelo_menos_uma_peca():
    erros = PedidoService.validar_dados_pedido("a@x.com", "111 - P", "FDM", "2026-09-20", [])
    assert any("pelo menos uma peça" in e for e in erros)


@pytest.mark.parametrize("peca,trecho", [
    (_peca(pn=""), "Part Number"),
    (_peca(material=""), "material"),
    (_peca(qtd=""), "quantidade"),
    (_peca(qtd="0"), "quantidade"),
    (_peca(qtd="2.5"), "quantidade"),
    (_peca(qtd="-1"), "quantidade"),
])
def test_validar_dados_pedido_valida_cada_peca(peca, trecho):
    erros = PedidoService.validar_dados_pedido("a@x.com", "111 - P", "FDM", "2026-09-20", [_peca(), peca])
    assert len(erros) == 1
    assert trecho in erros[0]


def test_validar_dados_pedido_devolve_todos_os_erros_de_uma_vez():
    erros = PedidoService.validar_dados_pedido("", "", "", "", [_peca(pn="", material="", qtd="")])
    assert len(erros) == 7


# ---------- Progresso por peça e fecho do ciclo ordem → pedido ----------

def _pecas(*pares):
    return [{"pn": f"P{i}", "material": "PLA", "qtd_solicitada": s, "qtd_produzida": f} for i, (s, f) in enumerate(pares)]


def test_progresso_soma_unidades_e_nao_passa_do_pedido():
    assert PedidoService.progresso({"pecas": _pecas((4, 1), (2, 5))}) == (3, 6)
    assert PedidoService.progresso({"pecas": []}) == (0, 0)


@pytest.mark.parametrize("pecas,estado,vinculadas,esperado", [
    (_pecas((2, 2)), "Em Andamento", [1], "Concluído"),
    (_pecas((2, 1)), "Pendente", [], "Em Andamento"),
    (_pecas((2, 0)), "Pendente", [7], "Em Andamento"),
    (_pecas((2, 0)), "Pendente", [], "Pendente"),
    (_pecas((2, 2)), "Entregue", [1], "Entregue"),   # nunca sugere recuar
])
def test_estado_sugerido(pecas, estado, vinculadas, esperado):
    assert PedidoService.estado_sugerido({"pecas": pecas, "estado": estado, "producoes_vinculadas": vinculadas}) == esperado


def test_dias_ate_prazo():
    from datetime import date
    hoje = date(2026, 10, 15)
    assert PedidoService.dias_ate_prazo({"data_entrega": "2026-10-20"}, hoje) == 5
    assert PedidoService.dias_ate_prazo({"data_entrega": "13/10/2026"}, hoje) == -2
    assert PedidoService.dias_ate_prazo({"data_entrega": ""}, hoje) is None


def test_registar_pecas_produzidas_marca_so_as_linhas_indicadas(arquivo_pedidos):
    p = _criar(arquivo_pedidos, pecas=_pecas((3, 0), (5, 0)))

    alterados = PedidoService.registar_pecas_produzidas([f"{p['id']}:P1:1", "lixo", "x:y:z"])

    guardado = PedidoService.obter_por_id(p["id"])
    assert [pc["qtd_produzida"] for pc in guardado["pecas"]] == [0, 5]
    assert len(alterados) == 1 and alterados[0]["id"] == p["id"]


def test_registar_pecas_produzidas_e_idempotente(arquivo_pedidos):
    p = _criar(arquivo_pedidos, pecas=_pecas((3, 0)))
    PedidoService.registar_pecas_produzidas([f"{p['id']}:P0:0"])

    assert PedidoService.registar_pecas_produzidas([f"{p['id']}:P0:0"]) == []
