def _esta_visivel(frame):
    """Um frame com grid_info() preenchido está colocado no layout (grid_forget()
    limpa-o); winfo_ismapped() não serve aqui porque a janela de teste está oculta."""
    return bool(frame.grid_info())


def test_arranca_no_dashboard(app_sessao):
    app_sessao.selecionar_tela("dash")
    assert _esta_visivel(app_sessao._frames["dash"])
    assert "pedidos" not in app_sessao._frames or not _esta_visivel(app_sessao._frames["pedidos"])


def test_selecionar_tela_pedidos_mostra_apenas_esse_frame(app_sessao):
    app_sessao.selecionar_tela("pedidos")

    assert _esta_visivel(app_sessao._frames["pedidos"])
    assert not _esta_visivel(app_sessao._frames["dash"])
    assert "producao" not in app_sessao._frames or not _esta_visivel(app_sessao._frames["producao"])
    assert "parque" not in app_sessao._frames or not _esta_visivel(app_sessao._frames["parque"])


def test_selecionar_tela_producao_destaca_botao_acao(app_sessao):
    app_sessao.selecionar_tela("producao")

    assert _esta_visivel(app_sessao._frames["producao"])
    assert app_sessao.btn_producao.cget("fg_color") != app_sessao.btn_dash.cget("fg_color")


def test_selecionar_tela_manutencao_mostra_apenas_esse_frame(app_sessao):
    app_sessao.selecionar_tela("manutencao")

    assert _esta_visivel(app_sessao._frames["manutencao"])
    assert not _esta_visivel(app_sessao._frames["dash"])
    assert not _esta_visivel(app_sessao._frames["pedidos"])
    assert "producao" not in app_sessao._frames or not _esta_visivel(app_sessao._frames["producao"])


def test_pasta_dados_acessivel_confirma_escrita_real(app_sessao, tmp_path, monkeypatch):
    from gui import app as app_module

    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    assert app_sessao._pasta_dados_acessivel() is True

    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path / "nao_existe"))
    assert app_sessao._pasta_dados_acessivel() is False
