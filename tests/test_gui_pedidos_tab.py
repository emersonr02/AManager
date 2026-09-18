from services.pedido_service import PedidoService
from gui.pedidos_tab import PedidosTab


def _criar_pedido(gui_arquivos, **overrides):
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
    estado = overrides.pop("estado", None)
    ativo = overrides.pop("ativo", None)
    dados.update(overrides)
    pedido = PedidoService.criar_pedido(**dados)
    if estado is not None:
        pedido["estado"] = estado
        PedidoService.atualizar_pedido(pedido)
    if ativo is not None:
        pedido["ativo"] = ativo
        PedidoService.atualizar_pedido(pedido)
    return pedido


def _linhas(tab):
    return [tab.tree_pedidos.item(i)["values"] for i in tab.tree_pedidos.get_children()]


def test_tabela_vazia_sem_pedidos(gui_arquivos, ctk_root):
    tab = PedidosTab(ctk_root, None, None)

    assert _linhas(tab) == []
    assert tab.lbl_kpi_total.cget("text") == "0"


def test_tabela_lista_pedidos_ativos_com_codigo_formatado(gui_arquivos, ctk_root):
    p1 = _criar_pedido(gui_arquivos)

    tab = PedidosTab(ctk_root, None, None)

    linhas = _linhas(tab)
    assert len(linhas) == 1
    assert linhas[0][0] == PedidoService.formatar_codigo(p1["id"])
    assert linhas[0][4] == "Pendente"


def test_tabela_ignora_pedidos_cancelados_e_inativos(gui_arquivos, ctk_root):
    _criar_pedido(gui_arquivos, estado="Cancelado")
    _criar_pedido(gui_arquivos, ativo=False)
    _criar_pedido(gui_arquivos)  # este fica visível

    tab = PedidosTab(ctk_root, None, None)

    assert len(_linhas(tab)) == 1
    assert tab.lbl_kpi_total.cget("text") == "1"


def test_kpis_contam_andamento_e_entregues(gui_arquivos, ctk_root):
    _criar_pedido(gui_arquivos, estado="Em Andamento")
    _criar_pedido(gui_arquivos, estado="Entregue")
    _criar_pedido(gui_arquivos)  # Pendente

    tab = PedidosTab(ctk_root, None, None)

    assert tab.lbl_kpi_total.cget("text") == "3"
    assert tab.lbl_kpi_andamento.cget("text") == "1"
    assert tab.lbl_kpi_entregues.cget("text") == "1"


def test_soft_delete_pedido_marca_inativo_sem_remover(gui_arquivos, ctk_root, monkeypatch):
    p1 = _criar_pedido(gui_arquivos)
    tab = PedidosTab(ctk_root, None, None)

    monkeypatch.setattr("gui.pedidos_tab.messagebox.askyesno", lambda *a, **k: True)
    tab.tree_pedidos.selection_set(tab.tree_pedidos.get_children()[0])

    tab.soft_delete_pedido()

    pedidos = PedidoService.obter_todos()
    assert pedidos[0]["ativo"] is False
    assert _linhas(tab) == []


def _encontrar_widgets(container, classe):
    encontrados = []
    for child in container.winfo_children():
        if type(child).__name__ == classe:
            encontrados.append(child)
        encontrados.extend(_encontrar_widgets(child, classe))
    return encontrados


def test_abrir_dialogo_estado_guarda_novo_estado(gui_arquivos, ctk_root):
    p1 = _criar_pedido(gui_arquivos)
    tab = PedidosTab(ctk_root, None, None)
    tab.tree_pedidos.selection_set(tab.tree_pedidos.get_children()[0])

    tab.abrir_dialogo_estado()
    # O Toplevel é filho da janela raiz real (winfo_toplevel()), não do frame
    # descartável do teste — CTkToplevel ancora-se sempre à janela de topo.
    top = ctk_root.winfo_toplevel().winfo_children()[-1]

    combo = _encontrar_widgets(top, "CTkComboBox")[0]
    botao = _encontrar_widgets(top, "CTkButton")[0]

    combo.set("Concluído")
    botao.cget("command")()  # simula o clique em GUARDAR

    assert PedidoService.obter_todos()[0]["estado"] == "Concluído"
    assert top.winfo_exists() == 0  # a janela fecha-se após guardar
