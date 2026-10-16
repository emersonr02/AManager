from datetime import datetime, timedelta

from database.json_manager import JSONManager
from services.pedido_service import PedidoService
from services.producao_service import ProducaoService
from services.maquina_service import MaquinaService
from services.manutencao_service import ManutencaoService
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
    assert linhas[0][1] == "15/06/2026"


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


def test_anular_ordem_esconde_mas_mantem_registo_e_auditoria(gui_arquivos, ctk_root, monkeypatch):
    # Antes "Apagar registo" apagava de vez um registo de qualidade, sem rasto.
    from services.audit_service import AuditService
    p = _criar_producao(gui_arquivos)
    tab = HistoricoTab(ctk_root, None, None, None)
    tab.tab_tree.selection_set(tab.tab_tree.get_children()[0])

    tab.anular_ordem()
    dialogo = ctk_root.winfo_toplevel().winfo_children()[-1]
    dialogo.ent_motivo.insert(0, "registo duplicado")
    dialogo.confirmar()

    assert ProducaoService.obter_todos() == []                      # deixa de contar
    guardada = ProducaoService.obter_todos(incluir_anuladas=True)[0]  # mas continua no ficheiro
    assert guardada["anulada"] is True
    assert guardada["motivo_anulacao"] == "registo duplicado"
    assert any(e["campo"] == "anulada" for e in AuditService.obter_historico("producao", p["id"]))
    assert _linhas(tab) == []


def test_anular_sem_motivo_e_bloqueado(gui_arquivos, ctk_root, monkeypatch):
    avisos = []
    monkeypatch.setattr("gui.historico_tab.messagebox.showwarning", lambda t, m: avisos.append(m))
    _criar_producao(gui_arquivos)
    tab = HistoricoTab(ctk_root, None, None, None)
    tab.tab_tree.selection_set(tab.tab_tree.get_children()[0])

    tab.anular_ordem()
    dialogo = ctk_root.winfo_toplevel().winfo_children()[-1]
    dialogo.confirmar()

    assert avisos
    assert len(ProducaoService.obter_todos()) == 1
    dialogo.destroy()


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


# ---------- Fase 2: botões ligados à seleção, detalhe e fecho do ciclo ----------

def test_botoes_de_acao_so_ativos_com_selecao(gui_arquivos, ctk_root):
    _criar_producao(gui_arquivos)
    tab = HistoricoTab(ctk_root, None, None, None)

    assert tab.btn_fechar.cget("state") == "disabled"
    tab.tab_tree.selection_set(tab.tab_tree.get_children()[0])
    tab._atualizar_botoes()
    assert tab.btn_fechar.cget("state") == "normal"


def test_detalhe_mostra_operador_e_pedidos(gui_arquivos, ctk_root):
    pedido = _criar_pedido(gui_arquivos)
    _criar_producao(gui_arquivos, pedidos_vinculados=[pedido["id"]], operador="jsilva")
    tab = HistoricoTab(ctk_root, None, None, None)

    tab.tab_tree.selection_set(tab.tab_tree.get_children()[0])
    tab._mostrar_detalhe()

    texto = tab.lbl_detalhe.cget("text")
    assert "jsilva" in texto
    assert PedidoService.formatar_codigo(pedido["id"]) in texto


def test_concluir_ordem_regista_pecas_e_propoe_estado_do_pedido(gui_arquivos, ctk_root, monkeypatch):
    perguntas = []
    monkeypatch.setattr("gui.historico_tab.messagebox.askyesno", lambda t, m: perguntas.append(m) or True)
    pedido = _criar_pedido(gui_arquivos, pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}])
    producao = _criar_producao(gui_arquivos, pedidos_vinculados=[pedido["id"]])
    PedidoService.vincular_producao([pedido["id"]], producao["id"])
    tab = HistoricoTab(ctk_root, None, None, None)

    producao["estado"] = "Concluída"
    producao["qa_por_peca"] = {f"{pedido['id']}:P1:0": {"inspecao_visual": True, "controlo_dimensional": True, "conformidade": True}}
    tab.salvar_estado_final_ordem(producao)

    atualizado = PedidoService.obter_por_id(pedido["id"])
    assert atualizado["pecas"][0]["qtd_produzida"] == 2
    assert perguntas and "Concluído" in perguntas[0]
    assert atualizado["estado"] == "Concluído"


def test_recusar_proposta_mantem_estado_do_pedido(gui_arquivos, ctk_root, monkeypatch):
    monkeypatch.setattr("gui.historico_tab.messagebox.askyesno", lambda t, m: False)
    pedido = _criar_pedido(gui_arquivos, pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}])
    producao = _criar_producao(gui_arquivos, pedidos_vinculados=[pedido["id"]])
    PedidoService.vincular_producao([pedido["id"]], producao["id"])
    tab = HistoricoTab(ctk_root, None, None, None)

    producao["estado"] = "Concluída"
    producao["qa_por_peca"] = {f"{pedido['id']}:P1:0": {"conformidade": True}}
    tab.salvar_estado_final_ordem(producao)

    assert PedidoService.obter_por_id(pedido["id"])["estado"] == "Em Andamento"


# ---------- Crédito no pedido por unidades aprovadas (idempotente) ----------

def _ordem_com_pecas(gui_arquivos, pedido, qtd):
    producao = _criar_producao(gui_arquivos, pedidos_vinculados=[pedido["id"]], campos_extra={"pecas_producao": [
        {"pedido_id": pedido["id"], "indice": 0, "pn": "P1", "material": "PLA", "qtd": qtd}]})
    PedidoService.vincular_producao([pedido["id"]], producao["id"])
    return producao


def _fechar(producao, pedido, aprovadas, rejeitadas, estado="Concluída"):
    producao["estado"] = estado
    producao["qa_por_peca"] = {f"{pedido['id']}:P1:0": {
        "qtd_planeada": aprovadas + rejeitadas, "qtd_aprovada": aprovadas, "qtd_rejeitada": rejeitadas,
        "nc_codigo": "COD003" if rejeitadas else "", "inspecao_visual": True, "controlo_dimensional": True,
        "conformidade": rejeitadas == 0}}
    return producao


def test_so_as_unidades_aprovadas_contam_no_pedido(gui_arquivos, ctk_root, monkeypatch):
    monkeypatch.setattr("gui.historico_tab.messagebox.askyesno", lambda t, m: False)
    pedido = _criar_pedido(gui_arquivos, pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 10, "qtd_produzida": 0}])
    producao = _ordem_com_pecas(gui_arquivos, pedido, 6)
    tab = HistoricoTab(ctk_root, None, None, None)

    tab.salvar_estado_final_ordem(_fechar(producao, pedido, aprovadas=5, rejeitadas=1))

    assert PedidoService.obter_por_id(pedido["id"])["pecas"][0]["qtd_produzida"] == 5


def test_reabrir_e_guardar_nao_conta_duas_vezes(gui_arquivos, ctk_root, monkeypatch):
    monkeypatch.setattr("gui.historico_tab.messagebox.askyesno", lambda t, m: False)
    pedido = _criar_pedido(gui_arquivos, pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 10, "qtd_produzida": 0}])
    producao = _ordem_com_pecas(gui_arquivos, pedido, 6)
    tab = HistoricoTab(ctk_root, None, None, None)

    tab.salvar_estado_final_ordem(_fechar(producao, pedido, aprovadas=6, rejeitadas=0))
    reaberta = ProducaoService.obter_por_id(producao["id"])
    tab.salvar_estado_final_ordem(_fechar(reaberta, pedido, aprovadas=6, rejeitadas=0))
    assert PedidoService.obter_por_id(pedido["id"])["pecas"][0]["qtd_produzida"] == 6

    # corrigir para menos desconta a diferença
    reaberta = ProducaoService.obter_por_id(producao["id"])
    tab.salvar_estado_final_ordem(_fechar(reaberta, pedido, aprovadas=4, rejeitadas=2))
    assert PedidoService.obter_por_id(pedido["id"])["pecas"][0]["qtd_produzida"] == 4


def test_ordem_cancelada_nao_credita_pecas(gui_arquivos, ctk_root, monkeypatch):
    monkeypatch.setattr("gui.historico_tab.messagebox.askyesno", lambda t, m: False)
    pedido = _criar_pedido(gui_arquivos, pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 10, "qtd_produzida": 0}])
    producao = _ordem_com_pecas(gui_arquivos, pedido, 6)
    tab = HistoricoTab(ctk_root, None, None, None)

    tab.salvar_estado_final_ordem(_fechar(producao, pedido, aprovadas=6, rejeitadas=0, estado="Cancelada"))

    assert PedidoService.obter_por_id(pedido["id"])["pecas"][0]["qtd_produzida"] == 0


# ---------- Retrocompatibilidade: ordens fechadas por versões anteriores ----------

def test_reabrir_ordem_antiga_ja_concluida_nao_volta_a_contar(gui_arquivos, ctk_root, monkeypatch):
    """Ordem fechada por uma versão anterior (QA só conforme/não conforme, sem
    `pecas_creditadas`): o pedido já reflete esse fecho, por isso guardá-la de
    novo sem alterações não pode somar outra vez."""
    monkeypatch.setattr("gui.historico_tab.messagebox.askyesno", lambda t, m: False)
    pedido = _criar_pedido(gui_arquivos, pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 10, "qtd_produzida": 6}])
    chave = f"{pedido['id']}:P1:0"
    antiga = _criar_producao(gui_arquivos, pedidos_vinculados=[pedido["id"]])
    antiga.update({"estado": "Concluída", "qa_por_peca": {chave: {"conformidade": True}}})
    ProducaoService.atualizar_producao(antiga)
    tab = HistoricoTab(ctk_root, None, None, None)

    # O diálogo novo mostra planeado 4 (o que faltava) e grava as quantidades
    reaberta = ProducaoService.obter_por_id(antiga["id"])
    reaberta["qa_por_peca"] = {chave: {"qtd_planeada": 4, "qtd_aprovada": 4, "qtd_rejeitada": 0, "nc_codigo": "",
                                       "inspecao_visual": True, "controlo_dimensional": True, "conformidade": True}}
    tab.salvar_estado_final_ordem(reaberta)

    assert PedidoService.obter_por_id(pedido["id"])["pecas"][0]["qtd_produzida"] == 6
    assert ProducaoService.obter_por_id(antiga["id"])["pecas_creditadas"] == {chave: 4}
