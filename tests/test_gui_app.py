import pytest


def _esta_visivel(frame):
    """Um frame com grid_info() preenchido está colocado no layout (grid_forget()
    limpa-o); winfo_ismapped() não serve aqui porque a janela de teste está oculta."""
    return bool(frame.grid_info())


def test_arranca_no_painel(app_sessao):
    app_sessao.selecionar_tela("painel")
    assert _esta_visivel(app_sessao._frames["painel"])
    assert "pedidos" not in app_sessao._frames or not _esta_visivel(app_sessao._frames["pedidos"])


def test_selecionar_tela_pedidos_mostra_apenas_esse_frame(app_sessao):
    app_sessao.selecionar_tela("pedidos")

    assert _esta_visivel(app_sessao._frames["pedidos"])
    assert not _esta_visivel(app_sessao._frames["painel"])
    assert "producao" not in app_sessao._frames or not _esta_visivel(app_sessao._frames["producao"])
    assert "parque" not in app_sessao._frames or not _esta_visivel(app_sessao._frames["parque"])


def test_nova_ordem_nao_esta_na_navegacao_e_destaca_ordens(app_sessao):
    # "Nova ordem" é uma ação (botões em Painel/Ordens/Máquinas), não um ecrã da
    # navegação — quando está aberta, o item destacado é "Ordens de produção".
    assert "producao" not in app_sessao._botoes_nav

    app_sessao.abrir_nova_ordem()

    assert _esta_visivel(app_sessao._frames["producao"])
    assert app_sessao._btn_ativo is app_sessao._botoes_nav["ordens"]


def test_item_ativo_da_navegacao_distingue_se_do_fundo(app_sessao):
    # O ativo usava a mesma cor do fundo da sidebar e não se via qual estava selecionado.
    app_sessao.selecionar_tela("pedidos")
    ativo = app_sessao._botoes_nav["pedidos"].cget("fg_color")
    assert ativo not in ("transparent", app_sessao.sidebar_frame.cget("fg_color"))
    assert app_sessao._botoes_nav["ordens"].cget("fg_color") == "transparent"


@pytest.mark.parametrize("tela", ["painel", "ordens", "pedidos", "parque", "manutencao", "analytics", "configuracao"])
def test_todos_os_ecras_da_navegacao_abrem(app_sessao, tela):
    app_sessao.selecionar_tela(tela)
    assert _esta_visivel(app_sessao._frames[tela])


def test_abrir_nova_ordem_pre_seleciona_maquina(app_sessao, gui_arquivos):
    from services.maquina_service import MaquinaService
    MaquinaService.salvar_maquina(mid="S1", nome="SLS Um", tech="SLS", estado="Operacional", manutencao="OK")

    app_sessao.abrir_nova_ordem("SLS", "SLS Um")

    ui = app_sessao._uis["producao"]
    assert ui.cmb_tech.get() == "SLS"
    assert ui.cmb_maq.get() == "SLS Um"


def test_pasta_dados_acessivel_confirma_escrita_real(app_sessao, tmp_path, monkeypatch):
    from gui import app as app_module

    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    assert app_sessao._pasta_dados_acessivel() is True

    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path / "nao_existe"))
    assert app_sessao._pasta_dados_acessivel() is False


def test_voltar_ao_painel_refresca_manutencao_atrasada(app_sessao, gui_arquivos):
    # Concluir uma tarefa no separador Manutenção tem de refletir-se no Painel
    # quando se volta a ele (antes o cartão só era calculado na construção).
    from datetime import datetime, timedelta
    from database.json_manager import JSONManager
    from services.maquina_service import MaquinaService
    from services.manutencao_service import ManutencaoService

    MaquinaService.salvar_maquina(mid="M1", nome="Printer 1", tech="FDM", estado="Operacional",
                                  manutencao="OK", modelo="Modelo X")
    tarefa = ManutencaoService.criar_tarefa(modelo="Modelo X", nome="Limpeza", frequencia_dias=10)
    JSONManager.salvar([{
        "id": 1, "tarefa_id": tarefa["id"], "maquina_id": "M1", "operador": "a", "notas": "",
        "data_realizacao": (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
    }], gui_arquivos["manutencoes"])

    app_sessao.selecionar_tela("painel")
    painel = app_sessao._uis["painel"]
    assert any(etiqueta == "Manutenção" for _, etiqueta, _, _ in painel.itens_atencao)

    ManutencaoService.registar_conclusao(tarefa["id"], "M1", "operador")
    app_sessao.selecionar_tela("manutencao")
    app_sessao.selecionar_tela("painel")

    assert not any(etiqueta == "Manutenção" for _, etiqueta, _, _ in painel.itens_atencao)
