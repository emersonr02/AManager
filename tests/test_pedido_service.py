from services.pedido_service import PedidoService


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
