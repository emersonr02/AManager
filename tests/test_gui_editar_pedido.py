import pytest

from services.pedido_service import PedidoService
from services.projeto_service import ProjetoService
from services.material_service import MaterialService
from gui.dialogs.editar_pedido import JanelaEditarPedido


@pytest.fixture
def avisos(monkeypatch, toasts):
    # A validação vive no formulário partilhado (novo_pedido.FormularioPedido);
    # o sucesso é um toast, não um messagebox.
    chamadas = {"error": [], "info": toasts}
    monkeypatch.setattr("gui.dialogs.novo_pedido.messagebox.showerror", lambda t, m: chamadas["error"].append(m))
    return chamadas


def _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais, **overrides):
    ProjetoService.criar_projeto("111", "Projeto Original")
    dados = dict(
        requerente_email="original@x.com",
        nr_projeto="111",
        nome_projeto="Projeto Original",
        tecnologia="FDM",
        data_entrega="2026-09-01",
        link_arquivos="link/original",
        observacoes="obs originais",
        pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 3, "qtd_produzida": 0}],
    )
    dados.update(overrides)
    return PedidoService.criar_pedido(**dados)


def test_preenche_campos_com_dados_existentes(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    assert win.ent_req.get() == "original@x.com"
    assert win.ent_data.get() == "2026-09-01"
    assert win.ent_link.get() == "link/original"
    assert win.txt_obs.get("1.0", "end").strip() == "obs originais"
    assert win.cmb_tech.get() == "FDM"
    assert win.cmb_proj.get() == "111 - Projeto Original"
    assert len(win.linhas_pecas) == 1
    assert win.linhas_pecas[0]["pn"].get() == "P1"
    assert win.linhas_pecas[0]["qtd"].get() == "3"
    win.destroy()


def test_preenche_multiplas_pecas_existentes(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais, pecas=[
        {"pn": "P1", "material": "PLA", "qtd_solicitada": 3, "qtd_produzida": 0},
        {"pn": "P2", "material": "ABS", "qtd_solicitada": 7, "qtd_produzida": 0},
    ])
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    assert len(win.linhas_pecas) == 2
    assert win.linhas_pecas[1]["pn"].get() == "P2"
    assert win.linhas_pecas[1]["qtd"].get() == "7"
    win.destroy()


def test_salvar_sem_requerente_bloqueia(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)
    win.ent_req.delete(0, "end")

    win.salvar_alteracoes()

    assert avisos["error"]
    assert PedidoService.obter_todos()[0]["requerente_email"] == "original@x.com"
    win.destroy()


def test_salvar_peca_com_quantidade_invalida_bloqueia(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)
    win.linhas_pecas[0]["qtd"].delete(0, "end")
    win.linhas_pecas[0]["qtd"].insert(0, "abc")

    win.salvar_alteracoes()

    assert avisos["error"]
    assert PedidoService.obter_todos()[0]["pecas"][0]["qtd_solicitada"] == 3
    win.destroy()


def test_salvar_altera_campos_e_persiste(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    win.ent_req.delete(0, "end")
    win.ent_req.insert(0, "novo@x.com")
    win.linhas_pecas[0]["qtd"].delete(0, "end")
    win.linhas_pecas[0]["qtd"].insert(0, "9")

    win.salvar_alteracoes()

    atualizado = PedidoService.obter_todos()[0]
    assert atualizado["requerente_email"] == "novo@x.com"
    assert atualizado["pecas"][0]["qtd_solicitada"] == 9
    assert atualizado["id"] == pedido["id"]  # continua o mesmo registo, não um novo
    assert avisos["info"]
    assert win.winfo_exists() == 0


def test_salvar_chama_callback_de_atualizacao(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    chamado = []
    win = JanelaEditarPedido(ctk_root, pedido, lambda: chamado.append(True))

    win.salvar_alteracoes()

    assert chamado == [True]


def test_adicionar_e_remover_linha_peca(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    win.adicionar_linha_peca()
    assert len(win.linhas_pecas) == 2

    win.remover_linha(win.linhas_pecas[0]["frame"])
    assert len(win.linhas_pecas) == 1
    win.destroy()


# ---------- Fase 0: mesma validação do Novo Pedido + preservar valores legados ----------

def test_salvar_com_data_invalida_bloqueia(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    # A edição gravava a data tal como escrita, sem validar o formato.
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)
    win.ent_data.delete(0, "end")
    win.ent_data.insert(0, "amanhã")

    win.salvar_alteracoes()

    assert avisos["error"]
    assert PedidoService.obter_todos()[0]["data_entrega"] == "2026-09-01"
    win.destroy()


def test_salvar_normaliza_data_dd_mm_aaaa(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)
    win.ent_data.delete(0, "end")
    win.ent_data.insert(0, "15/10/2026")

    win.salvar_alteracoes()

    assert PedidoService.obter_todos()[0]["data_entrega"] == "2026-10-15"


def test_salvar_pedido_legado_sem_tecnologia_obriga_a_escolher(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais, tecnologia="")
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    win.salvar_alteracoes()

    assert "tecnologia" in avisos["error"][0]
    win.destroy()


def test_projeto_fora_da_lista_e_mantido_em_vez_de_trocado(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    # Antes, um projeto desativado/renomeado era trocado em silêncio pelo
    # primeiro da lista — e gravar a edição alterava o projeto do pedido.
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    ProjetoService.criar_projeto("222", "Outro Projeto")
    ProjetoService.definir_ativo("111", False)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    assert win.cmb_proj.get() == "111 - Projeto Original"
    win.salvar_alteracoes()

    assert PedidoService.obter_todos()[0]["nr_projeto"] == "111"


def test_material_legado_fora_da_lista_e_mantido(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    # "PLA" não está registado em materiais.json — com o material obrigatório,
    # deixá-lo vazio impediria gravar qualquer outra alteração ao pedido.
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    assert win.linhas_pecas[0]["mat"].get() == "PLA"
    win.salvar_alteracoes()

    assert not avisos["error"]
    assert PedidoService.obter_todos()[0]["pecas"][0]["material"] == "PLA"


def test_botao_guardar_fica_no_rodape_fixo(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais)
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    assert _no_rodape_fixo(win, win.btn_salvar)
    win.destroy()


def _no_rodape_fixo(dialogo, botao):
    """O botão está dentro do rodapé fixo do Dialogo (empacotado com side=bottom,
    antes do corpo) — nunca é empurrado para fora da janela."""
    w = botao
    while w is not None and w is not dialogo.rodape:
        w = w.master
    return w is dialogo.rodape and dialogo.rodape.pack_info()["side"] == "bottom"


def test_editar_preserva_quantidade_ja_produzida(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    # Antes, guardar uma edição repunha qtd_produzida a 0 — agora que o fecho das
    # ordens a atualiza, tem de sobreviver às edições do pedido.
    pedido = _criar_pedido(gui_arquivos, arquivo_projetos, arquivo_materiais,
                           pecas=[{"pn": "P1", "material": "PLA", "qtd_solicitada": 3, "qtd_produzida": 3}])
    win = JanelaEditarPedido(ctk_root, pedido, lambda: None)

    win.salvar_alteracoes()

    assert PedidoService.obter_todos()[0]["pecas"][0]["qtd_produzida"] == 3
