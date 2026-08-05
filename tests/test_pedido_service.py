from services.pedido_service import PedidoService


def test_criar_pedido_atribui_ids_sequenciais(arquivo_pedidos):
    p1 = PedidoService.criar_pedido("a@x.com", "123 - Projeto A", "FDM", "resp", "obs")
    p2 = PedidoService.criar_pedido("b@x.com", "456 - Projeto B", "SLA", "resp2", "obs2")

    assert p1["id"] == 1
    assert p2["id"] == 2


def test_criar_pedido_limpa_nome_do_projeto(arquivo_pedidos):
    pedido = PedidoService.criar_pedido("a@x.com", "123 - Projeto A", "FDM", "resp", "obs")
    assert pedido["projeto"] == "123"


def test_atualizar_pedido_substitui_registo_existente(arquivo_pedidos):
    pedido = PedidoService.criar_pedido("a@x.com", "123 - Projeto A", "FDM", "resp", "obs")
    pedido["status"] = "Concluido"

    PedidoService.atualizar_pedido(pedido)

    todos = PedidoService.obter_todos()
    assert len(todos) == 1
    assert todos[0]["status"] == "Concluido"


def test_obter_todos_ordena_do_mais_recente_para_o_mais_antigo(arquivo_pedidos):
    PedidoService.criar_pedido("a@x.com", "1 - A", "FDM", "resp", "")
    PedidoService.criar_pedido("b@x.com", "2 - B", "FDM", "resp", "")

    todos = PedidoService.obter_todos()

    assert [p["id"] for p in todos] == [2, 1]
