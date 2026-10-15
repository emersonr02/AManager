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
    assert linhas[0][6] == "Pendente"


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

    # "Abertos" conta só Pendente + Em Andamento (antes contava também os entregues)
    assert tab.lbl_kpi_total.cget("text") == "2"
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


# ---------- Fase 2: prazo, progresso, separadores e pesquisa ----------

def test_separador_cancelados_mostra_pedidos_cancelados(gui_arquivos, ctk_root):
    _criar_pedido(gui_arquivos, estado="Cancelado")
    _criar_pedido(gui_arquivos)
    tab = PedidosTab(ctk_root, None, None)

    tab.seg_filtro.set("Cancelados")
    tab.atualizar_tabela()

    linhas = _linhas(tab)
    assert len(linhas) == 1
    assert linhas[0][6] == "Cancelado"


def test_pesquisa_filtra_por_projeto_ou_requerente(gui_arquivos, ctk_root):
    _criar_pedido(gui_arquivos, requerente_email="ana@x.com")
    _criar_pedido(gui_arquivos, requerente_email="rui@x.com")
    tab = PedidosTab(ctk_root, None, None)

    tab.ent_pesquisa.insert(0, "rui")
    tab.atualizar_tabela()

    assert [l[3] for l in _linhas(tab)] == ["rui@x.com"]


def test_abertos_ordenados_pelo_prazo_mais_proximo(gui_arquivos, ctk_root):
    from datetime import datetime, timedelta
    longe = _criar_pedido(gui_arquivos, data_entrega=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))
    perto = _criar_pedido(gui_arquivos, data_entrega=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
    tab = PedidosTab(ctk_root, None, None)

    codigos = [l[0] for l in _linhas(tab)]
    assert codigos == [PedidoService.formatar_codigo(perto["id"]), PedidoService.formatar_codigo(longe["id"])]


def test_pedido_atrasado_conta_no_kpi_e_e_assinalado(gui_arquivos, ctk_root):
    _criar_pedido(gui_arquivos, data_entrega="2020-01-01")
    tab = PedidosTab(ctk_root, None, None)

    assert tab.lbl_kpi_atrasados.cget("text") == "1"
    item = tab.tree_pedidos.get_children()[0]
    assert "atrasado" in tab.tree_pedidos.item(item)["values"][1]
    assert "tag_bad" in tab.tree_pedidos.item(item)["tags"]


def test_progresso_mostra_unidades_produzidas(gui_arquivos, ctk_root):
    _criar_pedido(gui_arquivos, pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 4, "qtd_produzida": 1}])
    tab = PedidosTab(ctk_root, None, None)

    assert _linhas(tab)[0][5] == "1/4"


def test_botoes_de_acao_so_ativos_com_selecao(gui_arquivos, ctk_root):
    _criar_pedido(gui_arquivos)
    tab = PedidosTab(ctk_root, None, None)

    assert tab.btn_editar.cget("state") == "disabled"
    tab.tree_pedidos.selection_set(tab.tree_pedidos.get_children()[0])
    tab._atualizar_botoes()
    assert tab.btn_editar.cget("state") == "normal"
