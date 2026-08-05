import re
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox

from services.projeto_service import ProjetoService
from services.material_service import MaterialService


class JanelaGestaoProjetosMateriais(ctk.CTkToplevel):
    def __init__(self, parent, callback_atualizar=None):
        super().__init__(parent)
        self.callback_atualizar = callback_atualizar or (lambda: None)

        self.title("Gestão de Projetos e Materiais")
        self.geometry("680x560")
        self.transient(parent)
        self.grab_set()

        self.tabview = ctk.CTkTabview(self, width=640, height=520)
        self.tabview.pack(padx=15, pady=15, fill="both", expand=True)
        self.tab_proj = self.tabview.add("Projetos")
        self.tab_mat = self.tabview.add("Materiais")

        self.construir_tab_projetos()
        self.construir_tab_materiais()

    # ==========================================
    # PROJETOS
    # ==========================================
    def construir_tab_projetos(self):
        frm_form = ctk.CTkFrame(self.tab_proj, fg_color="transparent")
        frm_form.pack(fill="x", pady=(10, 5))

        self.ent_proj_id = ctk.CTkEntry(frm_form, placeholder_text="ID (6 dígitos)", width=140)
        self.ent_proj_id.pack(side="left", padx=(0, 10))
        self.ent_proj_nome = ctk.CTkEntry(frm_form, placeholder_text="Nome do Projeto", width=320)
        self.ent_proj_nome.pack(side="left", padx=(0, 10))
        ctk.CTkButton(frm_form, text="Adicionar", command=self.adicionar_projeto, width=100).pack(side="left")

        cols = ("id", "nome", "estado")
        self.tree_proj = ttk.Treeview(self.tab_proj, columns=cols, show="headings", height=12)
        for c, h, w in [("id", "ID", 90), ("nome", "NOME", 340), ("estado", "ESTADO", 100)]:
            self.tree_proj.heading(c, text=h)
            self.tree_proj.column(c, width=w, anchor="w" if c == "nome" else "center")
        self.tree_proj.pack(fill="both", expand=True, pady=10)
        self.tree_proj.bind("<Double-1>", self.editar_projeto_selecionado)

        frm_acoes = ctk.CTkFrame(self.tab_proj, fg_color="transparent")
        frm_acoes.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(frm_acoes, text="Editar Selecionado", command=self.editar_projeto_selecionado).pack(side="left", padx=(0, 10))
        ctk.CTkButton(frm_acoes, text="Ativar / Desativar", fg_color="#dc3545", hover_color="#c82333", command=self.toggle_ativo_projeto).pack(side="left")

        self.atualizar_lista_projetos()

    def atualizar_lista_projetos(self):
        for i in self.tree_proj.get_children():
            self.tree_proj.delete(i)
        for p in ProjetoService.obter_todos(incluir_inativos=True):
            estado = "Ativo" if p.get("ativo", True) else "Inativo"
            self.tree_proj.insert("", "end", values=(p["id"], p["nome"], estado))

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
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(top, text="ID:").pack(pady=(15, 0))
        ent_id = ctk.CTkEntry(top, width=260)
        ent_id.insert(0, id_atual)
        ent_id.pack(pady=5)

        ctk.CTkLabel(top, text="Nome:").pack()
        ent_nome = ctk.CTkEntry(top, width=260)
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

        ctk.CTkButton(top, text="Guardar", command=guardar).pack(pady=15)

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

        self.ent_mat_nome = ctk.CTkEntry(frm_form, placeholder_text="Nome do Material", width=220)
        self.ent_mat_nome.pack(side="left", padx=(0, 10))
        self.ent_mat_fab = ctk.CTkEntry(frm_form, placeholder_text="Fabricante (opcional)", width=220)
        self.ent_mat_fab.pack(side="left", padx=(0, 10))
        ctk.CTkButton(frm_form, text="Adicionar", command=self.adicionar_material, width=100).pack(side="left")

        cols = ("nome", "fabricante", "estado")
        self.tree_mat = ttk.Treeview(self.tab_mat, columns=cols, show="headings", height=12)
        for c, h, w in [("nome", "NOME", 220), ("fabricante", "FABRICANTE", 220), ("estado", "ESTADO", 100)]:
            self.tree_mat.heading(c, text=h)
            self.tree_mat.column(c, width=w, anchor="w" if c != "estado" else "center")
        self.tree_mat.pack(fill="both", expand=True, pady=10)
        self.tree_mat.bind("<Double-1>", self.editar_material_selecionado)

        frm_acoes = ctk.CTkFrame(self.tab_mat, fg_color="transparent")
        frm_acoes.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(frm_acoes, text="Editar Selecionado", command=self.editar_material_selecionado).pack(side="left", padx=(0, 10))
        ctk.CTkButton(frm_acoes, text="Ativar / Desativar", fg_color="#dc3545", hover_color="#c82333", command=self.toggle_ativo_material).pack(side="left")

        self.atualizar_lista_materiais()

    def atualizar_lista_materiais(self):
        for i in self.tree_mat.get_children():
            self.tree_mat.delete(i)
        for m in MaterialService.obter_todos(incluir_inativos=True):
            estado = "Ativo" if m.get("ativo", True) else "Inativo"
            self.tree_mat.insert("", "end", values=(m["nome"], m["fabricante"], estado))

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
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(top, text="Nome:").pack(pady=(15, 0))
        ent_nome = ctk.CTkEntry(top, width=260)
        ent_nome.insert(0, nome_atual)
        ent_nome.pack(pady=5)

        ctk.CTkLabel(top, text="Fabricante:").pack()
        ent_fab = ctk.CTkEntry(top, width=260)
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

        ctk.CTkButton(top, text="Guardar", command=guardar).pack(pady=15)

    def toggle_ativo_material(self):
        sel = self.tree_mat.selection()
        if not sel:
            return
        nome_val, fab_val, estado_atual = self.tree_mat.item(sel[0])['values']
        MaterialService.definir_ativo(str(nome_val), str(fab_val), estado_atual != "Ativo")
        self.atualizar_lista_materiais()
        self.callback_atualizar()
