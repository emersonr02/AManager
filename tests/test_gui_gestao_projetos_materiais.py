import pytest

from services.projeto_service import ProjetoService
from services.material_service import MaterialService
from gui.dialogs.gestao_projetos_materiais import JanelaGestaoProjetosMateriais


@pytest.fixture
def avisos(monkeypatch):
    chamadas = {"warning": [], "error": []}
    monkeypatch.setattr("gui.dialogs.gestao_projetos_materiais.messagebox.showwarning", lambda t, m: chamadas["warning"].append(m))
    monkeypatch.setattr("gui.dialogs.gestao_projetos_materiais.messagebox.showerror", lambda t, m: chamadas["error"].append(m))
    return chamadas


def _linhas(tree):
    return [tree.item(i)["values"] for i in tree.get_children()]


def _encontrar_widgets(container, classe):
    encontrados = []
    for child in container.winfo_children():
        if type(child).__name__ == classe:
            encontrados.append(child)
        encontrados.extend(_encontrar_widgets(child, classe))
    return encontrados


# ---------- Projetos ----------

def test_lista_projetos_mostra_ativos_e_inativos(arquivo_projetos, ctk_root, avisos):
    ProjetoService.criar_projeto("111111", "Ativo")
    ProjetoService.criar_projeto("222222", "Inativo")
    ProjetoService.definir_ativo("222222", False)

    win = JanelaGestaoProjetosMateriais(ctk_root)

    # Nota: o Treeview do Tk devolve valores puramente numéricos como int, não str
    # (conversão automática do Tcl ao fazer round-trip) — daí comparar por campo.
    linhas = {(str(l[0]), l[1]): l[2] for l in _linhas(win.tree_proj)}
    assert linhas[("111111", "Ativo")] == "Ativo"
    assert linhas[("222222", "Inativo")] == "Inativo"
    win.destroy()


def test_adicionar_projeto_sem_dados_bloqueia(arquivo_projetos, ctk_root, avisos):
    win = JanelaGestaoProjetosMateriais(ctk_root)

    win.adicionar_projeto()

    assert avisos["warning"]
    assert ProjetoService.obter_todos() == []
    win.destroy()


def test_adicionar_projeto_id_com_formato_invalido_bloqueia(arquivo_projetos, ctk_root, avisos):
    win = JanelaGestaoProjetosMateriais(ctk_root)
    win.ent_proj_id.insert(0, "12AB")
    win.ent_proj_nome.insert(0, "Projeto X")

    win.adicionar_projeto()

    assert avisos["warning"]
    assert ProjetoService.obter_todos() == []
    win.destroy()


def test_adicionar_projeto_duplicado_mostra_erro(arquivo_projetos, ctk_root, avisos):
    ProjetoService.criar_projeto("111111", "Original")
    win = JanelaGestaoProjetosMateriais(ctk_root)
    win.ent_proj_id.insert(0, "111111")
    win.ent_proj_nome.insert(0, "Duplicado")

    win.adicionar_projeto()

    assert avisos["error"]
    assert len(ProjetoService.obter_todos()) == 1
    win.destroy()


def test_adicionar_projeto_valido_persiste_limpa_campos_e_chama_callback(arquivo_projetos, ctk_root, avisos):
    chamado = []
    win = JanelaGestaoProjetosMateriais(ctk_root, lambda: chamado.append(True))
    win.ent_proj_id.insert(0, "111111")
    win.ent_proj_nome.insert(0, "Projeto Novo")

    win.adicionar_projeto()

    assert ProjetoService.obter_todos() == [{"id": "111111", "nome": "Projeto Novo", "ativo": True}]
    assert win.ent_proj_id.get() == ""
    assert win.ent_proj_nome.get() == ""
    assert chamado == [True]
    win.destroy()


def test_toggle_ativo_projeto_desativa_e_reativa(arquivo_projetos, ctk_root, avisos):
    ProjetoService.criar_projeto("111111", "Projeto A")
    win = JanelaGestaoProjetosMateriais(ctk_root)
    win.tree_proj.selection_set(win.tree_proj.get_children()[0])

    win.toggle_ativo_projeto()
    assert ProjetoService.obter_todos() == []  # inativo, filtrado por omissão
    assert ProjetoService.obter_todos(incluir_inativos=True)[0]["ativo"] is False

    win.tree_proj.selection_set(win.tree_proj.get_children()[0])
    win.toggle_ativo_projeto()
    assert len(ProjetoService.obter_todos()) == 1
    win.destroy()


def test_editar_projeto_guarda_alteracoes(arquivo_projetos, ctk_root, avisos):
    ProjetoService.criar_projeto("111111", "Nome Antigo")
    win = JanelaGestaoProjetosMateriais(ctk_root)
    win.tree_proj.selection_set(win.tree_proj.get_children()[0])

    win.editar_projeto_selecionado()
    top = win.winfo_children()[-1]
    entradas = _encontrar_widgets(top, "CTkEntry")
    botao = _encontrar_widgets(top, "CTkButton")[0]
    ent_id, ent_nome = entradas[0], entradas[1]

    ent_nome.delete(0, "end")
    ent_nome.insert(0, "Nome Novo")
    botao.cget("command")()

    assert ProjetoService.obter_todos()[0]["nome"] == "Nome Novo"
    assert top.winfo_exists() == 0
    win.destroy()


# ---------- Materiais ----------

def test_lista_materiais_mostra_ativos_e_inativos(arquivo_materiais, ctk_root, avisos):
    MaterialService.criar_material("PLA", "Generic")
    MaterialService.criar_material("ABS", "Generic")
    MaterialService.definir_ativo("ABS", "Generic", False)

    win = JanelaGestaoProjetosMateriais(ctk_root)

    linhas = {(l[0], l[1]): l[2] for l in _linhas(win.tree_mat)}
    assert linhas[("PLA", "Generic")] == "Ativo"
    assert linhas[("ABS", "Generic")] == "Inativo"
    win.destroy()


def test_adicionar_material_sem_nome_bloqueia(arquivo_materiais, ctk_root, avisos):
    win = JanelaGestaoProjetosMateriais(ctk_root)

    win.adicionar_material()

    assert avisos["warning"]
    assert MaterialService.obter_todos() == []
    win.destroy()


def test_adicionar_material_duplicado_mostra_erro(arquivo_materiais, ctk_root, avisos):
    MaterialService.criar_material("PLA", "Generic")
    win = JanelaGestaoProjetosMateriais(ctk_root)
    win.ent_mat_nome.insert(0, "PLA")
    win.ent_mat_fab.insert(0, "Generic")

    win.adicionar_material()

    assert avisos["error"]
    assert len(MaterialService.obter_todos()) == 1
    win.destroy()


def test_adicionar_material_valido_persiste_e_chama_callback(arquivo_materiais, ctk_root, avisos):
    chamado = []
    win = JanelaGestaoProjetosMateriais(ctk_root, lambda: chamado.append(True))
    win.ent_mat_nome.insert(0, "TPU")
    win.ent_mat_fab.insert(0, "Recreus")

    win.adicionar_material()

    assert MaterialService.obter_todos() == [{"nome": "TPU", "fabricante": "Recreus", "ativo": True}]
    assert chamado == [True]
    win.destroy()


def test_toggle_ativo_material_desativa_e_reativa(arquivo_materiais, ctk_root, avisos):
    MaterialService.criar_material("PLA", "Generic")
    win = JanelaGestaoProjetosMateriais(ctk_root)
    win.tree_mat.selection_set(win.tree_mat.get_children()[0])

    win.toggle_ativo_material()
    assert MaterialService.obter_todos() == []
    assert MaterialService.obter_todos(incluir_inativos=True)[0]["ativo"] is False
    win.destroy()


def test_editar_material_guarda_alteracoes(arquivo_materiais, ctk_root, avisos):
    MaterialService.criar_material("PLA", "Generic")
    win = JanelaGestaoProjetosMateriais(ctk_root)
    win.tree_mat.selection_set(win.tree_mat.get_children()[0])

    win.editar_material_selecionado()
    top = win.winfo_children()[-1]
    entradas = _encontrar_widgets(top, "CTkEntry")
    botao = _encontrar_widgets(top, "CTkButton")[0]
    ent_nome, ent_fab = entradas[0], entradas[1]

    ent_nome.delete(0, "end")
    ent_nome.insert(0, "PLA+")
    botao.cget("command")()

    assert MaterialService.obter_todos()[0]["nome"] == "PLA+"
    assert top.winfo_exists() == 0
    win.destroy()


def test_callback_omitido_nao_rebenta(arquivo_projetos, ctk_root, avisos):
    # callback_atualizar é opcional (default lambda: None) — não deve rebentar sem ele
    win = JanelaGestaoProjetosMateriais(ctk_root)
    win.ent_proj_id.insert(0, "111111")
    win.ent_proj_nome.insert(0, "Projeto")

    win.adicionar_projeto()

    assert len(ProjetoService.obter_todos()) == 1
    win.destroy()
