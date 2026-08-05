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
from gui import theme

_VARIANTE_ESTADO = {
    "Concluída": "ok", "Entregue": "ok",
    "Em Andamento": "run", "A Imprimir": "run",
    "Cancelada": "bad", "Falha": "bad",
    "Pendente": "neutral",
}

class HistoricoTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.master_app = master_app

        self.parent.configure(fg_color=theme.BG)

        self.construir_layout()
        self.carregar_combos_filtro()
        self.atualizar_tabela()

    def construir_layout(self):
        # 1. HEADER & TÍTULO
        hoje = theme.data_extensa_pt(datetime.now()).capitalize()
        theme.page_header(self.parent, "Painel de Produção", "Dashboard", hoje).pack(fill="x", padx=24, pady=(22, 10))

        # 2. PAINEL DE FILTROS — linha única e fluida
        frm_flt = ctk.CTkFrame(self.parent, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
        frm_flt.pack(fill="x", padx=24, pady=6)
        frm_flt_inner = ctk.CTkFrame(frm_flt, fg_color="transparent")
        frm_flt_inner.pack(fill="x", padx=16, pady=14)

        def _campo(texto, widget_builder, width):
            col = ctk.CTkFrame(frm_flt_inner, fg_color="transparent")
            col.pack(side="left", padx=(0, 16))
            ctk.CTkLabel(col, text=texto, font=theme.font_eyebrow(9), text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", pady=(0, 4))
            widget = widget_builder(col, width)
            widget.pack(fill="x")
            return widget

        self.flt_data_ini = _campo("DATA INÍCIO", lambda p, w: theme.entry(p, width=w, placeholder_text="AAAA-MM-DD", font=theme.font_mono(12)), 112)
        self.flt_data_ini.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        self.flt_data_fim = _campo("DATA FIM", lambda p, w: theme.entry(p, width=w, placeholder_text="AAAA-MM-DD", font=theme.font_mono(12)), 112)
        self.flt_data_fim.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        self.flt_maq = _campo("MÁQUINA", lambda p, w: theme.combobox(p, values=["Todas"], width=w, font=self.f_padrao, command=lambda e: self.atualizar_tabela()), 150)

        self.flt_estado = _campo("ESTADO", lambda p, w: theme.combobox(p, values=["Todos", "Em Andamento", "Concluída", "Cancelada"], width=w, font=self.f_padrao, command=lambda e: self.atualizar_tabela()), 140)

        self.flt_p = _campo("PROJETO", lambda p, w: theme.entry(p, width=w, font=self.f_padrao), 130)
        self.flt_p.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        self.flt_m = _campo("MATERIAL", lambda p, w: theme.entry(p, width=w, font=self.f_padrao), 130)
        self.flt_m.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        self.flt_cod = _campo("CÓD. FALHA", lambda p, w: theme.entry(p, width=w, placeholder_text="COD001", font=theme.font_mono(12)), 110)
        self.flt_cod.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        col_limpar = ctk.CTkFrame(frm_flt_inner, fg_color="transparent")
        col_limpar.pack(side="left", fill="y")
        ctk.CTkLabel(col_limpar, text=" ", font=theme.font_eyebrow(9)).pack(fill="x", pady=(0, 4))
        ctk.CTkButton(col_limpar, text="Limpar", fg_color=theme.SURFACE_ALT, text_color=theme.TEXT, hover_color=theme.BORDER, font=self.f_padrao, corner_radius=theme.RADIUS_S, width=80, command=self.limpar_filtros).pack()

        # 3. CARDS DE KPI
        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=24, pady=(4, 10))

        self.lbl_kpi_total = theme.kpi_card(frm_kpi, "Produções Filtradas", "0")
        self.lbl_kpi_taxa = theme.kpi_card(frm_kpi, "Taxa de Sucesso", "0.0%", theme.SUCCESS)
        self.lbl_kpi_horas = theme.kpi_card(frm_kpi, "Total de Horas", "00:00", theme.TEAL)

        # 4. CONTAINER DA TABELA
        frm_conteudo = ctk.CTkFrame(self.parent, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
        frm_conteudo.pack(fill="both", expand=True, padx=24, pady=5)

        cols = ("id", "data", "projeto", "maquina", "material", "qnt", "tempo", "estado")
        anchors = {"id": "center", "data": "center", "projeto": "w", "maquina": "w", "material": "w", "qnt": "center", "tempo": "center", "estado": "w"}
        self.tab_tree = ttk.Treeview(frm_conteudo, columns=cols, show="headings", style="Dashboard.Treeview")
        for c in cols:
            self.tab_tree.heading(c, text=c.upper(), anchor=anchors[c])


        self.tab_tree.column("id", width=95, anchor="center")
        self.tab_tree.column("data", width=90, anchor="center")
        self.tab_tree.column("projeto", width=200, anchor="w")
        self.tab_tree.column("maquina", width=150, anchor="w")
        self.tab_tree.column("material", width=150, anchor="w")
        self.tab_tree.column("qnt", width=70, anchor="center")
        self.tab_tree.column("tempo", width=70, anchor="center")
        self.tab_tree.column("estado", width=130, anchor="w")

        self.tab_tree.bind("<Double-1>", self.abrir_tratamento_ordem)

        sb = ttk.Scrollbar(frm_conteudo, orient="vertical", command=self.tab_tree.yview)
        self.tab_tree.configure(yscrollcommand=sb.set)
        sb.pack(fill="y", side="right", pady=10, padx=(0, 5))
        self.tab_tree.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        # Criado depois da scrollbar: precisa de "envolver" o yscrollcommand já
        # ligado ao sb.set, para saber repor as pills sempre que a vista faz scroll.
        self.estado_pills = theme.TreeviewPillColumn(self.tab_tree, "estado")

        # 5. BARRA DE AÇÕES INFERIOR
        frm_acoes = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes.pack(fill="x", padx=24, pady=(5, 18))

        theme.button_ghost(frm_acoes, text="Clonar Ordem", height=35, command=self.clonar_log).pack(side="left", padx=5)
        theme.button_primary(frm_acoes, text="Exportar Dados (CSV)", height=35, command=self.exportar_csv).pack(side="left", padx=5)
        theme.button_danger(frm_acoes, text="Apagar Registo", height=35, command=self.remover_log).pack(side="right", padx=5)

        self.configurar_estilo_tabela()

    def configurar_estilo_tabela(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dashboard.Treeview", background=theme.SURFACE[0], foreground=theme.TEXT[0], rowheight=32, fieldbackground=theme.SURFACE[0], borderwidth=0)
        style.configure("Dashboard.Treeview.Heading", background=theme.SURFACE_ALT[0], foreground=theme.TEXT_MUTED[0], borderwidth=0, rowheight=35)
        style.map("Dashboard.Treeview", background=[("selected", theme.ACCENT[0])], foreground=[("selected", "white")])

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
        pecas_finalizadas = 0
        total_horas = 0.0

        logs = JSONManager.carregar(ARQUIVO_LOGS) if os.path.exists(ARQUIVO_LOGS) else []
        pedidos_db = JSONManager.carregar(ARQUIVO_PEDIDOS) if os.path.exists(ARQUIVO_PEDIDOS) else []
        
        logs.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
        pill_dados = {}

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

            item_id = self.tab_tree.insert("", "end", values=(
                ProducaoService.formatar_codigo(l.get("id")), data_tabela, projeto_final, maquina_log,
                material_final, qtd_mostrar, tempo_mostrar, estado_log
            ))
            pill_dados[item_id] = (estado_log, _VARIANTE_ESTADO.get(estado_log, "neutral"))


            # Cálculos de KPI focados apenas nas peças listadas no ecrã
            total_filtradas += 1
            if estado_log in ["Concluída", "Entregue"]:
                sucesso_pecas += 1
            if estado_log in ["Concluída", "Entregue", "Cancelada"]:
                pecas_finalizadas += 1
            total_horas += ProducaoService.converter_para_horas(str(tempo_mostrar))

        # Taxa de sucesso ignora as peças "Em Andamento"
        taxa = (sucesso_pecas / pecas_finalizadas * 100) if pecas_finalizadas > 0 else 0.0
        
        self.lbl_kpi_total.configure(text=str(total_filtradas))
        self.lbl_kpi_taxa.configure(text=f"{taxa:.1f}%")
        self.lbl_kpi_horas.configure(text=ProducaoService.converter_para_string(total_horas))
        self.estado_pills.definir_dados(pill_dados)

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
        id_reg = ProducaoService.extrair_id(self.tab_tree.item(sel[0])['values'][0])


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
        id_reg = ProducaoService.extrair_id(self.tab_tree.item(sel[0])['values'][0])
        for log in JSONManager.carregar(ARQUIVO_LOGS):
            if log.get("id") == id_reg:
                JanelaFecharOrdem(self.master_app, log, self.salvar_estado_final_ordem)
                break

    def salvar_estado_final_ordem(self, log_atualizado):
        # Guarda a atualização na base de dados. O estado dos pedidos vinculados
        # NÃO é alterado automaticamente aqui — um pedido pode ter mais do que uma
        # produção associada, e o sistema não sabe (ainda) se as quantidades pedidas
        # já foram todas satisfeitas. Mudar o estado do pedido é feito manualmente
        # em Gestão de Pedidos.
        logs = JSONManager.carregar(ARQUIVO_LOGS)
        for idx, log in enumerate(logs):
            if log.get("id") == log_atualizado.get("id"):
                logs[idx] = log_atualizado
                break
        JSONManager.salvar(logs, ARQUIVO_LOGS)

        self.atualizar_tabela()

    def remover_log(self):
        sel = self.tab_tree.selection()
        if not sel: return
        id_reg = ProducaoService.extrair_id(self.tab_tree.item(sel[0])['values'][0])
        if messagebox.askyesno("Aviso", "Remover do histórico local permanentemente?"):
            logs = [l for l in JSONManager.carregar(ARQUIVO_LOGS) if l.get("id") != id_reg]
            JSONManager.salvar(logs, ARQUIVO_LOGS)
            self.carregar_combos_filtro()
            self.atualizar_tabela()