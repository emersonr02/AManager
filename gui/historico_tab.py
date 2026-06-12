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

        # Configura o fundo cinza claro para destacar os blocos brancos
        self.parent.configure(fg_color="#f0f2f5")

        self.construir_layout()
        self.atualizar_tabela()

    def construir_layout(self):
        # 1. HEADER & FILTROS (No topo, integrados de forma limpa)
        frm_header = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(frm_header, text="Dashboard de Produção", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1f538d").pack(side="left")
        
        # Bloco de filtros rápido à direita do título
        frm_flt = ctk.CTkFrame(frm_header, fg_color="transparent")
        frm_flt.pack(side="right")
        
        ctk.CTkLabel(frm_flt, text="Projeto:", font=self.f_padrao, text_color="gray30").grid(row=0, column=0, padx=5)
        self.flt_p = ctk.CTkEntry(frm_flt, width=120, font=self.f_padrao, fg_color="white", border_width=1, border_color="gray80")
        self.flt_p.grid(row=0, column=1, padx=5)
        self.flt_p.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        ctk.CTkLabel(frm_flt, text="Material:", font=self.f_padrao, text_color="gray30").grid(row=0, column=2, padx=5)
        self.flt_m = ctk.CTkEntry(frm_flt, width=120, font=self.f_padrao, fg_color="white", border_width=1, border_color="gray80")
        self.flt_m.grid(row=0, column=3, padx=5)
        self.flt_m.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        # 2. CARDS DE KPI (Idênticos ao conceito do mockup do dashboard)
        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=20, pady=10)
        
        self.lbl_kpi_total = self.criar_card_kpi(frm_kpi, "Produções Concluídas", "0", "#1f538d")
        self.lbl_kpi_taxa = self.criar_card_kpi(frm_kpi, "Taxa de Sucesso", "0.0%", "#28a745")
        self.lbl_kpi_horas = self.criar_card_kpi(frm_kpi, "Total de Horas", "00:00", "#e0a800")

        # 3. CONTAINER DA TABELA (Bloco Branco com cantos arredondados)
        frm_conteudo = ctk.CTkFrame(self.parent, fg_color="white", corner_radius=10)
        frm_conteudo.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("id", "data", "projeto", "maquina", "material", "qnt", "tempo", "estado")
        self.tab_tree = ttk.Treeview(frm_conteudo, columns=cols, show="headings", style="Dashboard.Treeview")
        for c in cols: 
            self.tab_tree.heading(c, text=c.upper())
        
        self.tab_tree.column("id", width=50, anchor="center")
        self.tab_tree.column("data", width=100, anchor="center")
        self.tab_tree.column("maquina", width=90, anchor="center")
        self.tab_tree.column("qnt", width=70, anchor="center")
        self.tab_tree.column("tempo", width=80, anchor="center")
        self.tab_tree.column("estado", width=120, anchor="center")

        self.tab_tree.bind("<Double-1>", self.abrir_tratamento_ordem)

        sb = ttk.Scrollbar(frm_conteudo, orient="vertical", command=self.tab_tree.yview)
        self.tab_tree.configure(yscrollcommand=sb.set)
        sb.pack(fill="y", side="right", pady=10, padx=(0, 10))
        self.tab_tree.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        # 4. BARRA DE ACÇÕES INFERIOR
        frm_acoes = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes.pack(fill="x", padx=20, pady=(5, 15))
        
        ctk.CTkButton(frm_acoes, text="Clonar Ordem", fg_color="#EAA115", text_color="black", font=self.f_padrao, command=self.clonar_log).pack(side="left", padx=5)
        ctk.CTkButton(frm_acoes, text="Exportar Dados (CSV)", fg_color="#28a745", text_color="white", font=self.f_padrao, command=self.exportar_csv).pack(side="left", padx=5)
        ctk.CTkButton(frm_acoes, text="Apagar Registo", fg_color="#A12222", text_color="white", font=self.f_padrao, command=self.remover_log).pack(side="right", padx=5)

        self.configurar_estilo_tabela()

    def criar_card_kpi(self, parent, titulo, valor, cor_destaque):
        card = ctk.CTkFrame(parent, fg_color="white", corner_radius=10, height=100)
        card.pack(side="left", fill="x", expand=True, padx=5)
        card.pack_propagate(False)
        
        ctk.CTkLabel(card, text=titulo, text_color="gray50", font=self.f_padrao).pack(anchor="w", padx=15, pady=(15, 0))
        lbl_valor = ctk.CTkLabel(card, text=valor, text_color=cor_destaque, font=ctk.CTkFont(size=28, weight="bold"))
        lbl_valor.pack(anchor="w", padx=15, pady=5)
        return lbl_valor

    def configurar_estilo_tabela(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dashboard.Treeview", background="white", foreground="black", rowheight=28, fieldbackground="white", borderwidth=0)
        style.configure("Dashboard.Treeview.Heading", background="#f0f2f5", foreground="gray30", font=("Arial", 10, "bold"), borderwidth=0)
        style.map("Dashboard.Treeview", background=[("selected", "#1f538d")], foreground=[("selected", "white")])

    def atualizar_tabela(self):
        for i in self.tab_tree.get_children(): 
            self.tab_tree.delete(i)
        
        proj_q = self.flt_p.get().lower()
        mat_q = self.flt_m.get().lower()

        total_pecas = 0
        sucesso_pecas = 0
        total_horas = 0.0

        logs = JSONManager.carregar(ARQUIVO_LOGS)
        logs.sort(key=lambda x: int(x.get("id", 0)), reverse=True)

        for l in logs:
            proj_str = str(l.get("nr_projeto", "")).lower()
            mat_str = str(l.get("material", "")).lower()
            
            if (proj_q in proj_str) and (mat_q in mat_str):
                self.tab_tree.insert("", "end", values=(
                    l.get("id"), l.get("data_inicio", ""), l.get("nr_projeto", ""), l.get("id_maquina", ""), 
                    l.get("material", ""), l.get("quantidade", 0.0), l.get("hora_maquina", "00:00"), 
                    l.get("estado", "Em Andamento")
                ))
                
                total_pecas += 1
                if l.get("estado") == "Concluída": 
                    sucesso_pecas += 1
                total_horas += ProducaoService.converter_para_horas(l.get("hora_maquina", "00:00"))

        # Atualização em tempo real dos Cards do Dashboard
        taxa = (sucesso_pecas / total_pecas * 100) if total_pecas > 0 else 0.0
        
        self.lbl_kpi_total.configure(text=str(total_pecas))
        self.lbl_kpi_taxa.configure(text=f"{taxa:.1f}%")
        self.lbl_kpi_horas.configure(text=ProducaoService.converter_para_string(total_horas))

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