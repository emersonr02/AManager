from services.pedido_service import PedidoService
from services.producao_service import ProducaoService
from gui.historico_tab import HistoricoTab


def _criar_producao(gui_arquivos, **overrides):
    dados = dict(
        tecnologia="FDM",
        maquina="X1C-1",
        tempo_estimado="02:00",
        pedidos_vinculados=[],
        operador="tester",
        campos_extra={},
    )
    data_inicio = overrides.pop("data_inicio", None)
    estado = overrides.pop("estado", None)
    dados.update(overrides)
    producao = ProducaoService.criar_producao(**dados)
    if data_inicio is not None or estado is not None:
        if data_inicio is not None:
            producao["data_inicio"] = data_inicio
        if estado is not None:
            producao["estado"] = estado
        ProducaoService.atualizar_producao(producao)
    return producao


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
    dados.update(overrides)
    return PedidoService.criar_pedido(**dados)


def _linhas(tab):
    return [tab.tab_tree.item(i)["values"] for i in tab.tab_tree.get_children()]


def test_tabela_vazia_sem_producoes(gui_arquivos, ctk_root):
    tab = HistoricoTab(ctk_root, None, None, None)

    assert _linhas(tab) == []
    assert tab.lbl_kpi_total.cget("text") == "0"
    assert tab.lbl_kpi_taxa.cget("text") == "0.0%"


def test_tabela_lista_producoes_com_codigo_formatado(gui_arquivos, ctk_root):
    p1 = _criar_producao(gui_arquivos)

    tab = HistoricoTab(ctk_root, None, None, None)

    linhas = _linhas(tab)
    assert len(linhas) == 1
    assert linhas[0][0] == ProducaoService.formatar_codigo(p1["id"])


def test_filtro_por_maquina(gui_arquivos, ctk_root):
    _criar_producao(gui_arquivos, maquina="X1C-1")
    _criar_producao(gui_arquivos, maquina="X1C-2")

    tab = HistoricoTab(ctk_root, None, None, None)
    tab.flt_maq.configure(values=["Todas", "X1C-1", "X1C-2"])
    tab.flt_maq.set("X1C-2")
    tab.atualizar_tabela()

    linhas = _linhas(tab)
    assert len(linhas) == 1
    assert linhas[0][3] == "X1C-2"


def test_filtro_por_estado_uniformiza_a_imprimir_como_em_andamento(gui_arquivos, ctk_root):
    _criar_producao(gui_arquivos)  # estado default "A Imprimir"

    tab = HistoricoTab(ctk_root, None, None, None)
    tab.flt_estado.set("Em Andamento")
    tab.atualizar_tabela()

    assert len(_linhas(tab)) == 1


def test_filtro_por_data_exclui_fora_do_intervalo(gui_arquivos, ctk_root):
    _criar_producao(gui_arquivos, data_inicio="2026-01-01 10:00:00")
    _criar_producao(gui_arquivos, data_inicio="2026-06-15 10:00:00")

    tab = HistoricoTab(ctk_root, None, None, None)
    tab.flt_data_ini.insert(0, "2026-06-01")
    tab.flt_data_fim.insert(0, "2026-06-30")
    tab.atualizar_tabela()

    linhas = _linhas(tab)
    assert len(linhas) == 1
    assert linhas[0][1] == "2026-06-15"


def test_kpi_taxa_sucesso_ignora_em_andamento(gui_arquivos, ctk_root):
    _criar_producao(gui_arquivos, estado="Concluída")
    _criar_producao(gui_arquivos, estado="Cancelada")
    _criar_producao(gui_arquivos, estado="Em Andamento")

    tab = HistoricoTab(ctk_root, None, None, None)

    # 1 sucesso em 2 finalizadas (Em Andamento não conta para o denominador)
    assert tab.lbl_kpi_taxa.cget("text") == "50.0%"
    assert tab.lbl_kpi_total.cget("text") == "3"


def test_kpi_total_horas_soma_tempos(gui_arquivos, ctk_root):
    _criar_producao(gui_arquivos, tempo_estimado="01:00")
    _criar_producao(gui_arquivos, tempo_estimado="00:30")

    tab = HistoricoTab(ctk_root, None, None, None)

    assert tab.lbl_kpi_horas.cget("text") == "01:30"


def test_join_com_pedido_vinculado_mostra_projeto_e_material(gui_arquivos, ctk_root):
    pedido = _criar_pedido(gui_arquivos, nr_projeto="999", nome_projeto="Projeto Teste",
                            pecas=[{"pn": "P1", "material": "ABS", "qtd_solicitada": 2, "qtd_produzida": 0}])
    _criar_producao(gui_arquivos, pedidos_vinculados=[pedido["id"]])

    tab = HistoricoTab(ctk_root, None, None, None)

    linhas = _linhas(tab)
    assert linhas[0][2] == "999 - Projeto Teste"
    assert linhas[0][4] == "ABS"


def test_producao_sem_pedido_vinculado_mostra_sem_projeto(gui_arquivos, ctk_root):
    _criar_producao(gui_arquivos, pedidos_vinculados=[])

    tab = HistoricoTab(ctk_root, None, None, None)

    linhas = _linhas(tab)
    assert linhas[0][2] == ""  # nr_projeto vazio no log em si (sem vínculo N:N)


def test_limpar_filtros_repoe_todos_os_registos(gui_arquivos, ctk_root):
    _criar_producao(gui_arquivos, maquina="X1C-1")
    _criar_producao(gui_arquivos, maquina="X1C-2")

    tab = HistoricoTab(ctk_root, None, None, None)
    tab.flt_maq.configure(values=["Todas", "X1C-1", "X1C-2"])
    tab.flt_maq.set("X1C-2")
    tab.atualizar_tabela()
    assert len(_linhas(tab)) == 1

    tab.limpar_filtros()
    assert len(_linhas(tab)) == 2


def test_clonar_log_cria_nova_producao_em_andamento(gui_arquivos, ctk_root, monkeypatch):
    p1 = _criar_producao(gui_arquivos, estado="Concluída")
    tab = HistoricoTab(ctk_root, None, None, None)
    monkeypatch.setattr("gui.historico_tab.messagebox.showinfo", lambda *a, **k: None)

    tab.tab_tree.selection_set(tab.tab_tree.get_children()[0])
    tab.clonar_log()

    todos = ProducaoService.obter_todos()
    assert len(todos) == 2
    clone = next(p for p in todos if p["id"] != p1["id"])
    assert clone["estado"] == "Em Andamento"


def test_remover_log_apaga_apos_confirmacao(gui_arquivos, ctk_root, monkeypatch):
    _criar_producao(gui_arquivos)
    tab = HistoricoTab(ctk_root, None, None, None)
    monkeypatch.setattr("gui.historico_tab.messagebox.askyesno", lambda *a, **k: True)

    tab.tab_tree.selection_set(tab.tab_tree.get_children()[0])
    tab.remover_log()

    assert ProducaoService.obter_todos() == []


def test_exportar_csv_gera_ficheiro_a_partir_da_tabela(gui_arquivos, ctk_root, monkeypatch, tmp_path):
    _criar_producao(gui_arquivos, maquina="X1C-1", tempo_estimado="01:00")
    tab = HistoricoTab(ctk_root, None, None, None)

    destino = str(tmp_path / "export.csv")
    monkeypatch.setattr("gui.historico_tab.filedialog.asksaveasfilename", lambda **k: destino)
    monkeypatch.setattr("gui.historico_tab.messagebox.showinfo", lambda *a, **k: None)

    tab.exportar_csv()

    import os
    assert os.path.exists(destino)
    with open(destino, encoding="utf-8-sig") as f:
        conteudo = f.read()
    assert "X1C-1" in conteudo
