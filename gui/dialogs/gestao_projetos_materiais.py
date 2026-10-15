"""Gestão de Projetos e Materiais — componente embebido no ecrã Configuração.

Antes era uma janela à parte, aberta por um botão escondido em Gestão de
Pedidos; agora vive junto do resto da configuração (Templates, Códigos NC)."""
import re
from tkinter import messagebox

import customtkinter as ctk

from services.projeto_service import ProjetoService
from services.material_service import MaterialService
from gui import theme


class _JanelaEdicao(theme.Dialogo):
    """Diálogo genérico de edição com dois campos de texto."""

    def __init__(self, parent, titulo, campos, ao_guardar):
        # campos: [(rótulo, valor_inicial, mono)]
        self._ao_guardar = ao_guardar
        super().__init__(parent, titulo, largura=420, altura=300, scroll=False)
        self.entradas = []
        for rotulo, valor, mono in campos:
            theme.rotulo_campo(self.corpo, rotulo, True).pack(anchor="w", pady=(8, 2))
            ent = theme.entry(self.corpo, font=theme.font_mono(12) if mono else theme.font_body(13))
            ent.insert(0, valor)
            ent.pack(fill="x")
            self.entradas.append(ent)

    def confirmar(self):
        if self._ao_guardar([e.get().strip() for e in self.entradas]):
            self.destroy()


class GestaoProjetosMateriais:
    """Constrói as listas de Projetos e de Materiais dentro de `pai_projetos` e
    `pai_materiais` (normalmente dois separadores de um tabview)."""

    def __init__(self, pai_projetos, pai_materiais, callback_atualizar=None):
        self.tab_proj = pai_projetos
        self.tab_mat = pai_materiais
        self.callback_atualizar = callback_atualizar or (lambda: None)
        self.dialogo_edicao = None
        self.construir_tab_projetos()
        self.construir_tab_materiais()

    def destroy(self):
        for frm in (self.tab_proj, self.tab_mat):
            for w in frm.winfo_children():
                w.destroy()

    # ==========================================
    # PROJETOS
    # ==========================================
    def construir_tab_projetos(self):
        frm_form = ctk.CTkFrame(self.tab_proj, fg_color="transparent")
        frm_form.pack(fill="x", pady=(10, 6))
        self.ent_proj_id = theme.entry(frm_form, placeholder_text="Nº (6 dígitos)", width=150, font=theme.font_mono(12))
        self.ent_proj_id.pack(side="left", padx=(0, 10))
        self.ent_proj_nome = theme.entry(frm_form, placeholder_text="Nome do projeto", width=320)
        self.ent_proj_nome.pack(side="left", padx=(0, 10), fill="x", expand=True)
        theme.button_action(frm_form, text="Adicionar projeto", command=self.adicionar_projeto, width=150).pack(side="left")

        frm_acoes = ctk.CTkFrame(self.tab_proj, fg_color="transparent")
        frm_acoes.pack(side="bottom", fill="x", pady=(6, 8))
        frm_tab, self.tree_proj = theme.tabela(self.tab_proj, [
            ("id", "Nº", 100, "center", False), ("nome", "Nome", 360, "w"), ("estado", "Estado", 110, "w", False)])
        frm_tab.pack(fill="both", expand=True)
        self.tree_proj.bind("<Double-1>", self.editar_projeto_selecionado)

        btn_editar = theme.button_ghost(frm_acoes, text="Editar", width=100, command=self.editar_projeto_selecionado)
        btn_editar.pack(side="left", padx=(0, 10))
        btn_toggle = theme.button_secondary(frm_acoes, text="Ativar / desativar", width=150, command=self.toggle_ativo_projeto)
        btn_toggle.pack(side="left")
        self._sel_proj = theme.ligar_a_selecao(self.tree_proj, [btn_editar, btn_toggle])

        self.atualizar_lista_projetos()

    def atualizar_lista_projetos(self):
        for i in self.tree_proj.get_children():
            self.tree_proj.delete(i)
        for p in ProjetoService.obter_todos(incluir_inativos=True):
            estado = "Ativo" if p.get("ativo", True) else "Inativo"
            self.tree_proj.insert("", "end", tags=("tag_ok" if estado == "Ativo" else "tag_muted",),
                                  values=(p["id"], p["nome"], estado))
        self._sel_proj()

    def adicionar_projeto(self):
        id_val = self.ent_proj_id.get().strip()
        nome = self.ent_proj_nome.get().strip()
        if not id_val or not nome:
            messagebox.showwarning("Projeto incompleto", "Preencha o número e o nome do projeto.")
            return
        if not re.match(r"^\d{6}$", id_val):
            messagebox.showwarning("Número inválido", "O número do projeto tem de ter exatamente 6 algarismos.")
            return
        try:
            ProjetoService.criar_projeto(id_val, nome)
        except ValueError as e:
            messagebox.showerror("Não foi possível adicionar", str(e))
            return
        self.ent_proj_id.delete(0, "end")
        self.ent_proj_nome.delete(0, "end")
        self.atualizar_lista_projetos()
        theme.toast(self.tab_proj, f"Projeto {id_val} adicionado.")
        self.callback_atualizar()

    def editar_projeto_selecionado(self, event=None):
        sel = self.tree_proj.selection()
        if not sel:
            return
        id_atual, nome_atual, _ = self.tree_proj.item(sel[0])["values"]
        id_atual = str(id_atual)

        def _guardar(valores):
            novo_id, novo_nome = valores
            if not novo_id or not novo_nome:
                messagebox.showwarning("Projeto incompleto", "Preencha o número e o nome.")
                return False
            if not re.match(r"^\d{6}$", novo_id):
                messagebox.showwarning("Número inválido", "O número do projeto tem de ter exatamente 6 algarismos.")
                return False
            try:
                ProjetoService.atualizar_projeto(id_atual, novo_id, novo_nome)
            except ValueError as e:
                messagebox.showerror("Não foi possível guardar", str(e))
                return False
            self.atualizar_lista_projetos()
            self.callback_atualizar()
            return True

        self.dialogo_edicao = _JanelaEdicao(self.tab_proj.winfo_toplevel(), f"Editar projeto {id_atual}",
                                            [("Nº do projeto", id_atual, True), ("Nome", nome_atual, False)], _guardar)

    def toggle_ativo_projeto(self):
        sel = self.tree_proj.selection()
        if not sel:
            return
        id_val, _, estado_atual = self.tree_proj.item(sel[0])["values"]
        ProjetoService.definir_ativo(str(id_val), estado_atual != "Ativo")
        self.atualizar_lista_projetos()
        self.callback_atualizar()

    # ==========================================
    # MATERIAIS
    # ==========================================
    def construir_tab_materiais(self):
        frm_form = ctk.CTkFrame(self.tab_mat, fg_color="transparent")
        frm_form.pack(fill="x", pady=(10, 6))
        self.ent_mat_nome = theme.entry(frm_form, placeholder_text="Nome do material", width=240)
        self.ent_mat_nome.pack(side="left", padx=(0, 10))
        self.ent_mat_fab = theme.entry(frm_form, placeholder_text="Fabricante (opcional)", width=240)
        self.ent_mat_fab.pack(side="left", padx=(0, 10))
        theme.button_action(frm_form, text="Adicionar material", command=self.adicionar_material, width=150).pack(side="left")

        frm_acoes = ctk.CTkFrame(self.tab_mat, fg_color="transparent")
        frm_acoes.pack(side="bottom", fill="x", pady=(6, 8))
        frm_tab, self.tree_mat = theme.tabela(self.tab_mat, [
            ("nome", "Nome", 260, "w"), ("fabricante", "Fabricante", 240, "w"), ("estado", "Estado", 110, "w", False)])
        frm_tab.pack(fill="both", expand=True)
        self.tree_mat.bind("<Double-1>", self.editar_material_selecionado)

        btn_editar = theme.button_ghost(frm_acoes, text="Editar", width=100, command=self.editar_material_selecionado)
        btn_editar.pack(side="left", padx=(0, 10))
        btn_toggle = theme.button_secondary(frm_acoes, text="Ativar / desativar", width=150, command=self.toggle_ativo_material)
        btn_toggle.pack(side="left")
        self._sel_mat = theme.ligar_a_selecao(self.tree_mat, [btn_editar, btn_toggle])

        self.atualizar_lista_materiais()

    def atualizar_lista_materiais(self):
        for i in self.tree_mat.get_children():
            self.tree_mat.delete(i)
        for m in MaterialService.obter_todos(incluir_inativos=True):
            estado = "Ativo" if m.get("ativo", True) else "Inativo"
            self.tree_mat.insert("", "end", tags=("tag_ok" if estado == "Ativo" else "tag_muted",),
                                 values=(m["nome"], m["fabricante"], estado))
        self._sel_mat()

    def adicionar_material(self):
        nome = self.ent_mat_nome.get().strip()
        fab = self.ent_mat_fab.get().strip()
        if not nome:
            messagebox.showwarning("Material incompleto", "Preencha o nome do material.")
            return
        try:
            MaterialService.criar_material(nome, fab)
        except ValueError as e:
            messagebox.showerror("Não foi possível adicionar", str(e))
            return
        self.ent_mat_nome.delete(0, "end")
        self.ent_mat_fab.delete(0, "end")
        self.atualizar_lista_materiais()
        theme.toast(self.tab_mat, f"Material {nome} adicionado.")
        self.callback_atualizar()

    def editar_material_selecionado(self, event=None):
        sel = self.tree_mat.selection()
        if not sel:
            return
        nome_atual, fab_atual, _ = self.tree_mat.item(sel[0])["values"]
        nome_atual, fab_atual = str(nome_atual), str(fab_atual)

        def _guardar(valores):
            novo_nome, novo_fab = valores
            if not novo_nome:
                messagebox.showwarning("Material incompleto", "Preencha o nome do material.")
                return False
            try:
                MaterialService.atualizar_material(nome_atual, fab_atual, novo_nome, novo_fab)
            except ValueError as e:
                messagebox.showerror("Não foi possível guardar", str(e))
                return False
            self.atualizar_lista_materiais()
            self.callback_atualizar()
            return True

        self.dialogo_edicao = _JanelaEdicao(self.tab_mat.winfo_toplevel(), f"Editar material {nome_atual}",
                                            [("Nome", nome_atual, False), ("Fabricante", fab_atual, False)], _guardar)

    def toggle_ativo_material(self):
        sel = self.tree_mat.selection()
        if not sel:
            return
        nome_val, fab_val, estado_atual = self.tree_mat.item(sel[0])["values"]
        MaterialService.definir_ativo(str(nome_val), str(fab_val), estado_atual != "Ativo")
        self.atualizar_lista_materiais()
        self.callback_atualizar()
