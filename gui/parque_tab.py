import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from services.maquina_service import MaquinaService

class ParqueTab:
    def __init__(self, parent_frame, f_padrao, f_titulo):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo

        self.construir_layout()
        self.atualizar_tabela()

    def construir_layout(self):
        frm_layout = ctk.CTkFrame(self.parent)
        frm_layout.pack(fill="both", expand=True, padx=10, pady=10)

        frm_inv = ctk.CTkFrame(frm_layout, width=300)
        frm_inv.pack(side="left", fill="y", padx=10, pady=10)
        
        ctk.CTkLabel(frm_inv, text="Controle de Ativos i3D", font=self.f_titulo).pack(pady=10)
        self.ent_m_id = ctk.CTkEntry(frm_inv, placeholder_text="ID Único (Ex: X1C-4)", font=self.f_padrao)
        self.ent_m_id.pack(padx=10, pady=5, fill="x")
        self.ent_m_nome = ctk.CTkEntry(frm_inv, placeholder_text="Nome Descritivo", font=self.f_padrao)
        self.ent_m_nome.pack(padx=10, pady=5, fill="x")
        
        self.cmb_m_tech = ctk.CTkComboBox(frm_inv, values=["FDM", "SLA", "SLS"], font=self.f_padrao, state="readonly")
        self.cmb_m_tech.pack(padx=10, pady=5, fill="x")
        self.cmb_m_est = ctk.CTkComboBox(frm_inv, values=["Operacional", "Manutenção - Parado", "Desativado"], font=self.f_padrao, state="readonly")
        self.cmb_m_est.pack(padx=10, pady=5, fill="x")
        self.ent_m_notas = ctk.CTkEntry(frm_inv, placeholder_text="Notas / Manutenção", font=self.f_padrao)
        self.ent_m_notas.pack(padx=10, pady=5, fill="x")

        ctk.CTkButton(frm_inv, text="SALVAR MÁQUINA", fg_color="#1f538d", font=self.f_padrao, command=self.gravar).pack(padx=10, pady=15, fill="x")

        frm_grid = ctk.CTkFrame(frm_layout)
        frm_grid.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        cols = ("id", "nome", "tecnologia", "estado", "histórico_manutenção")
        self.tree_parque = ttk.Treeview(frm_grid, columns=cols, show="headings")
        for c in cols: self.tree_parque.heading(c, text=c.upper())
        self.tree_parque.pack(fill="both", expand=True)

        frm_act = ctk.CTkFrame(frm_grid)
        frm_act.pack(fill="x", pady=10)
        ctk.CTkButton(frm_act, text="Carregar para Edição", fg_color="#EAA115", text_color="black", font=self.f_padrao, command=self.carregar_edicao).pack(side="left", padx=10)
        ctk.CTkButton(frm_act, text="Remover Máquina", fg_color="#A12222", font=self.f_padrao, command=self.remover).pack(side="right", padx=10)

    def atualizar_tabela(self):
        for i in self.tree_parque.get_children(): self.tree_parque.delete(i)
        for m in MaquinaService.obter_todas():
            self.tree_parque.insert("", "end", values=(m.get("id"), m.get("nome"), m.get("tech"), m.get("estado"), m.get("manutencao")))

    def gravar(self):
        mid = self.ent_m_id.get().strip()
        nome = self.ent_m_nome.get().strip()
        if not mid or not nome: return
        
        MaquinaService.salvar_maquina(
            mid=mid, nome=nome, tech=self.cmb_m_tech.get(), 
            estado=self.cmb_m_est.get(), manutencao=self.ent_m_notas.get().strip()
        )
        
        self.ent_m_id.configure(state="normal")
        self.ent_m_id.delete(0, tk.END)
        self.ent_m_nome.delete(0, tk.END)
        self.ent_m_notas.delete(0, tk.END)
        self.atualizar_tabela()

    def carregar_edicao(self):
        sel = self.tree_parque.selection()
        if not sel: return
        mid = self.tree_parque.item(sel[0])['values'][0]
        
        for m in MaquinaService.obter_todas():
            if m.get("id") == mid:
                self.ent_m_id.delete(0, tk.END)
                self.ent_m_id.insert(0, m.get("id"))
                self.ent_m_id.configure(state="disabled")
                
                self.ent_m_nome.delete(0, tk.END)
                self.ent_m_nome.insert(0, m.get("nome"))
                
                self.cmb_m_tech.set(m.get("tech"))
                self.cmb_m_est.set(m.get("estado"))
                
                self.ent_m_notas.delete(0, tk.END)
                self.ent_m_notas.insert(0, m.get("manutencao"))
                break

    def remover(self):
        sel = self.tree_parque.selection()
        if not sel: return
        mid = self.tree_parque.item(sel[0])['values'][0]
        if messagebox.askyesno("Aviso", "Remover do parque?"):
            MaquinaService.remover_maquina(mid)
            self.atualizar_tabela()