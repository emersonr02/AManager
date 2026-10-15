"""Retrocompatibilidade: a app tem de ler e trabalhar com os registos que as
versões anteriores deixaram nos ficheiros partilhados — sem migração prévia.

Os dados abaixo imitam esses formatos antigos (fictícios): ordens anteriores aos
pedidos (projeto/material na própria ordem, `id_maquina`, `hora_maquina`,
`responsavel`, `quantidade`, QA em campos soltos, estado "Falha"), ordens que
cobriam pedidos inteiros (sem `pecas_producao`, IDs de pedido gravados como
texto, QA por peça só com conforme / não conforme, sem `pecas_creditadas`) e
pedidos com quantidades em texto ou sem `qtd_produzida`.
"""
from datetime import datetime

import pytest

from database.json_manager import JSONManager
from gui.dialogs.fechar_ordem import JanelaFecharOrdem
from services.export_service import ExportService
from services.maquina_service import MaquinaService
from services.nc_service import NCService
from services.pdf_service import PDFService
from services.pedido_service import PedidoService
from services.producao_service import ProducaoService
from services.resumo_diario_service import ResumoDiarioService


@pytest.fixture
def dados_antigos(gui_arquivos, arquivos_nc):
    hoje = datetime.now().strftime("%Y-%m-%d")
    falhas_path, acoes_path = arquivos_nc
    JSONManager.salvar([{"tecnologia": "FDM", "cod": "COD001", "descricao": "Warping"}], falhas_path)
    JSONManager.salvar([{"codigos_aplicaveis": ["COD001"], "acao": "Aquecer a câmara"}], acoes_path)
    JSONManager.salvar([
        {"id": "X1-1", "nome": "Bambu Lab X1C #1", "modelo": "X1C", "tech": "FDM", "estado": "Operacional",
         "manutencao": "", "url_img": ""},
        {"id": "SLS-380", "nome": "3D Systems SLS 380", "modelo": "SLS 380", "tech": "SLS", "estado": "Operacional",
         "manutencao": "", "url_img": ""},
    ], gui_arquivos["maquinas"])
    JSONManager.salvar([
        {"id": 1, "requerente_email": "a@exemplo.pt", "nr_projeto": "100", "nome_projeto": "Suporte",
         "tecnologia": "FDM", "data_pedido": "2026-01-10", "data_entrega": "2026-02-01", "estado": "Em Andamento",
         "link_arquivos": "", "observacoes": "",
         "pecas": [{"pn": "A-1", "material": "PLA", "qtd_solicitada": 4},                         # sem qtd_produzida
                   {"pn": "A-2", "material": "PLA", "qtd_solicitada": "2", "qtd_produzida": "1"}],  # números em texto
         "producoes_vinculadas": [2, 3]},
        {"id": 2, "requerente_email": "b@exemplo.pt", "nr_projeto": "200", "nome_projeto": "Caixa",
         "tecnologia": "SLS", "data_entrega": "", "estado": "Pendente",
         "pecas": [{"pn": "B-1", "material": "PA12", "qtd_solicitada": 10, "qtd_produzida": 0}]},
    ], gui_arquivos["pedidos"])
    JSONManager.salvar([
        # Anterior aos pedidos: projeto e material na própria ordem
        {"id": 1, "data_inicio": "2025-03-10 09:00:00", "id_maquina": "X1-1", "hora_maquina": "1 day, 5:30:00",
         "responsavel": "op.antigo", "nr_projeto": "77", "material": "PETG", "quantidade": "120",
         "estado": "Falha", "erro": "Warping", "inspecao_visual": True, "controlo_dimensional": False,
         "conformidade_peca": False},
        # Fechada pela versão anterior: pedido inteiro, QA só conforme / não conforme
        {"id": 2, "data_inicio": f"{hoje} 08:00:00", "tecnologia": "FDM", "maquina": "Bambu Lab X1C #1",
         "tempo_estimado": "02:00", "pedidos_vinculados": ["1"], "operador": "op", "estado": "Concluída",
         "quantidade_consumida": 80, "tempo_real": "02:10", "quantidade_real": "85", "verificado_por": "qa",
         "data_fecho": f"{hoje} 10:30:00", "nc_codigo": "COD001", "acoes_aplicadas": [],
         "qa_por_peca": {"1:A-1:0": {"inspecao_visual": True, "controlo_dimensional": True, "conformidade": True},
                         "1:A-2:1": {"inspecao_visual": True, "controlo_dimensional": True, "conformidade": False}},
         "controlo_qualidade": {"inspecao_visual": True, "controlo_dimensional": True, "conformidade": False}},
        # Aberta pela versão anterior: cobre o pedido inteiro
        {"id": 3, "data_inicio": f"{hoje} 11:00:00", "tecnologia": "FDM", "maquina": "Bambu Lab X1C #1",
         "tempo_estimado": "1:30:00", "pedidos_vinculados": [1], "operador": "op", "estado": "A Imprimir",
         "quantidade_consumida": "40"},
        {"id": 4, "data_inicio": f"{hoje} 07:00:00", "tecnologia": "SLS", "maquina": "3D Systems SLS 380",
         "tempo_estimado": "10:00", "pedidos_vinculados": ["2"], "responsavel": "op", "estado": "Em Andamento",
         "altura_cuba": "5", "percentagem_po_novo": "30", "lote_po": "L-01"},
    ], gui_arquivos["producoes"])
    return gui_arquivos


def test_todos_os_ecras_abrem_com_dados_antigos(dados_antigos, app_sessao):
    for nome in ("painel", "ordens", "pedidos", "parque", "analytics", "manutencao", "configuracao", "producao"):
        app_sessao.selecionar_tela(nome)
        app_sessao.update_idletasks()

    ordens = app_sessao._uis["ordens"]
    ids = ordens.tab_tree.get_children()
    assert len(ids) == 4
    for item in ids:   # a linha de detalhe de cada ordem
        ordens.tab_tree.selection_set(item)
        ordens._mostrar_detalhe()
    app_sessao.selecionar_tela("painel")


def test_pecas_e_ncs_de_ordens_antigas(dados_antigos):
    ordens = {p["id"]: p for p in ProducaoService.obter_todos()}

    assert ProducaoService.pecas_da_producao(ordens[1]) == []
    # ordem antiga com o pedido inteiro: A-1 faltavam 4, A-2 faltava 1
    assert [(p["chave"], p["qtd"]) for p in ProducaoService.pecas_da_producao(ordens[3])] == [("1:A-1:0", 4), ("1:A-2:1", 1)]
    assert ProducaoService.ncs_da_producao(ordens[2]) == ["COD001"]
    # fecho antigo: peça conforme conta o planeado, não conforme conta 0
    assert ProducaoService.unidades_aprovadas(ordens[2]) == {"1:A-1:0": 4}
    assert ProducaoService.qtd_em_producao_por_peca() == {(1, 0): 4, (1, 1): 1, (2, 0): 10}

    for p in PedidoService.obter_todos():
        PedidoService.progresso(p)
        PedidoService.estado_sugerido(p)


def test_exportacoes_pdf_e_resumo_com_dados_antigos(dados_antigos, tmp_path):
    producoes = ProducaoService.obter_todos()
    pedidos = PedidoService.obter_todos()
    id_para_nome = MaquinaService.obter_lookup_id_nome()

    assert ExportService.exportar_historico_csv(str(tmp_path / "historico.csv"), producoes, pedidos)
    for p in producoes:
        vinculados = [x for x in pedidos if x["id"] in ProducaoService.ids_pedidos_vinculados(p)]
        PDFService.gerar_ordem_producao(p, vinculados, id_para_nome, str(tmp_path / f"ordem_{p['id']}.pdf"))
        assert (tmp_path / f"ordem_{p['id']}.pdf").stat().st_size > 0
    ResumoDiarioService.coletar()
    PDFService.gerar_resumo_diario(str(tmp_path / "resumo.pdf"))
    NCService.detectar_recorrencia("Bambu Lab X1C #1")


@pytest.mark.parametrize("id_ordem", [1, 2, 3, 4])
def test_fechar_ordem_antiga_abre_e_grava(dados_antigos, ctk_root, monkeypatch, id_ordem):
    monkeypatch.setattr("gui.dialogs.fechar_ordem.messagebox.showerror", lambda t, m: pytest.fail(m))
    monkeypatch.setattr("gui.dialogs.fechar_ordem.messagebox.askyesno", lambda t, m: True)
    log = ProducaoService.obter_por_id(id_ordem)
    recebido = []
    win = JanelaFecharOrdem(ctk_root, log, recebido.append)
    win.cmb_estado.set("Concluída")
    if id_ordem == 2:
        # A-2 vinha como não conforme: abre como rejeitada, com a NC da ordem
        assert win.linhas_qa[1]["ent_rejeitadas"].get() == "1"
        assert win.linhas_qa[1]["cmb_nc"].get().startswith("COD001")
    if not win.ent_qtd_real.get().strip():
        win.ent_qtd_real.insert(0, "10")

    win.salvar()

    assert recebido and recebido[0]["estado"] == "Concluída"


def test_editar_pedido_antigo_e_selecionar_pecas(dados_antigos, app_sessao, ctk_root):
    from gui.dialogs.editar_pedido import JanelaEditarPedido
    for pedido in PedidoService.obter_todos():
        JanelaEditarPedido(ctk_root, pedido, lambda: None).destroy()

    app_sessao.selecionar_tela("producao")
    tab = app_sessao._uis["producao"]
    tab.cmb_tech.set("FDM")
    tab.abrir_selecao_pecas()
    # A ordem antiga ainda aberta (#3) cobre o que faltava do pedido 1
    assert [(i["pn"], i["falta"]) for i in tab.dict_checks_pecas] == [("A-1", 0), ("A-2", 0)]
    tab.dialogo_selecao.destroy()
    app_sessao.selecionar_tela("painel")
