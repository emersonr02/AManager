from datetime import datetime
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os

from config.paths import ARQUIVO_LOGS, ARQUIVO_PEDIDOS
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

        self.parent.configure(fg_color="#f0f2f5")

        self.construir_layout()
        self.carregar_combos_filtro()
        self.atualizar_tabela()

    def construir_layout(self):
        # 1. HEADER & TÍTULO
        frm_header = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_header.pack(fill="x", padx=20, pady=(20, 5))
        ctk.CTkLabel(frm_header, text="Dashboard de Produção", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1f538d").pack(side="left")
        
        # 2. PAINEL DE FILTROS AVANÇADOS
        frm_flt = ctk.CTkFrame(self.parent, fg_color="white", corner_radius=8, border_width=1, border_color="#e0e0e0")
        frm_flt.pack(fill="x", padx=20, pady=5)
        
        # Linha 1 de Filtros
        ctk.CTkLabel(frm_flt, text="Data Início:", font=self.f_padrao, text_color="gray40").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.flt_data_ini = ctk.CTkEntry(frm_flt, width=120, placeholder_text="YYYY-MM-DD", font=self.f_padrao, fg_color="#f0f2f5", text_color="black")
        self.flt_data_ini.grid(row=0, column=1, padx=5, pady=10)
        self.flt_data_ini.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        ctk.CTkLabel(frm_flt, text="Data Fim:", font=self.f_padrao, text_color="gray40").grid(row=0, column=2, padx=10, pady=10, sticky="e")
        self.flt_data_fim = ctk.CTkEntry(frm_flt, width=120, placeholder_text="YYYY-MM-DD", font=self.f_padrao, fg_color="#f0f2f5", text_color="black")
        self.flt_data_fim.grid(row=0, column=3, padx=5, pady=10)
        self.flt_data_fim.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        ctk.CTkLabel(frm_flt, text="Máquina:", font=self.f_padrao, text_color="gray40").grid(row=0, column=4, padx=10, pady=10, sticky="e")
        self.flt_maq = ctk.CTkComboBox(frm_flt, values=["Todas"], width=140, font=self.f_padrao, fg_color="#f0f2f5", text_color="black", command=lambda e: self.atualizar_tabela())
        self.flt_maq.grid(row=0, column=5, padx=5, pady=10)

        ctk.CTkLabel(frm_flt, text="Estado:", font=self.f_padrao, text_color="gray40").grid(row=0, column=6, padx=10, pady=10, sticky="e")
        self.flt_estado = ctk.CTkComboBox(frm_flt, values=["Todos", "Em Andamento", "Concluída", "Cancelada"], width=140, font=self.f_padrao, fg_color="#f0f2f5", text_color="black", command=lambda e: self.atualizar_tabela())
        self.flt_estado.grid(row=0, column=7, padx=5, pady=10)

        # Linha 2 de Filtros
        ctk.CTkLabel(frm_flt, text="Projeto:", font=self.f_padrao, text_color="gray40").grid(row=1, column=0, padx=10, pady=(0,10), sticky="e")
        self.flt_p = ctk.CTkEntry(frm_flt, width=120, font=self.f_padrao, fg_color="#f0f2f5", text_color="black")
        self.flt_p.grid(row=1, column=1, padx=5, pady=(0,10))
        self.flt_p.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        ctk.CTkLabel(frm_flt, text="Material:", font=self.f_padrao, text_color="gray40").grid(row=1, column=2, padx=10, pady=(0,10), sticky="e")
        self.flt_m = ctk.CTkEntry(frm_flt, width=120, font=self.f_padrao, fg_color="#f0f2f5", text_color="black")
        self.flt_m.grid(row=1, column=3, padx=5, pady=(0,10))
        self.flt_m.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        ctk.CTkLabel(frm_flt, text="Cód. Falha:", font=self.f_padrao, text_color="gray40").grid(row=1, column=4, padx=10, pady=(0,10), sticky="e")
        self.flt_cod = ctk.CTkEntry(frm_flt, width=140, placeholder_text="Ex: COD001", font=self.f_padrao, fg_color="#f0f2f5", text_color="black")
        self.flt_cod.grid(row=1, column=5, padx=5, pady=(0,10))
        self.flt_cod.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        ctk.CTkButton(frm_flt, text="Limpar Filtros", width=140, fg_color="#e0e0e0", text_color="black", hover_color="#d6d6d6", font=self.f_padrao, command=self.limpar_filtros).grid(row=1, column=7, padx=5, pady=(0,10))

        # 3. CARDS DE KPI
        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=20, pady=10)
        
        self.lbl_kpi_total = self.criar_card_kpi(frm_kpi, "📦 Produções Filtradas", "0", "#1f538d")
        self.lbl_kpi_taxa = self.criar_card_kpi(frm_kpi, "🎯 Taxa de Sucesso", "0.0%", "#28a745")
        self.lbl_kpi_horas = self.criar_card_kpi(frm_kpi, "⏱️ Total de Horas", "00:00", "#e0a800")

        # 4. CONTAINER DA TABELA
        frm_conteudo = ctk.CTkFrame(self.parent, fg_color="white", corner_radius=12, border_width=1, border_color="#e0e0e0")
        frm_conteudo.pack(fill="both", expand=True, padx=20, pady=5)

        cols = ("id", "data", "projeto", "maquina", "material", "qnt", "tempo", "estado")
        self.tab_tree = ttk.Treeview(frm_conteudo, columns=cols, show="headings", style="Dashboard.Treeview")
        for c in cols: 
            self.tab_tree.heading(c, text=c.upper())
        
        self.tab_tree.column("id", width=50, anchor="center")
        self.tab_tree.column("data", width=100, anchor="center")
        self.tab_tree.column("projeto", width=220, anchor="w")
        self.tab_tree.column("maquina", width=110, anchor="center")
        self.tab_tree.column("material", width=160, anchor="w")
        self.tab_tree.column("qnt", width=80, anchor="center")
        self.tab_tree.column("tempo", width=80, anchor="center")
        self.tab_tree.column("estado", width=120, anchor="center")

        self.tab_tree.bind("<Double-1>", self.abrir_tratamento_ordem)

        sb = ttk.Scrollbar(frm_conteudo, orient="vertical", command=self.tab_tree.yview)
        self.tab_tree.configure(yscrollcommand=sb.set)
        sb.pack(fill="y", side="right", pady=10, padx=(0, 5))
        self.tab_tree.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        # 5. BARRA DE AÇÕES INFERIOR
        frm_acoes = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes.pack(fill="x", padx=20, pady=(5, 15))
        
        ctk.CTkButton(frm_acoes, text="Clonar Ordem", fg_color="#e8f0fe", text_color="#1f538d", hover_color="#d2e3fc", height=35, font=self.f_padrao, command=self.clonar_log).pack(side="left", padx=5)
        ctk.CTkButton(frm_acoes, text="Exportar Dados (CSV)", fg_color="#1f538d", text_color="white", hover_color="#143a63", height=35, font=self.f_padrao, command=self.exportar_csv).pack(side="left", padx=5)
        ctk.CTkButton(frm_acoes, text="Apagar Registo", fg_color="#fbe9e7", text_color="#dc3545", hover_color="#ffcdd2", height=35, font=self.f_padrao, command=self.remover_log).pack(side="right", padx=5)

        self.configurar_estilo_tabela()

    def criar_card_kpi(self, parent, titulo, valor, cor_destaque):
        card = ctk.CTkFrame(parent, fg_color="white", corner_radius=12, border_width=1, border_color="#e0e0e0", height=80)
        card.pack(side="left", fill="x", expand=True, padx=5)
        card.pack_propagate(False)
        
        ctk.CTkLabel(card, text=titulo, text_color="gray20", font=ctk.CTkFont(family="Arial", size=13, weight="bold")).pack(anchor="w", padx=15, pady=(10, 0))
        lbl_valor = ctk.CTkLabel(card, text=valor, text_color=cor_destaque, font=ctk.CTkFont(size=24, weight="bold"))
        lbl_valor.pack(anchor="w", padx=15, pady=2)
        return lbl_valor

    def configurar_estilo_tabela(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dashboard.Treeview", background="white", foreground="#2d3748", font=("Arial", 11), rowheight=32, fieldbackground="white", borderwidth=0)
        style.configure("Dashboard.Treeview.Heading", background="#f8f9fa", foreground="gray40", font=("Arial", 10, "bold"), borderwidth=0, rowheight=35)
        style.map("Dashboard.Treeview", background=[("selected", "#1f538d")], foreground=[("selected", "white")])

    def carregar_combos_filtro(self):
        logs = JSONManager.carregar(ARQUIVO_LOGS) if os.path.exists(ARQUIVO_LOGS) else []
        maquinas = ["Todas"] + sorted(list(set(l.get("maquina", "") for l in logs if l.get("maquina"))))
        self.flt_maq.configure(values=maquinas)
        self.flt_maq.set("Todas")

    def limpar_filtros(self):
        self.flt_data_ini.delete(0, tk.END)
        self.flt_data_fim.delete(0, tk.END)
        self.flt_p.delete(0, tk.END)
        self.flt_m.delete(0, tk.END)
        self.flt_cod.delete(0, tk.END)
        self.flt_maq.set("Todas")
        self.flt_estado.set("Todos")
        self.atualizar_tabela()

    def parse_data_segura(self, data_str):
        if not data_str: return None
        # Limpa as horas se existirem (ex: "2026-08-04 15:59:21")
        if " " in data_str:
            data_str = data_str.split(" ")[0]
        try:
            return datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            return None

    def atualizar_tabela(self):
        for i in self.tab_tree.get_children(): 
            self.tab_tree.delete(i)
        
        proj_q = self.flt_p.get().lower()
        mat_q = self.flt_m.get().lower()
        cod_q = self.flt_cod.get().lower()
        maq_q = self.flt_maq.get()
        est_q = self.flt_estado.get()
        
        d_ini = self.parse_data_segura(self.flt_data_ini.get())
        d_fim = self.parse_data_segura(self.flt_data_fim.get())

        total_filtradas = 0
        sucesso_pecas = 0
        total_horas = 0.0

        logs = JSONManager.carregar(ARQUIVO_LOGS) if os.path.exists(ARQUIVO_LOGS) else []
        pedidos_db = JSONManager.carregar(ARQUIVO_PEDIDOS) if os.path.exists(ARQUIVO_PEDIDOS) else []
        
        logs.sort(key=lambda x: int(x.get("id", 0)), reverse=True)

        for l in logs:
            # --- 1. INTEGRAÇÃO N:N (PROJETO E MATERIAL) ---
            if "pedidos_vinculados" in l and isinstance(l["pedidos_vinculados"], list) and l["pedidos_vinculados"]:
                vinculos = l["pedidos_vinculados"]
                projetos_set = set()
                materiais_set = set()

                for p in pedidos_db:
                    if p.get("id") in vinculos:
                        nr_proj = p.get("nr_projeto", "")
                        nome_proj = p.get("nome_projeto", "")
                        proj_str = f"{nr_proj} - {nome_proj}" if nome_proj else str(nr_proj)
                        if proj_str: projetos_set.add(proj_str)

                        if p.get("material"): materiais_set.add(p["material"])
                        for peca in p.get("pecas", []):
                            if peca.get("material"): materiais_set.add(peca["material"])

                projeto_final = " | ".join(projetos_set) if projetos_set else "Sem Projeto"
                material_final = " | ".join(materiais_set) if materiais_set else "N/A"
            else:
                projeto_final = str(l.get("nr_projeto", ""))
                material_final = str(l.get("material", ""))

            # --- 2. FILTROS DE TEXTO ---
            if proj_q and proj_q not in projeto_final.lower(): continue
            if mat_q and mat_q not in material_final.lower(): continue
            if cod_q and cod_q not in str(l.get("erro", "")).lower(): continue
            
            # --- 3. FILTROS DE COMBOBOX E ESTADO ---
            maquina_log = l.get("maquina", "")
            if maq_q != "Todas" and maquina_log != maq_q: continue

            estado_log = l.get("estado", "Em Andamento")
            if estado_log == "Falha": estado_log = "Cancelada"
            if estado_log == "A Imprimir": estado_log = "Em Andamento" # Uniformizar filtros
            if est_q != "Todos" and estado_log != est_q: continue

            # --- 4. FILTROS DE DATA ---
            log_data_str = l.get("data_inicio", "")
            log_data = self.parse_data_segura(log_data_str)
            if log_data:
                if d_ini and log_data < d_ini: continue
                if d_fim and log_data > d_fim: continue

            # --- 5. ADICIONAR À TABELA ---
            tempo_mostrar = l.get("tempo_real", l.get("tempo_estimado", "00:00"))
            qtd_mostrar = l.get("quantidade_real", l.get("quantidade_consumida", 0.0))

            # Formata a data para a tabela (esconde a hora se existir)
            data_tabela = log_data_str.split(" ")[0] if " " in log_data_str else log_data_str

            self.tab_tree.insert("", "end", values=(
                l.get("id"), data_tabela, projeto_final, maquina_log,
                material_final, qtd_mostrar, tempo_mostrar, estado_log
            ))
            
            # Cálculos de KPI focados apenas nas peças listadas no ecrã
            total_filtradas += 1
            if estado_log in ["Concluída", "Entregue"]: 
                sucesso_pecas += 1
            total_horas += ProducaoService.converter_para_horas(str(tempo_mostrar))

        # Taxa de sucesso ignora as peças "Em Andamento"
        pecas_finalizadas = sum(1 for item in self.tab_tree.get_children() if self.tab_tree.item(item)['values'][7] in ["Concluída", "Entregue", "Cancelada"])
        taxa = (sucesso_pecas / pecas_finalizadas * 100) if pecas_finalizadas > 0 else 0.0
        
        self.lbl_kpi_total.configure(text=str(total_filtradas))
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
                novo_log["id"] = max([int(l.get("id", 0)) for l in logs]) + 1
                novo_log["data_inicio"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                novo_log["estado"] = "Em Andamento"
                novo_log["erro"] = ""
                # Limpa dados reais na clonagem
                novo_log.pop("tempo_real", None)
                novo_log.pop("quantidade_real", None)
                
                logs.append(novo_log)
                JSONManager.salvar(logs, ARQUIVO_LOGS)
                self.carregar_combos_filtro()
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
        # 1. Guarda a atualização na base de dados
        logs = JSONManager.carregar(ARQUIVO_LOGS)
        for idx, log in enumerate(logs):
            if log.get("id") == log_atualizado.get("id"):
                logs[idx] = log_atualizado
                break
        JSONManager.salvar(logs, ARQUIVO_LOGS)

        # 2. RASTREABILIDADE BIDIRECIONAL
        estado_final = log_atualizado.get("estado")
        pedidos_vinc = log_atualizado.get("pedidos_vinculados", [])
        
        if pedidos_vinc:
            pedidos_db = JSONManager.carregar(ARQUIVO_PEDIDOS)
            mudou_pedido = False
            
            for p in pedidos_db:
                if p.get("id") in pedidos_vinc:
                    if estado_final == "Concluída":
                        p["estado"] = "Entregue"
                    elif estado_final == "Cancelada":
                        p["estado"] = "Pendente"
                    mudou_pedido = True
                    
            if mudou_pedido:
                JSONManager.salvar(pedidos_db, ARQUIVO_PEDIDOS)

        self.atualizar_tabela()

    def remover_log(self):
        sel = self.tab_tree.selection()
        if not sel: return
        id_reg = self.tab_tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Aviso", "Remover do histórico local permanentemente?"):
            logs = [l for l in JSONManager.carregar(ARQUIVO_LOGS) if l.get("id") != id_reg]
            JSONManager.salvar(logs, ARQUIVO_LOGS)
            self.carregar_combos_filtro()
            self.atualizar_tabela()