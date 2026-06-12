from datetime import datetime
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config.paths import ARQUIVO_LOGS
from database.json_manager import JSONManager
from services.producao_service import ProducaoService
from services.export_service import ExportService
from gui.dialogs.fechar_ordem import JanelaFecharOrdem

class HistoricoTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.master_app = master_app

        self.construir_layout()
        self.atualizar_tabela()

    def construir_layout(self):
        frm_flt = ctk.CTkFrame(self.parent)
        frm_flt.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frm_flt, text="Projeto:", font=self.f_padrao).grid(row=0, column=0, padx=5, pady=5)
        self.flt_p = ctk.CTkEntry(frm_flt, width=120, font=self.f_padrao)
        self.flt_p.grid(row=0, column=1, padx=5, pady=5)
        self.flt_p.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        ctk.CTkLabel(frm_flt, text="Material:", font=self.f_padrao).grid(row=0, column=2, padx=5, pady=5)
        self.flt_m = ctk.CTkEntry(frm_flt, width=120, font=self.f_padrao)
        self.flt_m.grid(row=0, column=3, padx=5, pady=5)
        self.flt_m.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        self.frm_dash = ctk.CTkFrame(self.parent, fg_color="#2b2b2b")
        self.frm_dash.pack(fill="x", padx=10, pady=5)
        self.lbl_stats = ctk.CTkLabel(self.frm_dash, text="A carregar dados...", font=self.f_titulo)
        self.lbl_stats.pack(pady=5)

        frm_tab = ctk.CTkFrame(self.parent)
        frm_tab.pack(fill="both", expand=True, padx=10, pady=5)
        
        cols = ("id", "data", "projeto", "maquina", "material", "qnt", "tempo", "estado")
        self.tab_tree = ttk.Treeview(frm_tab, columns=cols, show="headings")
        for c in cols: self.tab_tree.heading(c, text=c.upper())
        self.tab_tree.column("id", width=30, anchor="center")
        self.tab_tree.column("qnt", width=60, anchor="center")
        self.tab_tree.column("tempo", width=70, anchor="center")
        self.tab_tree.pack(fill="both", expand=True, side="left")

        self.tab_tree.bind("<Double-1>", self.abrir_tratamento_ordem)

        sb = ttk.Scrollbar(frm_tab, orient="vertical", command=self.tab_tree.yview)
        self.tab_tree.configure(yscrollcommand=sb.set)
        sb.pack(fill="y", side="right")

        frm_acoes = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(frm_acoes, text="Clonar Ordem Selecionada", fg_color="#EAA115", text_color="black", font=self.f_padrao, command=self.clonar_log).pack(side="left", padx=5)
        ctk.CTkButton(frm_acoes, text="Exportar Dados (CSV)", fg_color="#28a745", font=self.f_padrao, command=self.exportar_csv).pack(side="left", padx=5)
        ctk.CTkButton(frm_acoes, text="Apagar Registro", fg_color="#A12222", font=self.f_padrao, command=self.remover_log).pack(side="right", padx=5)

    def atualizar_tabela(self):
        for i in self.tab_tree.get_children(): self.tab_tree.delete(i)
        
        proj_q = self.flt_p.get().lower()
        mat_q = self.flt_m.get().lower()

        total_pecas = 0
        sucesso_pecas = 0
        total_horas = 0.0

        logs = JSONManager.carregar(ARQUIVO_LOGS)
        logs.sort(key=lambda x: int(x.get("id", 0)), reverse=True)

        for l in logs:
            if (proj_q in str(l.get("nr_projeto", "")).lower()) and (mat_q in str(l.get("material", "")).lower()):
                self.tab_tree.insert("", "end", values=(
                    l.get("id"), l.get("data_inicio", ""), l.get("nr_projeto", ""), l.get("id_maquina", ""), 
                    l.get("material", ""), l.get("quantidade", 0.0), l.get("hora_maquina", "00:00"), 
                    l.get("estado", "Em Andamento")
                ))
                
                total_pecas += 1
                if l.get("estado") == "Concluída": sucesso_pecas += 1
                total_horas += ProducaoService.converter_para_horas(l.get("hora_maquina", "00:00"))

        taxa = (sucesso_pecas / total_pecas * 100) if total_pecas > 0 else 0
        self.lbl_stats.configure(text=f"Visível: {total_pecas} Peças | Sucesso: {taxa:.1f}% | Horas de Carga: {ProducaoService.converter_para_string(total_horas)}")

    def exportar_csv(self):
        caminho_salvar = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not caminho_salvar: return

        linhas = self.tab_tree.get_children()
        consumo_materiais = {}
        horas_maquinas = {}
        dados_principais = []

        for i in linhas:
            val = self.tab_tree.item(i)['values']
            dados_principais.append(val)
            maq, mat = val[3], val[4]
            try: qnt = float(val[5])
            except ValueError: qnt = 0.0
            horas = ProducaoService.converter_para_horas(str(val[6]))

            consumo_materiais[mat] = consumo_materiais.get(mat, 0.0) + qnt
            horas_maquinas[maq] = horas_maquinas.get(maq, 0.0) + horas

        if ExportService.exportar_historico_csv(caminho_salvar, dados_principais, consumo_materiais, horas_maquinas):
            messagebox.showinfo("Sucesso", "Exportação analítica concluída.")
        else:
            messagebox.showerror("Erro", "Falha ao salvar CSV.")

    def clonar_log(self):
        sel = self.tab_tree.selection()
        if not sel: return
        id_reg = self.tab_tree.item(sel[0])['values'][0]
        
        logs = JSONManager.carregar(ARQUIVO_LOGS)
        for log in logs:
            if log.get("id") == id_reg:
                novo_log = log.copy()
                novo_log["id"] = max([l.get("id", 0) for l in logs]) + 1
                novo_log["data_inicio"] = datetime.now().strftime("%Y-%m-%d")
                novo_log["estado"] = "Em Andamento"
                novo_log["erro"] = ""
                
                logs.append(novo_log)
                JSONManager.salvar(logs, ARQUIVO_LOGS)
                self.atualizar_tabela()
                messagebox.showinfo("Clonado", "Nova impressão registada com base na anterior.")
                break

    def abrir_tratamento_ordem(self, event=None):
        sel = self.tab_tree.selection()
        if not sel: return
        id_reg = self.tab_tree.item(sel[0])['values'][0]
        for log in JSONManager.carregar(ARQUIVO_LOGS):
            if log.get("id") == id_reg:
                JanelaFecharOrdem(self.master_app, log, self.salvar_estado_final_ordem)
                break

    def salvar_estado_final_ordem(self, log_atualizado):
        logs = JSONManager.carregar(ARQUIVO_LOGS)
        for idx, log in enumerate(logs):
            if log.get("id") == log_atualizado["id"]:
                logs[idx] = log_atualizado
                break
        JSONManager.salvar(logs, ARQUIVO_LOGS)
        self.atualizar_tabela()

    def remover_log(self):
        sel = self.tab_tree.selection()
        if not sel: return
        id_reg = self.tab_tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Aviso", "Remover do histórico local permanentemente?"):
            logs = [l for l in JSONManager.carregar(ARQUIVO_LOGS) if l.get("id") != id_reg]
            JSONManager.salvar(logs, ARQUIVO_LOGS)
            self.atualizar_tabela()