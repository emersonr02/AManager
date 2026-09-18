import pytest

from services.maquina_service import MaquinaService
from services.pedido_service import PedidoService
from services.producao_service import ProducaoService
from gui.producao_tab import ProducaoTab


@pytest.fixture
def avisos(monkeypatch):
    """Substitui os popups modais por captura de chamadas — do contrário bloqueiam
    o teste à espera de um clique que nunca vem (sem mainloop nem utilizador)."""
    chamadas = {"warning": [], "info": [], "error": []}
    monkeypatch.setattr("gui.producao_tab.messagebox.showwarning", lambda titulo, msg: chamadas["warning"].append(msg))
    monkeypatch.setattr("gui.producao_tab.messagebox.showinfo", lambda titulo, msg: chamadas["info"].append(msg))
    monkeypatch.setattr("gui.producao_tab.messagebox.showerror", lambda titulo, msg: chamadas["error"].append(msg))
    return chamadas


def _criar_maquina(gui_arquivos, mid="M1", nome="Printer FDM 1", tech="FDM", estado="Operacional"):
    MaquinaService.salvar_maquina(mid=mid, nome=nome, tech=tech, estado=estado, manutencao="OK")


def _criar_pedido(gui_arquivos, tecnologia="FDM", pecas=None):
    return PedidoService.criar_pedido(
        requerente_email="a@x.com", nr_projeto="123", nome_projeto="Projeto A",
        tecnologia=tecnologia, data_entrega="2026-09-01", link_arquivos="", observacoes="",
        pecas=pecas if pecas is not None else [{"pn": "P1", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}],
    )


def _tab_fdm_pronta(gui_arquivos, ctk_root, avisos):
    """Cria uma ProducaoTab em FDM com máquina, pedido vinculado e tempo válidos —
    faltando só os campos específicos de segurança, consoante o teste."""
    _criar_maquina(gui_arquivos)
    pedido = _criar_pedido(gui_arquivos)

    tab = ProducaoTab(ctk_root, None, None)
    tab.pedidos_vinculados = [pedido["id"]]
    tab.ent_tempo.insert(0, "02:00")
    return tab, pedido


def test_mascara_tempo_formata_hhmm_automaticamente(gui_arquivos, ctk_root):
    tab = ProducaoTab(ctk_root, None, None)
    tab.ent_tempo.insert(0, "0230")

    tab.mascara_tempo(None, tab.ent_tempo)

    assert tab.ent_tempo.get() == "02:30"


def test_mascara_tempo_rejeita_caracteres_nao_numericos(gui_arquivos, ctk_root):
    tab = ProducaoTab(ctk_root, None, None)
    tab.ent_tempo.insert(0, "ab:cd")

    tab.mascara_tempo(None, tab.ent_tempo)

    assert tab.ent_tempo.get() == ""


def test_gravar_sem_pedido_vinculado_bloqueia(gui_arquivos, ctk_root, avisos):
    tab = ProducaoTab(ctk_root, None, None)
    tab.ent_tempo.insert(0, "02:00")

    tab.gravar_producao()

    assert avisos["warning"]
    assert ProducaoService.obter_todos() == []


def test_gravar_sem_tempo_valido_bloqueia(gui_arquivos, ctk_root, avisos):
    _criar_maquina(gui_arquivos)
    pedido = _criar_pedido(gui_arquivos)
    tab = ProducaoTab(ctk_root, None, None)
    tab.pedidos_vinculados = [pedido["id"]]

    tab.gravar_producao()

    assert avisos["warning"]
    assert ProducaoService.obter_todos() == []


def test_gravar_sem_maquina_valida_bloqueia(gui_arquivos, ctk_root, avisos):
    # Nenhuma máquina FDM cadastrada -> combobox fica em "Sem máquinas p/ FDM"
    pedido = _criar_pedido(gui_arquivos)
    tab = ProducaoTab(ctk_root, None, None)
    tab.pedidos_vinculados = [pedido["id"]]
    tab.ent_tempo.insert(0, "02:00")

    tab.gravar_producao()

    assert avisos["warning"]
    assert ProducaoService.obter_todos() == []


def test_fdm_bloqueia_sem_checklist_completa(gui_arquivos, ctk_root, avisos):
    tab, _ = _tab_fdm_pronta(gui_arquivos, ctk_root, avisos)
    tab.ent_quant.insert(0, "150")
    # Nenhum checkbox do checklist FDM marcado

    tab.gravar_producao()

    assert avisos["warning"]
    assert ProducaoService.obter_todos() == []


def test_fdm_bloqueia_quantidade_invalida(gui_arquivos, ctk_root, avisos):
    tab, _ = _tab_fdm_pronta(gui_arquivos, ctk_root, avisos)
    tab.ent_quant.insert(0, "-5")
    for var in tab.fdm_vars.values():
        var.set(True)

    tab.gravar_producao()

    assert avisos["warning"]
    assert ProducaoService.obter_todos() == []


def test_fdm_grava_producao_com_checklist_completa(gui_arquivos, ctk_root, avisos):
    tab, pedido = _tab_fdm_pronta(gui_arquivos, ctk_root, avisos)
    tab.ent_quant.insert(0, "150.5")
    for var in tab.fdm_vars.values():
        var.set(True)

    tab.gravar_producao()

    assert avisos["info"]  # mensagem de sucesso
    producoes = ProducaoService.obter_todos()
    assert len(producoes) == 1
    assert producoes[0]["tecnologia"] == "FDM"
    assert producoes[0]["quantidade_consumida"] == "150.5"
    assert producoes[0]["checklist_seguranca"] == {k: True for k in tab.fdm_vars}

    # O pedido vinculado deve refletir a produção no seu lado do link N:N
    pedido_atualizado = PedidoService.obter_todos()[0]
    assert producoes[0]["id"] in pedido_atualizado["producoes_vinculadas"]


def test_fdm_grava_reseta_formulario_para_nova_producao(gui_arquivos, ctk_root, avisos):
    tab, _ = _tab_fdm_pronta(gui_arquivos, ctk_root, avisos)
    tab.ent_quant.insert(0, "150.5")
    for var in tab.fdm_vars.values():
        var.set(True)

    tab.gravar_producao()

    assert tab.ent_tempo.get() == ""
    assert tab.ent_quant.get() == ""
    assert all(not var.get() for var in tab.fdm_vars.values())
    assert tab.pedidos_vinculados == []


def test_sls_bloqueia_sem_lote_po(gui_arquivos, ctk_root, avisos):
    _criar_maquina(gui_arquivos, mid="S1", nome="SLS 1", tech="SLS")
    pedido = _criar_pedido(gui_arquivos, tecnologia="SLS")
    tab = ProducaoTab(ctk_root, None, None)
    tab.ao_mudar_tecnologia("SLS")
    tab.pedidos_vinculados = [pedido["id"]]
    tab.ent_tempo.insert(0, "02:00")
    tab.ent_altura.insert(0, "470")
    tab.ent_perc.insert(0, "0.3")
    # ent_lote fica vazio de propósito
    for var in tab.sls_vars.values():
        var.set(True)

    tab.gravar_producao()

    assert avisos["warning"]
    assert ProducaoService.obter_todos() == []


def test_sls_grava_producao_completa(gui_arquivos, ctk_root, avisos):
    _criar_maquina(gui_arquivos, mid="S1", nome="SLS 1", tech="SLS")
    pedido = _criar_pedido(gui_arquivos, tecnologia="SLS")
    tab = ProducaoTab(ctk_root, None, None)
    tab.ao_mudar_tecnologia("SLS")
    tab.pedidos_vinculados = [pedido["id"]]
    tab.ent_tempo.insert(0, "02:00")
    tab.ent_altura.insert(0, "470")
    tab.ent_perc.insert(0, "0.3")
    tab.ent_lote.insert(0, "LOTE-XPTO")
    for var in tab.sls_vars.values():
        var.set(True)

    tab.gravar_producao()

    producoes = ProducaoService.obter_todos()
    assert len(producoes) == 1
    assert producoes[0]["lote_po"] == "LOTE-XPTO"
    assert producoes[0]["altura_cuba"] == "470"
    assert producoes[0]["percentagem_po_novo"] == "0.3"


def test_preencher_lote_anterior_reutiliza_ultimo_lote_sls(gui_arquivos, ctk_root):
    _criar_maquina(gui_arquivos, mid="S1", nome="SLS 1", tech="SLS")
    ProducaoService.criar_producao(
        tecnologia="SLS", maquina="SLS 1", tempo_estimado="01:00",
        pedidos_vinculados=[], operador="tester", campos_extra={"lote_po": "LOTE-ANTERIOR"},
    )

    tab = ProducaoTab(ctk_root, None, None)
    tab.ao_mudar_tecnologia("SLS")
    tab.chk_var_lote.set(True)

    tab.preencher_lote_anterior()

    assert tab.ent_lote.get() == "LOTE-ANTERIOR"


def test_ao_mudar_tecnologia_reseta_pedidos_vinculados(gui_arquivos, ctk_root):
    _criar_maquina(gui_arquivos)
    pedido = _criar_pedido(gui_arquivos)
    tab = ProducaoTab(ctk_root, None, None)
    tab.pedidos_vinculados = [pedido["id"]]

    tab.ao_mudar_tecnologia("SLA")

    assert tab.pedidos_vinculados == []
    assert tab.ent_pedidos_sel.get() == "Nenhum pedido selecionado"


def _abrir_popup_selecao(tab):
    tab.abrir_pop_up_selecao_pedidos()
    return tab.parent.winfo_toplevel().winfo_children()[-1]


def _checks_por_pn(tab):
    """Mapeia cada pedido do popup pelo seu PN (via o texto do checkbox), já que
    dict_checks_pedidos não guarda o PN diretamente."""
    return {item["id"]: item for item in tab.dict_checks_pedidos}


def test_popup_selecao_bloqueia_pedidos_com_material_incompativel(gui_arquivos, ctk_root, avisos):
    _criar_maquina(gui_arquivos)
    p_pla = _criar_pedido(gui_arquivos, pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}])
    p_abs = _criar_pedido(gui_arquivos, pecas=[{"pn": "B", "material": "ABS", "qtd_solicitada": 1, "qtd_produzida": 0}])
    tab = ProducaoTab(ctk_root, None, None)

    top = _abrir_popup_selecao(tab)
    checks = _checks_por_pn(tab)

    # Marcar o pedido de PLA deve bloquear o de ABS (materiais incompatíveis)
    checks[p_pla["id"]]["var"].set(True)
    checks[p_pla["id"]]["widget"].cget("command")()

    assert checks[p_abs["id"]]["widget"].cget("state") == "disabled"
    assert checks[p_abs["id"]]["var"].get() is False
    top.destroy()


def test_popup_selecao_desbloqueia_ao_desmarcar_tudo(gui_arquivos, ctk_root, avisos):
    _criar_maquina(gui_arquivos)
    p_pla = _criar_pedido(gui_arquivos, pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}])
    p_abs = _criar_pedido(gui_arquivos, pecas=[{"pn": "B", "material": "ABS", "qtd_solicitada": 1, "qtd_produzida": 0}])
    tab = ProducaoTab(ctk_root, None, None)

    top = _abrir_popup_selecao(tab)
    checks = _checks_por_pn(tab)
    checks[p_pla["id"]]["var"].set(True)
    checks[p_pla["id"]]["widget"].cget("command")()
    assert checks[p_abs["id"]]["widget"].cget("state") == "disabled"

    checks[p_pla["id"]]["var"].set(False)
    checks[p_pla["id"]]["widget"].cget("command")()

    assert checks[p_abs["id"]]["widget"].cget("state") == "normal"
    top.destroy()


def test_popup_selecao_permite_mesmo_material(gui_arquivos, ctk_root, avisos):
    _criar_maquina(gui_arquivos)
    p1 = _criar_pedido(gui_arquivos, pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}])
    p2 = _criar_pedido(gui_arquivos, pecas=[{"pn": "B", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}])
    tab = ProducaoTab(ctk_root, None, None)

    top = _abrir_popup_selecao(tab)
    checks = _checks_por_pn(tab)
    checks[p1["id"]]["var"].set(True)
    checks[p1["id"]]["widget"].cget("command")()

    assert checks[p2["id"]]["widget"].cget("state") == "normal"
    top.destroy()


def test_popup_sem_pedidos_compativeis_avisa_e_nao_abre(gui_arquivos, ctk_root, avisos):
    _criar_maquina(gui_arquivos)
    tab = ProducaoTab(ctk_root, None, None)
    antes = len(tab.parent.winfo_toplevel().winfo_children())

    tab.abrir_pop_up_selecao_pedidos()

    assert avisos["info"]
    assert len(tab.parent.winfo_toplevel().winfo_children()) == antes


def test_confirmar_selecao_atualiza_pedidos_vinculados_e_texto(gui_arquivos, ctk_root, avisos):
    _criar_maquina(gui_arquivos)
    pedido = _criar_pedido(gui_arquivos, pecas=[{"pn": "A", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}])
    tab = ProducaoTab(ctk_root, None, None)

    top = _abrir_popup_selecao(tab)
    checks = _checks_por_pn(tab)
    checks[pedido["id"]]["var"].set(True)
    checks[pedido["id"]]["widget"].cget("command")()

    botao_confirmar = [w for w in top.winfo_children() if type(w).__name__ == "CTkButton"][-1]
    botao_confirmar.cget("command")()

    assert tab.pedidos_vinculados == [pedido["id"]]
    assert PedidoService.formatar_codigo(pedido["id"]) in tab.ent_pedidos_sel.get()
    assert top.winfo_exists() == 0
