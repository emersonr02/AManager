import pytest

from services.pedido_service import PedidoService
from services.projeto_service import ProjetoService
from services.material_service import MaterialService
from gui.dialogs.novo_pedido import JanelaNovoPedido, MODELO_EMAIL


@pytest.fixture
def avisos(monkeypatch):
    chamadas = {"error": [], "info": []}
    monkeypatch.setattr("gui.dialogs.novo_pedido.messagebox.showerror", lambda t, m: chamadas["error"].append(m))
    monkeypatch.setattr("gui.dialogs.novo_pedido.messagebox.showinfo", lambda t, m: chamadas["info"].append(m))
    return chamadas


@pytest.fixture
def janela(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    """JanelaNovoPedido lê ProjetoService/MaterialService já na construção — as
    fixtures de isolamento têm de estar ativas ANTES de instanciar, nunca só
    depois, sob pena de escrever/ler ficheiros de dados reais do projeto."""
    callback = []
    win = JanelaNovoPedido(ctk_root, lambda: callback.append(True))
    win.callback_chamado = callback
    yield win
    if win.winfo_exists():
        win.destroy()


def _preencher_minimo(win, pn="P1", mat=None, qtd="5"):
    win.cmb_req.set("cliente@x.com")
    win.ent_data.insert(0, "2026-10-01")
    win.cmb_proj.set(win.lista_projetos_fmt[0])
    linha = win.linhas_pecas[0]
    linha["pn"].insert(0, pn)
    if mat:
        linha["mat"].set(mat)
    linha["qtd"].insert(0, qtd)


def test_abre_com_uma_linha_de_peca_vazia_por_omissao(janela):
    assert len(janela.linhas_pecas) == 1


def test_adicionar_e_remover_linha_peca(janela):
    janela.adicionar_linha_peca()
    assert len(janela.linhas_pecas) == 2

    janela.remover_linha(janela.linhas_pecas[0]["frame"])
    assert len(janela.linhas_pecas) == 1


def test_salvar_sem_requerente_bloqueia(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    win = JanelaNovoPedido(ctk_root, lambda: None)
    win.ent_data.insert(0, "2026-10-01")

    win.salvar_pedido()

    assert avisos["error"]
    assert PedidoService.obter_todos() == []
    win.destroy()


def test_salvar_sem_projeto_valido_bloqueia(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    # Sem projetos registados -> combobox fica travado em "Sem projetos registados"
    win = JanelaNovoPedido(ctk_root, lambda: None)
    win.cmb_req.set("cliente@x.com")
    win.ent_data.insert(0, "2026-10-01")

    win.salvar_pedido()

    assert avisos["error"]
    assert PedidoService.obter_todos() == []
    win.destroy()


def test_salvar_sem_pecas_bloqueia(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    ProjetoService.criar_projeto("111", "Projeto Teste")
    win = JanelaNovoPedido(ctk_root, lambda: None)
    win.cmb_req.set("cliente@x.com")
    win.ent_data.insert(0, "2026-10-01")
    win.cmb_proj.set(win.lista_projetos_fmt[0])
    for linha in list(win.linhas_pecas):
        win.remover_linha(linha["frame"])

    win.salvar_pedido()

    assert avisos["error"]
    assert PedidoService.obter_todos() == []
    win.destroy()


def test_salvar_peca_sem_pn_bloqueia(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    ProjetoService.criar_projeto("111", "Projeto Teste")
    win = JanelaNovoPedido(ctk_root, lambda: None)
    win.cmb_req.set("cliente@x.com")
    win.ent_data.insert(0, "2026-10-01")
    win.cmb_proj.set(win.lista_projetos_fmt[0])
    win.linhas_pecas[0]["qtd"].insert(0, "5")  # sem PN

    win.salvar_pedido()

    assert avisos["error"]
    assert PedidoService.obter_todos() == []
    win.destroy()


def test_salvar_peca_com_quantidade_nao_positiva_bloqueia(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    ProjetoService.criar_projeto("111", "Projeto Teste")
    win = JanelaNovoPedido(ctk_root, lambda: None)
    win.cmb_req.set("cliente@x.com")
    win.ent_data.insert(0, "2026-10-01")
    win.cmb_proj.set(win.lista_projetos_fmt[0])
    win.linhas_pecas[0]["pn"].insert(0, "P1")
    win.linhas_pecas[0]["qtd"].insert(0, "0")

    win.salvar_pedido()

    assert avisos["error"]
    assert PedidoService.obter_todos() == []
    win.destroy()


def test_salvar_pedido_valido_cria_e_fecha_janela(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    ProjetoService.criar_projeto("111", "Projeto Teste")
    win = JanelaNovoPedido(ctk_root, lambda: None)
    _preencher_minimo(win)

    win.salvar_pedido()

    pedidos = PedidoService.obter_todos()
    assert len(pedidos) == 1
    assert pedidos[0]["requerente_email"] == "cliente@x.com"
    # Nota: o combobox de material começa vazio ("") até o utilizador o escolher
    # explicitamente — mesmo com lista_materiais_fmt == ["N/A"], não há auto-seleção.
    assert pedidos[0]["pecas"] == [{"pn": "P1", "material": "", "qtd_solicitada": 5, "qtd_produzida": 0}]
    assert avisos["info"]
    assert win.winfo_exists() == 0


def test_salvar_pedido_chama_callback_de_atualizacao(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    ProjetoService.criar_projeto("111", "Projeto Teste")
    chamado = []
    win = JanelaNovoPedido(ctk_root, lambda: chamado.append(True))
    _preencher_minimo(win)

    win.salvar_pedido()

    assert chamado == [True]


def test_salvar_projeto_sem_separador_usa_id_sem_nome(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    ProjetoService.criar_projeto("999", "")  # nome vazio -> lista_projetos_fmt == ["999"]
    win = JanelaNovoPedido(ctk_root, lambda: None)
    _preencher_minimo(win)

    win.salvar_pedido()

    pedido = PedidoService.obter_todos()[0]
    assert pedido["nr_projeto"] == "999"
    assert pedido["nome_projeto"] == ""


def test_processar_email_com_modelo_oficial_preenche_formulario(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    ProjetoService.criar_projeto("257147", "PPS AquaFountain")
    MaterialService.criar_material("PETG Preto", "")
    win = JanelaNovoPedido(ctk_root, lambda: None)

    # O próprio MODELO_EMAIL contém um exemplo completo — processá-lo é o teste
    # mais realista possível do parser (mantém-se em sincronia com docs/modelo_pedido_email.md).
    exemplo = MODELO_EMAIL.split("Exemplo:\n\n", 1)[1].split("\n\nNotas:")[0]
    win.processar_texto_email(exemplo)

    assert win.cmb_proj.get() == "257147 - PPS AquaFountain"
    assert win.cmb_tech.get() == "FDM"
    assert win.ent_data.get() == "2026-09-20"
    assert win.ent_link.get() == r"\\ceiia.com\PPS\AquaFountain"
    assert "Tolerância dimensional" in win.txt_obs.get("1.0", "end")

    assert len(win.linhas_pecas) == 2
    assert win.linhas_pecas[0]["pn"].get() == "AQF-001-Base"
    assert win.linhas_pecas[0]["mat"].get() == "PETG Preto"
    assert win.linhas_pecas[0]["qtd"].get() == "10"
    assert win.linhas_pecas[1]["pn"].get() == "AQF-002-Tampa"
    assert win.linhas_pecas[1]["qtd"].get() == "5"


def test_processar_email_requerente_nunca_e_preenchido_automaticamente(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    ProjetoService.criar_projeto("257147", "PPS AquaFountain")
    win = JanelaNovoPedido(ctk_root, lambda: None)
    win.cmb_req.set("alguem@x.com")

    exemplo = MODELO_EMAIL.split("Exemplo:\n\n", 1)[1].split("\n\nNotas:")[0]
    win.processar_texto_email(exemplo)

    # REQUERENTE é sempre manual, mesmo estando no texto do email
    assert win.cmb_req.get() == ""


def test_obter_requerentes_historico_devolve_emails_unicos_ordenados(gui_arquivos, arquivo_projetos, arquivo_materiais, ctk_root, avisos):
    PedidoService.criar_pedido(
        requerente_email="zeta@x.com", nr_projeto="1", nome_projeto="P", tecnologia="FDM",
        data_entrega="2026-09-01", link_arquivos="", observacoes="", pecas=[],
    )
    PedidoService.criar_pedido(
        requerente_email="alfa@x.com", nr_projeto="1", nome_projeto="P", tecnologia="FDM",
        data_entrega="2026-09-01", link_arquivos="", observacoes="", pecas=[],
    )
    win = JanelaNovoPedido(ctk_root, lambda: None)

    assert win.obter_requerentes_historico() == ["alfa@x.com", "zeta@x.com"]
