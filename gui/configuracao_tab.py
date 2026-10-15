"""Configuração — dados de referência num só sítio: Projetos, Materiais,
Templates de produção e o catálogo de Códigos NC / ações corretivas.

Antes, Projetos/Materiais estavam num botão dentro de Gestão de Pedidos, os
Templates só existiam dentro de Nova Produção e os Códigos NC não tinham UI."""
from tkinter import messagebox

import customtkinter as ctk

from services.nc_service import NCService
from services.template_service import TemplateService
from gui import theme
from gui.dialogs.gestao_projetos_materiais import GestaoProjetosMateriais


class ConfiguracaoTab:
    def __init__(self, parent_frame, f_padrao=None, f_titulo=None, master_app=None):
        self.parent = parent_frame
        self.master_app = master_app
        self.parent.configure(fg_color=theme.BG)

        theme.page_header(self.parent, "Dados de referência", "Configuração").pack(fill="x", padx=24, pady=(18, 8))

        self.tabview = theme.tabview(self.parent)
        self.tabview.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        tab_proj = self.tabview.add("Projetos")
        tab_mat = self.tabview.add("Materiais")
        self.tab_templates = self.tabview.add("Templates")
        self.tab_nc = self.tabview.add("Códigos NC")

        self.gestao = GestaoProjetosMateriais(tab_proj, tab_mat)
        self._construir_templates()
        self._construir_nc()
        self.atualizar()

    def atualizar(self):
        self.gestao.atualizar_lista_projetos()
        self.gestao.atualizar_lista_materiais()
        self.atualizar_templates()
        self.atualizar_nc()

    # ------------------------------------------------------------------ #
    #  TEMPLATES                                                           #
    # ------------------------------------------------------------------ #
    def _construir_templates(self):
        ctk.CTkLabel(self.tab_templates, text="Templates guardam os parâmetros de um job recorrente. "
                                              "Criam-se em Nova ordem → \"Guardar como template\".",
                     font=theme.font_body(12), text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", pady=(10, 6))
        frm_acoes = ctk.CTkFrame(self.tab_templates, fg_color="transparent")
        frm_acoes.pack(side="bottom", fill="x", pady=(6, 8))
        frm_tab, self.tree_templates = theme.tabela(self.tab_templates, [
            ("nome", "Nome", 260, "w"), ("tech", "Tecnologia", 100, "center", False),
            ("maquina", "Máquina", 200, "w"), ("tempo", "Tempo", 80, "center", False),
            ("usos", "Usos", 70, "center", False)])
        frm_tab.pack(fill="both", expand=True)
        btn_eliminar = theme.button_danger(frm_acoes, text="Eliminar template", width=150, command=self.eliminar_template)
        btn_eliminar.pack(side="left")
        self._sel_templates = theme.ligar_a_selecao(self.tree_templates, [btn_eliminar])

    def atualizar_templates(self):
        for i in self.tree_templates.get_children():
            self.tree_templates.delete(i)
        self._templates_por_item = {}
        for t in sorted(TemplateService.obter_todos(), key=lambda t: (t.get("tecnologia", ""), t.get("nome", ""))):
            item = self.tree_templates.insert("", "end", values=(
                t.get("nome", ""), t.get("tecnologia", ""), t.get("id_maquina", "") or "—",
                t.get("tempo_estimado", "") or "—", t.get("uso_count", 0)))
            self._templates_por_item[item] = t
        self._sel_templates()

    def eliminar_template(self):
        sel = self.tree_templates.selection()
        if not sel:
            return
        t = self._templates_por_item.get(sel[0])
        if t and messagebox.askyesno("Eliminar template", f"Eliminar o template \"{t.get('nome')}\"?"):
            TemplateService.remover_template(t.get("id"))
            self.atualizar_templates()
            theme.toast(self.parent, "Template eliminado.", "info")

    # ------------------------------------------------------------------ #
    #  CÓDIGOS NC                                                          #
    # ------------------------------------------------------------------ #
    def _construir_nc(self):
        ctk.CTkLabel(self.tab_nc, text="Catálogo de não-conformidades usado no fecho das ordens. Selecione um "
                                       "código para ver as ações corretivas sugeridas.",
                     font=theme.font_body(12), text_color=theme.TEXT_MUTED, anchor="w", justify="left").pack(fill="x", pady=(10, 6))
        self.lbl_acoes_nc = ctk.CTkLabel(self.tab_nc, text="", font=theme.font_body(12), text_color=theme.TEXT,
                                         anchor="w", justify="left", wraplength=800)
        self.lbl_acoes_nc.pack(side="bottom", fill="x", pady=(8, 8))
        frm_tab, self.tree_nc = theme.tabela(self.tab_nc, [
            ("cod", "Código", 100, "center", False), ("descricao", "Descrição", 380, "w"),
            ("tech", "Tecnologia", 110, "center", False)])
        frm_tab.pack(fill="both", expand=True)
        self.tree_nc.bind("<<TreeviewSelect>>", self._mostrar_acoes_nc, add="+")

    def atualizar_nc(self):
        for i in self.tree_nc.get_children():
            self.tree_nc.delete(i)
        for nc in NCService.obter_todos_codigos():
            self.tree_nc.insert("", "end", values=(nc.get("cod", ""), nc.get("descricao", ""), nc.get("tecnologia", "")))
        self.lbl_acoes_nc.configure(text="")

    def _mostrar_acoes_nc(self, event=None):
        sel = self.tree_nc.selection()
        if not sel:
            return
        cod = str(self.tree_nc.item(sel[0])["values"][0])
        acoes = NCService.obter_acoes_por_cod(cod)
        if acoes:
            texto = f"Ações corretivas para {cod}:\n" + "\n".join(f"•  {a.get('acao', a.get('act', ''))}" for a in acoes)
        else:
            texto = f"{cod} não tem ações corretivas associadas."
        self.lbl_acoes_nc.configure(text=texto)
