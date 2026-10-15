import pytest

from database.json_manager import JSONManager
from services.pedido_service import PedidoService
from services.producao_service import ProducaoService
from gui.dialogs.fechar_ordem import JanelaFecharOrdem


@pytest.fixture
def avisos(monkeypatch):
    chamadas = {"error": [], "askyesno": None}
    monkeypatch.setattr("gui.dialogs.fechar_ordem.messagebox.showerror", lambda t, m: chamadas["error"].append(m))
    monkeypatch.setattr("gui.dialogs.fechar_ordem.messagebox.askyesno", lambda t, m: chamadas["askyesno"])
    return chamadas


def _log_fdm(**overrides):
    dados = dict(
        id=1, tecnologia="FDM", maquina="X1C-1", tempo_estimado="02:00",
        pedidos_vinculados=[], operador="tester", estado="Em Andamento",
        quantidade_consumida=150.0,
    )
    dados.update(overrides)
    return dados


def test_extrai_quantidade_direta_para_fdm(gui_arquivos, arquivos_nc, ctk_root, avisos):
    log = _log_fdm()
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    assert win.qtd_raw == 150.0
    win.destroy()


def test_extrai_quantidade_calculada_para_sls(gui_arquivos, arquivos_nc, ctk_root, avisos):
    log = _log_fdm(tecnologia="SLS", altura_cuba="5.0", percentagem_po_novo="0.3")
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    esperado = ProducaoService.calcular_consumo_sls(5.0, 0.3)
    assert win.qtd_raw == esperado
    win.destroy()


def test_sls_aceita_percentagem_em_formato_inteiro(gui_arquivos, arquivos_nc, ctk_root, avisos):
    # Se o operador digitar "30" em vez de "0.3", o código ajusta para 0.3
    log = _log_fdm(tecnologia="SLS", altura_cuba="5.0", percentagem_po_novo="30")
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    esperado = ProducaoService.calcular_consumo_sls(5.0, 0.3)
    assert win.qtd_raw == esperado
    win.destroy()


def test_extrai_materiais_e_codigos_dos_pedidos_vinculados(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = PedidoService.criar_pedido(
        requerente_email="a@x.com", nr_projeto="1", nome_projeto="P", tecnologia="FDM",
        data_entrega="2026-09-01", link_arquivos="", observacoes="",
        pecas=[{"pn": "P1", "material": "PETG", "qtd_solicitada": 1, "qtd_produzida": 0}],
    )
    log = _log_fdm(pedidos_vinculados=[pedido["id"]])
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    assert win.material_fmt == "PETG"
    assert PedidoService.formatar_codigo(pedido["id"]) in win.pedidos_fmt
    win.destroy()


def test_sem_pedidos_vinculados_mostra_texto_generico(gui_arquivos, arquivos_nc, ctk_root, avisos):
    log = _log_fdm(pedidos_vinculados=[])
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    assert win.pedidos_fmt == "Nenhum vínculo direto"
    win.destroy()


def test_salvar_sem_tempo_real_bloqueia(gui_arquivos, arquivos_nc, ctk_root, avisos):
    log = _log_fdm()
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)
    win.ent_tempo_real.delete(0, "end")

    win.salvar()

    assert avisos["error"]
    win.destroy()


def _criar_pedido_com_pecas(pecas):
    return PedidoService.criar_pedido(
        requerente_email="a@x.com", nr_projeto="1", nome_projeto="P", tecnologia="FDM",
        data_entrega="2026-09-01", link_arquivos="", observacoes="", pecas=pecas,
    )


def test_sem_pecas_vinculadas_mostra_mensagem_e_nao_bloqueia(gui_arquivos, arquivos_nc, ctk_root, avisos):
    log = _log_fdm(estado="Em Andamento", pedidos_vinculados=[])
    recebido = []
    win = JanelaFecharOrdem(ctk_root, log, lambda l: recebido.append(l))
    win.cmb_estado.set("Concluída")

    assert win.linhas_qa == []
    win.salvar()

    # all([]) é True: sem peças para validar, a ordem fecha sem pedir confirmação
    assert avisos["askyesno"] is None
    assert recebido and recebido[0]["estado"] == "Concluída"


def test_concluir_com_peca_incompleta_pede_confirmacao(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _criar_pedido_com_pecas([{"pn": "P1", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}])
    log = _log_fdm(estado="Em Andamento", pedidos_vinculados=[pedido["id"]])
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)
    win.cmb_estado.set("Concluída")
    # a única linha de QA fica por marcar de propósito

    avisos["askyesno"] = False  # utilizador recusa concluir sem QA completo
    win.salvar()

    assert win.winfo_exists() == 1  # não fecha nem grava
    win.destroy()


def test_concluir_com_peca_incompleta_aceitando_aviso_grava_mesmo_assim(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _criar_pedido_com_pecas([{"pn": "P1", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}])
    log = _log_fdm(estado="Em Andamento", pedidos_vinculados=[pedido["id"]])
    recebido = []
    win = JanelaFecharOrdem(ctk_root, log, lambda l: recebido.append(l))
    win.cmb_estado.set("Concluída")

    avisos["askyesno"] = True  # utilizador confirma mesmo sem QA completo
    win.salvar()

    assert recebido and recebido[0]["estado"] == "Concluída"
    assert win.winfo_exists() == 0


def test_salvar_grava_qa_por_peca_quando_todas_completas(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _criar_pedido_com_pecas([{"pn": "P1", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}])
    log = _log_fdm(estado="Em Andamento", pedidos_vinculados=[pedido["id"]])
    recebido = []
    win = JanelaFecharOrdem(ctk_root, log, lambda l: recebido.append(l))
    win.cmb_estado.set("Concluída")
    linha = win.linhas_qa[0]
    linha["visual"].set(True)
    linha["dimensional"].set(True)

    win.salvar()

    assert len(recebido) == 1
    salvo = recebido[0]
    assert salvo["estado"] == "Concluída"
    # ordem antiga (sem pecas_producao): planeado = o que faltava do pedido (2)
    assert salvo["qa_por_peca"] == {
        f"{pedido['id']}:P1:0": {"qtd_planeada": 2, "qtd_aprovada": 2, "qtd_rejeitada": 0, "nc_codigo": "",
                                 "inspecao_visual": True, "controlo_dimensional": True, "conformidade": True},
    }
    assert salvo["nc_codigo"] == ""
    assert win.winfo_exists() == 0


def test_qa_por_peca_distingue_pns_repetidos_no_mesmo_pedido(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _criar_pedido_com_pecas([
        {"pn": "P1", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0},
        {"pn": "P1", "material": "ABS", "qtd_solicitada": 1, "qtd_produzida": 0},
    ])
    log = _log_fdm(pedidos_vinculados=[pedido["id"]])
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    assert len(win.linhas_qa) == 2
    assert win.linhas_qa[0]["chave"] != win.linhas_qa[1]["chave"]
    win.destroy()


def test_qa_gravada_anteriormente_e_reaberta_pre_preenchida(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _criar_pedido_com_pecas([{"pn": "P1", "material": "PLA", "qtd_solicitada": 1, "qtd_produzida": 0}])
    chave = f"{pedido['id']}:P1:0"
    log = _log_fdm(pedidos_vinculados=[pedido["id"]], qa_por_peca={
        chave: {"inspecao_visual": True, "controlo_dimensional": False, "qtd_aprovada": 0, "qtd_rejeitada": 1},
    })
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    linha = win.linhas_qa[0]
    assert linha["visual"].get() is True
    assert linha["dimensional"].get() is False
    assert linha["ent_aprovadas"].get() == "0"
    assert linha["ent_rejeitadas"].get() == "1"
    win.destroy()


def test_salvar_regista_codigo_nc_quando_selecionado(gui_arquivos, arquivos_nc, ctk_root, avisos):
    falhas_path, acoes_path = arquivos_nc
    JSONManager.salvar([{"tecnologia": "FDM", "cod": "COD001", "descricao": "Obstrução do bico"}], falhas_path)

    log = _log_fdm(estado="Em Andamento")
    recebido = []
    win = JanelaFecharOrdem(ctk_root, log, lambda l: recebido.append(l))
    win.cmb_nc.set("COD001 - Obstrução do bico")

    win.salvar()

    assert recebido[0]["nc_codigo"] == "COD001"


def test_on_nc_selecionada_mostra_acoes_corretivas_sugeridas(gui_arquivos, arquivos_nc, ctk_root, avisos):
    falhas_path, acoes_path = arquivos_nc
    JSONManager.salvar([{"tecnologia": "FDM", "cod": "COD001", "descricao": "Obstrução do bico"}], falhas_path)
    JSONManager.salvar([{"codigos_aplicaveis": ["COD001"], "acao": "Limpar o bico"}], acoes_path)

    log = _log_fdm()
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    win.on_nc_selecionada("COD001 - Obstrução do bico")

    checkboxes = win.frm_acoes_check.winfo_children()
    assert any(c.cget("text") == "Limpar o bico" for c in checkboxes)
    win.destroy()


# ---------- Resultado por peça: aprovadas, rejeitadas e NC da peça ----------

def _log_com_pecas(pedido, *quantidades):
    return _log_fdm(pedidos_vinculados=[pedido["id"]], pecas_producao=[
        {"pedido_id": pedido["id"], "indice": i, "pn": pedido["pecas"][i]["pn"],
         "material": pedido["pecas"][i]["material"], "qtd": q}
        for i, q in enumerate(quantidades)])


def _pedido_duas(material="PLA"):
    return _criar_pedido_com_pecas([
        {"pn": "BASE", "material": material, "qtd_solicitada": 10, "qtd_produzida": 0},
        {"pn": "TAMPA", "material": material, "qtd_solicitada": 4, "qtd_produzida": 0},
    ])


def test_mostra_so_as_pecas_da_ordem_com_quantidade_planeada(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _pedido_duas()
    log = _log_com_pecas(pedido, 6)   # só a BASE, 6 unidades
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    assert [(l["pn"], l["planeado"]) for l in win.linhas_qa] == [("BASE", 6)]
    assert win.linhas_qa[0]["ent_aprovadas"].get() == "6"
    win.destroy()


def test_rejeitadas_acertam_aprovadas(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _pedido_duas()
    win = JanelaFecharOrdem(ctk_root, _log_com_pecas(pedido, 6), lambda l: None)
    linha = win.linhas_qa[0]

    linha["ent_rejeitadas"].delete(0, "end")
    linha["ent_rejeitadas"].insert(0, "2")
    win._acertar_aprovadas(linha)

    assert linha["ent_aprovadas"].get() == "4"
    win.destroy()


def test_aprovadas_mais_rejeitadas_tem_de_dar_o_planeado(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _pedido_duas()
    recebido = []
    win = JanelaFecharOrdem(ctk_root, _log_com_pecas(pedido, 6), lambda l: recebido.append(l))
    win.cmb_estado.set("Concluída")
    linha = win.linhas_qa[0]
    linha["ent_aprovadas"].delete(0, "end")
    linha["ent_aprovadas"].insert(0, "3")   # 3 + 0 ≠ 6

    win.salvar()

    assert avisos["error"] and "tem de dar 6" in avisos["error"][0]
    assert recebido == []
    win.destroy()


def test_pecas_rejeitadas_exigem_nc_da_peca(gui_arquivos, arquivos_nc, ctk_root, avisos):
    falhas_path, _ = arquivos_nc
    JSONManager.salvar([{"tecnologia": "FDM", "cod": "COD003", "descricao": "Warping"}], falhas_path)
    pedido = _pedido_duas()
    recebido = []
    win = JanelaFecharOrdem(ctk_root, _log_com_pecas(pedido, 6, 4), lambda l: recebido.append(l))
    win.cmb_estado.set("Concluída")
    win.aprovar_todas()
    tampa = win.linhas_qa[1]
    tampa["ent_aprovadas"].delete(0, "end")
    tampa["ent_aprovadas"].insert(0, "3")
    tampa["ent_rejeitadas"].delete(0, "end")
    tampa["ent_rejeitadas"].insert(0, "1")

    win.salvar()
    assert avisos["error"] and "NC" in avisos["error"][0]

    # com a NC da peça indicada já grava — e só essa peça fica com NC
    tampa["cmb_nc"].set("COD003 - Warping")
    win.salvar()

    salvo = recebido[0]
    base_qa = salvo["qa_por_peca"][f"{pedido['id']}:BASE:0"]
    tampa_qa = salvo["qa_por_peca"][f"{pedido['id']}:TAMPA:1"]
    assert (base_qa["qtd_aprovada"], base_qa["qtd_rejeitada"], base_qa["nc_codigo"]) == (6, 0, "")
    assert (tampa_qa["qtd_aprovada"], tampa_qa["qtd_rejeitada"], tampa_qa["nc_codigo"]) == (3, 1, "COD003")
    assert salvo["nc_codigo"] == ""                                  # a ordem em si não falhou
    assert ProducaoService.ncs_da_producao(salvo) == ["COD003"]


def test_acoes_corretivas_incluem_os_codigos_das_pecas(gui_arquivos, arquivos_nc, ctk_root, avisos):
    falhas_path, acoes_path = arquivos_nc
    JSONManager.salvar([{"tecnologia": "FDM", "cod": "COD003", "descricao": "Warping"}], falhas_path)
    JSONManager.salvar([{"act": "ACT04", "codigos_aplicaveis": ["COD003"], "acao": "Aumentar temperatura"}], acoes_path)
    pedido = _pedido_duas()
    win = JanelaFecharOrdem(ctk_root, _log_com_pecas(pedido, 6), lambda l: None)

    win.linhas_qa[0]["cmb_nc"].set("COD003 - Warping")
    win.on_nc_selecionada(win.cmb_nc.get())

    assert any(c.cget("text") == "Aumentar temperatura" for c in win.frm_acoes_check.winfo_children())
    win.destroy()


# ---------- Retrocompatibilidade: ordens fechadas por versões anteriores ----------

def test_peca_nao_conforme_de_fecho_antigo_abre_como_rejeitada(gui_arquivos, arquivos_nc, ctk_root, avisos):
    falhas_path, _ = arquivos_nc
    JSONManager.salvar([{"tecnologia": "FDM", "cod": "COD001", "descricao": "Warping"}], falhas_path)
    pedido = _criar_pedido_com_pecas([{"pn": "P1", "material": "PLA", "qtd_solicitada": 3, "qtd_produzida": 0},
                                      {"pn": "P2", "material": "PLA", "qtd_solicitada": 2, "qtd_produzida": 0}])
    log = _log_fdm(estado="Concluída", nc_codigo="COD001", pedidos_vinculados=[pedido["id"]], qa_por_peca={
        f"{pedido['id']}:P1:0": {"inspecao_visual": True, "controlo_dimensional": True, "conformidade": False},
        f"{pedido['id']}:P2:1": {"inspecao_visual": True, "controlo_dimensional": True, "conformidade": True},
    })
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    p1, p2 = win.linhas_qa
    assert (p1["ent_aprovadas"].get(), p1["ent_rejeitadas"].get()) == ("0", "3")
    assert p1["cmb_nc"].get().startswith("COD001")
    assert (p2["ent_aprovadas"].get(), p2["ent_rejeitadas"].get()) == ("2", "0")
    win.destroy()


def test_fecho_de_ordem_antiga_grava_as_pecas_mostradas(gui_arquivos, arquivos_nc, ctk_root, avisos):
    pedido = _criar_pedido_com_pecas([{"pn": "P1", "material": "PLA", "qtd_solicitada": 5, "qtd_produzida": 2}])
    log = _log_fdm(estado="Em Andamento", pedidos_vinculados=[str(pedido["id"])])   # ID como texto
    recebido = []
    win = JanelaFecharOrdem(ctk_root, log, lambda l: recebido.append(l))
    win.cmb_estado.set("Concluída")
    win.aprovar_todas()

    win.salvar()

    assert recebido[0]["pecas_producao"] == [
        {"pedido_id": pedido["id"], "indice": 0, "pn": "P1", "material": "PLA", "qtd": 3}]


def test_ordem_muito_antiga_sem_pedidos_fecha_sem_pecas(gui_arquivos, arquivos_nc, ctk_root, avisos):
    # Antes dos pedidos, a ordem tinha projeto e material diretamente
    log = {"id": 1, "tecnologia": "FDM", "maquina": "X1C-1", "hora_maquina": "02:00", "responsavel": "antigo",
           "nr_projeto": "123", "material": "PLA", "estado": "Em Andamento", "quantidade_consumida": 50}
    recebido = []
    win = JanelaFecharOrdem(ctk_root, log, lambda l: recebido.append(l))
    win.cmb_estado.set("Concluída")

    win.salvar()

    assert win.linhas_qa == []
    assert recebido and recebido[0]["estado"] == "Concluída"
    assert "pecas_producao" not in recebido[0]
