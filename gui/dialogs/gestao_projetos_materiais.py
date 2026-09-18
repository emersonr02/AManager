import re
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

from services.projeto_service import ProjetoService
from services.material_service import MaterialService
from gui import theme

_VARIANTE_ATIVO = {"Ativo": "ok", "Inativo": "neutral"}


class JanelaGestaoProjetosMateriais(ctk.CTkToplevel):
    def __init__(self, parent, callback_atualizar=None):
        super().__init__(parent)
        self.callback_atualizar = callback_atualizar or (lambda: None)

        self.title("Gestão de Projetos e Materiais")
        self.geometry("680x560")
        self.configure(fg_color=theme.BG)
        self.transient(parent)
        self.grab_set()

        self.tabview = ctk.CTkTabview(self, width=640, height=520,
                                       fg_color=theme.SURFACE, segmented_button_fg_color=theme.SURFACE_ALT,
                                       segmented_button_selected_color=theme.ACCENT, segmented_button_selected_hover_color=theme.ACCENT_HOVER,
                                       text_color=theme.TEXT)
        self.tabview.pack(padx=15, pady=15, fill="both", expand=True)
        self.tab_proj = self.tabview.add("Projetos")
        self.tab_mat = self.tabview.add("Materiais")

        self._estilo_treeview()
        self.construir_tab_projetos()
        self.construir_tab_materiais()

    def _estilo_treeview(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Gestao.Treeview", background=theme.SURFACE[0], foreground=theme.TEXT[0], rowheight=28, fieldbackground=theme.SURFACE[0], borderwidth=0)
        style.configure("Gestao.Treeview.Heading", background=theme.SURFACE_ALT[0], foreground=theme.TEXT_MUTED[0], borderwidth=0)
        style.map("Gestao.Treeview", background=[("selected", theme.ACCENT[0])], foreground=[("selected", "white")])
        # As tags são configuradas após a criação das trees, em _configurar_tags_trees()

    # ==========================================
    # PROJETOS
    # ==========================================
    def construir_tab_projetos(self):
        frm_form = ctk.CTkFrame(self.tab_proj, fg_color="transparent")
        frm_form.pack(fill="x", pady=(10, 5))

        self.ent_proj_id = theme.entry(frm_form, placeholder_text="ID (6 dígitos)", width=140, font=theme.font_mono(12))
        self.ent_proj_id.pack(side="left", padx=(0, 10))
        self.ent_proj_nome = theme.entry(frm_form, placeholder_text="Nome do Projeto", width=320)
        self.ent_proj_nome.pack(side="left", padx=(0, 10))
        theme.button_action(frm_form, text="Adicionar", command=self.adicionar_projeto, width=100).pack(side="left")

        cols = ("id", "nome", "estado")
        anchors = {"id": "center", "nome": "w", "estado": "w"}
        self.tree_proj = ttk.Treeview(self.tab_proj, columns=cols, show="headings", height=12, style="Gestao.Treeview")
        for c, h, w in [("id", "ID", 90), ("nome", "NOME", 340), ("estado", "ESTADO", 100)]:
            self.tree_proj.heading(c, text=h, anchor=anchors[c])
            self.tree_proj.column(c, width=w, anchor=anchors[c])
        self.tree_proj.pack(fill="both", expand=True, pady=10)
        self.tree_proj.bind("<Double-1>", self.editar_projeto_selecionado)
        self.tree_proj.tag_configure("tag_ok",      foreground=theme.SUCCESS[0])
        self.tree_proj.tag_configure("tag_neutral", foreground=theme.TEXT_MUTED[0])

        frm_acoes = ctk.CTkFrame(self.tab_proj, fg_color="transparent")
        frm_acoes.pack(fill="x", pady=(0, 10))
        theme.button_ghost(frm_acoes, text="Editar Selecionado", command=self.editar_projeto_selecionado).pack(side="left", padx=(0, 10))
        theme.button_danger(frm_acoes, text="Ativar / Desativar", command=self.toggle_ativo_projeto).pack(side="left")

        self.atualizar_lista_projetos()

    def atualizar_lista_projetos(self):
        for i in self.tree_proj.get_children():
            self.tree_proj.delete(i)
        for p in ProjetoService.obter_todos(incluir_inativos=True):
            estado = "Ativo" if p.get("ativo", True) else "Inativo"
            tag = "tag_ok" if estado == "Ativo" else "tag_neutral"
            self.tree_proj.insert("", "end", tags=(tag,), values=(p["id"], p["nome"], estado))

    def adicionar_projeto(self):
        id_val = self.ent_proj_id.get().strip()
        nome = self.ent_proj_nome.get().strip()
        if not id_val or not nome:
            messagebox.showwarning("Aviso", "Preencha o ID e o Nome do projeto.")
            return
        if not re.match(r"^\d{6}$", id_val):
            messagebox.showwarning("Aviso", "O ID do projeto CEiiA tem de conter estritamente 6 algarismos.")
            return

        try:
            ProjetoService.criar_projeto(id_val, nome)
        except ValueError as e:
            messagebox.showerror("Erro", str(e))
            return

        self.ent_proj_id.delete(0, tk.END)
        self.ent_proj_nome.delete(0, tk.END)
        self.atualizar_lista_projetos()
        self.callback_atualizar()

    def editar_projeto_selecionado(self, event=None):
        sel = self.tree_proj.selection()
        if not sel:
            return
        id_atual, nome_atual, _ = self.tree_proj.item(sel[0])['values']
        id_atual = str(id_atual)

        top = ctk.CTkToplevel(self)
        top.title(f"Editar Projeto {id_atual}")
        top.geometry("360x230")
        top.configure(fg_color=theme.BG)
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(top, text="ID", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack(pady=(15, 0))
        ent_id = theme.entry(top, width=260, font=theme.font_mono(12))
        ent_id.insert(0, id_atual)
        ent_id.pack(pady=5)

        ctk.CTkLabel(top, text="NOME", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack()
        ent_nome = theme.entry(top, width=260)
        ent_nome.insert(0, nome_atual)
        ent_nome.pack(pady=5)

        def guardar():
            novo_id = ent_id.get().strip()
            novo_nome = ent_nome.get().strip()
            if not novo_id or not novo_nome:
                messagebox.showwarning("Aviso", "Preencha o ID e o Nome.")
                return
            if not re.match(r"^\d{6}$", novo_id):
                messagebox.showwarning("Aviso", "O ID do projeto CEiiA tem de conter estritamente 6 algarismos.")
                return
            try:
                ProjetoService.atualizar_projeto(id_atual, novo_id, novo_nome)
            except ValueError as e:
                messagebox.showerror("Erro", str(e))
                return
            top.destroy()
            self.atualizar_lista_projetos()
            self.callback_atualizar()

        theme.button_primary(top, text="Guardar", command=guardar).pack(pady=15)

    def toggle_ativo_projeto(self):
        sel = self.tree_proj.selection()
        if not sel:
            return
        id_val, _, estado_atual = self.tree_proj.item(sel[0])['values']
        ProjetoService.definir_ativo(str(id_val), estado_atual != "Ativo")
        self.atualizar_lista_projetos()
        self.callback_atualizar()

    # ==========================================
    # MATERIAIS
    # ==========================================
    def construir_tab_materiais(self):
        frm_form = ctk.CTkFrame(self.tab_mat, fg_color="transparent")
        frm_form.pack(fill="x", pady=(10, 5))

        self.ent_mat_nome = theme.entry(frm_form, placeholder_text="Nome do Material", width=220)
        self.ent_mat_nome.pack(side="left", padx=(0, 10))
        self.ent_mat_fab = theme.entry(frm_form, placeholder_text="Fabricante (opcional)", width=220)
        self.ent_mat_fab.pack(side="left", padx=(0, 10))
        theme.button_action(frm_form, text="Adicionar", command=self.adicionar_material, width=100).pack(side="left")

        cols = ("nome", "fabricante", "estado")
        anchors = {"nome": "w", "fabricante": "w", "estado": "w"}
        self.tree_mat = ttk.Treeview(self.tab_mat, columns=cols, show="headings", height=12, style="Gestao.Treeview")
        for c, h, w in [("nome", "NOME", 220), ("fabricante", "FABRICANTE", 220), ("estado", "ESTADO", 100)]:
            self.tree_mat.heading(c, text=h, anchor=anchors[c])
            self.tree_mat.column(c, width=w, anchor=anchors[c])
        self.tree_mat.pack(fill="both", expand=True, pady=10)
        self.tree_mat.bind("<Double-1>", self.editar_material_selecionado)
        self.tree_mat.tag_configure("tag_ok",      foreground=theme.SUCCESS[0])
        self.tree_mat.tag_configure("tag_neutral", foreground=theme.TEXT_MUTED[0])

        frm_acoes = ctk.CTkFrame(self.tab_mat, fg_color="transparent")
        frm_acoes.pack(fill="x", pady=(0, 10))
        theme.button_ghost(frm_acoes, text="Editar Selecionado", command=self.editar_material_selecionado).pack(side="left", padx=(0, 10))
        theme.button_danger(frm_acoes, text="Ativar / Desativar", command=self.toggle_ativo_material).pack(side="left")

        self.atualizar_lista_materiais()

    def atualizar_lista_materiais(self):
        for i in self.tree_mat.get_children():
            self.tree_mat.delete(i)
        for m in MaterialService.obter_todos(incluir_inativos=True):
            estado = "Ativo" if m.get("ativo", True) else "Inativo"
            tag = "tag_ok" if estado == "Ativo" else "tag_neutral"
            self.tree_mat.insert("", "end", tags=(tag,), values=(m["nome"], m["fabricante"], estado))

    def adicionar_material(self):
        nome = self.ent_mat_nome.get().strip()
        fab = self.ent_mat_fab.get().strip()
        if not nome:
            messagebox.showwarning("Aviso", "Preencha o Nome do material.")
            return

        try:
            MaterialService.criar_material(nome, fab)
        except ValueError as e:
            messagebox.showerror("Erro", str(e))
            return

        self.ent_mat_nome.delete(0, tk.END)
        self.ent_mat_fab.delete(0, tk.END)
        self.atualizar_lista_materiais()
        self.callback_atualizar()

    def editar_material_selecionado(self, event=None):
        sel = self.tree_mat.selection()
        if not sel:
            return
        nome_atual, fab_atual, _ = self.tree_mat.item(sel[0])['values']

        top = ctk.CTkToplevel(self)
        top.title(f"Editar Material {nome_atual}")
        top.geometry("360x230")
        top.configure(fg_color=theme.BG)
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(top, text="NOME", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack(pady=(15, 0))
        ent_nome = theme.entry(top, width=260)
        ent_nome.insert(0, nome_atual)
        ent_nome.pack(pady=5)

        ctk.CTkLabel(top, text="FABRICANTE", font=theme.font_eyebrow(10), text_color=theme.TEXT_MUTED).pack()
        ent_fab = theme.entry(top, width=260)
        ent_fab.insert(0, fab_atual)
        ent_fab.pack(pady=5)

        def guardar():
            novo_nome = ent_nome.get().strip()
            novo_fab = ent_fab.get().strip()
            if not novo_nome:
                messagebox.showwarning("Aviso", "Preencha o Nome do material.")
                return
            try:
                MaterialService.atualizar_material(nome_atual, fab_atual, novo_nome, novo_fab)
            except ValueError as e:
                messagebox.showerror("Erro", str(e))
                return
            top.destroy()
            self.atualizar_lista_materiais()
            self.callback_atualizar()

        theme.button_primary(top, text="Guardar", command=guardar).pack(pady=15)

    def toggle_ativo_material(self):
        sel = self.tree_mat.selection()
        if not sel:
            return
        nome_val, fab_val, estado_atual = self.tree_mat.item(sel[0])['values']
        MaterialService.definir_ativo(str(nome_val), str(fab_val), estado_atual != "Ativo")
        self.atualizar_lista_materiais()
        self.callback_atualizar()
