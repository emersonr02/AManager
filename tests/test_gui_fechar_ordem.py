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
    linha["conformidade"].set(True)

    win.salvar()

    assert len(recebido) == 1
    salvo = recebido[0]
    assert salvo["estado"] == "Concluída"
    assert salvo["qa_por_peca"] == {
        f"{pedido['id']}:P1:0": {"inspecao_visual": True, "controlo_dimensional": True, "conformidade": True},
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
        chave: {"inspecao_visual": True, "controlo_dimensional": False, "conformidade": True},
    })
    win = JanelaFecharOrdem(ctk_root, log, lambda l: None)

    linha = win.linhas_qa[0]
    assert linha["visual"].get() is True
    assert linha["dimensional"].get() is False
    assert linha["conformidade"].get() is True
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

    assert "Limpar o bico" in win.lbl_acoes_nc.cget("text")
    win.destroy()
