from datetime import datetime
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os

from services.maquina_service import MaquinaService
from services.producao_service import ProducaoService
from services.pedido_service import PedidoService
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

        cols = ("id", "data", "projeto", "maquina", "material", "qnt", "tempo", "estado", "operador", "verificado")
        anchors = {"id": "center", "data": "center", "projeto": "w", "maquina": "w", "material": "w", "qnt": "center", "tempo": "center", "estado": "w", "operador": "w", "verificado": "w"}
        self.tab_tree = ttk.Treeview(frm_conteudo, columns=cols, show="headings", style="Dashboard.Treeview")
        for c in cols:
            self.tab_tree.heading(c, text=c.upper(), anchor=anchors[c])
        self.tab_tree.heading("operador", text="INICIADO POR")
        self.tab_tree.heading("verificado", text="VERIFICADO POR")

        self.tab_tree.column("id", width=95, anchor="center")
        self.tab_tree.column("data", width=90, anchor="center")
        self.tab_tree.column("projeto", width=200, anchor="w")
        self.tab_tree.column("maquina", width=150, anchor="w")
        self.tab_tree.column("material", width=150, anchor="w")
        self.tab_tree.column("qnt", width=70, anchor="center")
        self.tab_tree.column("tempo", width=70, anchor="center")
        self.tab_tree.column("estado", width=130, anchor="w")
        self.tab_tree.column("operador", width=110, anchor="w")
        self.tab_tree.column("verificado", width=110, anchor="w")

        self.tab_tree.bind("<Double-1>", self.abrir_tratamento_ordem)

        # Ordenação por coluna — clique no cabeçalho inverte a ordem
        self._sort_col   = "data"   # coluna actualmente ordenada
        self._sort_asc   = False    # False = mais recente primeiro (padrão)
        _COL_IDX = {"id":0,"data":1,"projeto":2,"maquina":3,"material":4,
                    "qnt":5,"tempo":6,"estado":7,"operador":8,"verificado":9}
        for col in ("id","data","projeto","maquina","material","qnt","tempo","estado","operador","verificado"):
            self.tab_tree.heading(col, command=lambda c=col: self._ordenar_por(c))

        sb = ttk.Scrollbar(frm_conteudo, orient="vertical", command=self.tab_tree.yview)
        self.tab_tree.configure(yscrollcommand=sb.set)
        sb.pack(fill="y", side="right", pady=10, padx=(0, 5))
        self.tab_tree.pack(fill="both", expand=True, side="left", padx=10, pady=10)

        # 5. BARRA DE AÇÕES INFERIOR
        frm_acoes = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes.pack(fill="x", padx=24, pady=(5, 18))

        theme.button_ghost(frm_acoes, text="Clonar Ordem", height=35, command=self.clonar_log).pack(side="left", padx=5)
        theme.button_ghost(frm_acoes, text="📄 Gerar PDF", height=35, command=self.gerar_pdf_ordem).pack(side="left", padx=5)
        theme.button_ghost(frm_acoes, text="📋 Resumo do Dia", height=35, command=self.gerar_resumo_diario).pack(side="left", padx=5)
        theme.button_primary(frm_acoes, text="Exportar Dados (CSV)", height=35, command=self.exportar_csv).pack(side="left", padx=5)
        theme.button_danger(frm_acoes, text="Apagar Registo", height=35, command=self.remover_log).pack(side="right", padx=5)

        self.configurar_estilo_tabela()

    def configurar_estilo_tabela(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dashboard.Treeview", background=theme.SURFACE[0], foreground=theme.TEXT[0], rowheight=32, fieldbackground=theme.SURFACE[0], borderwidth=0)
        style.configure("Dashboard.Treeview.Heading", background=theme.SURFACE_ALT[0], foreground=theme.TEXT_MUTED[0], borderwidth=0, rowheight=35)
        style.map("Dashboard.Treeview", background=[("selected", theme.ACCENT[0])], foreground=[("selected", "white")])

        # Tags nativas do Treeview para colorir o texto da linha por estado
        # (substituem as pills flutuantes que desalinhavam noutros monitores/escalas)
        self.tab_tree.tag_configure("tag_ok",      foreground=theme.SUCCESS[0])
        self.tab_tree.tag_configure("tag_run",     foreground=theme.TEAL[0])
        self.tab_tree.tag_configure("tag_bad",     foreground=theme.CRITICAL[0])
        self.tab_tree.tag_configure("tag_neutral", foreground=theme.TEXT_MUTED[0])

    def carregar_combos_filtro(self):
        logs = ProducaoService.obter_todos()
        _id_para_nome_combo = MaquinaService.obter_lookup_id_nome()
        nomes_maquinas = set()
        for l in logs:
            nome = ProducaoService.normalizar_maquina(l, _id_para_nome_combo)
            if nome and not nome.startswith("Desconhecida"):
                nomes_maquinas.add(nome)
        maquinas = ["Todas"] + sorted(nomes_maquinas)
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

    def _ordenar_por(self, coluna: str):
        """Inverte a ordenação se a mesma coluna; caso contrário ordena pela nova."""
        if self._sort_col == coluna:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = coluna
            self._sort_asc = True
        # Atualiza símbolo ↑↓ no cabeçalho
        _LABELS = {"id":"ID","data":"DATA","projeto":"PROJETO","maquina":"MAQUINA",
                   "material":"MATERIAL","qnt":"QNT","tempo":"TEMPO","estado":"ESTADO",
                   "operador":"INICIADO POR","verificado":"VERIFICADO POR"}
        for c, lbl in _LABELS.items():
            seta = (" ↑" if self._sort_asc else " ↓") if c == coluna else ""
            self.tab_tree.heading(c, text=lbl + seta)
        self.atualizar_tabela()

    # ------------------------------------------------------------------ #
    #  HELPERS PRIVADOS                                                    #
    # ------------------------------------------------------------------ #

    def _resolver_projeto_material(self, log: dict, pedidos_db: list) -> tuple[str, str]:
        """Devolve (projeto_final, material_final) para uma linha de produção,
        com suporte completo a dados legacy."""
        vinculos_raw = log.get("pedidos_vinculados", [])
        if isinstance(vinculos_raw, list) and vinculos_raw:
            vinculos_int = set()
            for v in vinculos_raw:
                try:
                    vinculos_int.add(int(v))
                except (TypeError, ValueError):
                    pass
            projetos_set, materiais_set = set(), set()
            for p in pedidos_db:
                try:
                    pid = int(p.get("id", -1))
                except (TypeError, ValueError):
                    pid = -1
                if pid in vinculos_int:
                    nr  = p.get("nr_projeto", "")
                    nom = p.get("nome_projeto", "")
                    proj_str = f"{nr} - {nom}" if nom else str(nr)
                    if proj_str:
                        projetos_set.add(proj_str)
                    for peca in p.get("pecas", []):
                        if peca.get("material"):
                            materiais_set.add(peca["material"])
            return (
                " | ".join(projetos_set) if projetos_set else "Sem Projeto",
                " | ".join(materiais_set) if materiais_set else "N/A",
            )
        # Legacy
        projeto = str(log.get("nr_projeto") or log.get("projeto") or log.get("projeto_nr") or "")
        nome_leg = log.get("nome_projeto", "")
        if projeto and nome_leg:
            projeto = f"{projeto} - {nome_leg}"
        material = str(log.get("material") or log.get("material_tipo") or log.get("filamento") or "")
        return projeto, material

    def _passa_filtros(self, log: dict, projeto: str, material: str,
                       filtros: dict, id_para_nome: dict) -> bool:
        """Verifica se uma linha passa em todos os filtros activos."""
        if filtros["proj"] and filtros["proj"] not in projeto.lower():
            return False
        if filtros["mat"] and filtros["mat"] not in material.lower():
            return False
        if filtros["cod"] and filtros["cod"] not in str(log.get("erro", "")).lower():
            return False
        maquina = ProducaoService.normalizar_maquina(log, id_para_nome)
        if filtros["maq"] != "Todas" and maquina != filtros["maq"]:
            return False
        estado = log.get("estado", "Em Andamento")
        if estado == "Falha":      estado = "Cancelada"
        if estado == "A Imprimir": estado = "Em Andamento"
        if filtros["est"] != "Todos" and estado != filtros["est"]:
            return False
        log_data = self.parse_data_segura(log.get("data_inicio", ""))
        if log_data:
            if filtros["d_ini"] and log_data < filtros["d_ini"]:
                return False
            if filtros["d_fim"] and log_data > filtros["d_fim"]:
                return False
        return True

    # ------------------------------------------------------------------ #
    #  TABELA PRINCIPAL                                                    #
    # ------------------------------------------------------------------ #

    def atualizar_tabela(self):
        for i in self.tab_tree.get_children():
            self.tab_tree.delete(i)

        filtros = {
            "proj":  self.flt_p.get().lower(),
            "mat":   self.flt_m.get().lower(),
            "cod":   self.flt_cod.get().lower(),
            "maq":   self.flt_maq.get(),
            "est":   self.flt_estado.get(),
            "d_ini": self.parse_data_segura(self.flt_data_ini.get()),
            "d_fim": self.parse_data_segura(self.flt_data_fim.get()),
        }

        logs       = ProducaoService.obter_todos()
        pedidos_db = PedidoService.obter_todos()
        _id_para_nome = MaquinaService.obter_lookup_id_nome()

        total_filtradas = sucesso_pecas = pecas_finalizadas = 0
        total_horas = 0.0

        # Ordena os logs antes de iterar, para que a inserção na tabela
        # já respeite a ordem pretendida pelo utilizador.
        _COL_KEY = {
            "id":       lambda l: int(l.get("id", 0)),
            "data":     lambda l: str(l.get("data_inicio", "")),
            "projeto":  lambda l: str(l.get("nr_projeto", "")),
            "maquina":  lambda l: ProducaoService.normalizar_maquina(l, _id_para_nome),
            "material": lambda l: str(l.get("material", "")),
            "qnt":      lambda l: float(str(l.get("quantidade_real") or l.get("quantidade_consumida") or l.get("quantidade") or 0).replace(",",".")),
            "tempo":    lambda l: ProducaoService.converter_para_horas(ProducaoService.normalizar_tempo(l)),
            "estado":   lambda l: str(l.get("estado", "")),
            "operador": lambda l: str(l.get("operador") or l.get("responsavel") or ""),
            "verificado":lambda l: str(l.get("verificado_por", "")),
        }
        key_fn = _COL_KEY.get(self._sort_col, _COL_KEY["data"])
        logs = sorted(logs, key=lambda l: key_fn(l), reverse=not self._sort_asc)

        for l in logs:
            projeto_final, material_final = self._resolver_projeto_material(l, pedidos_db)

            if not self._passa_filtros(l, projeto_final, material_final, filtros, _id_para_nome):
                continue

            # ── Campos para exibição ──────────────────────────────────────
            maquina_log  = ProducaoService.normalizar_maquina(l, _id_para_nome)
            estado_log   = l.get("estado", "Em Andamento")
            if estado_log == "Falha":      estado_log = "Cancelada"
            if estado_log == "A Imprimir": estado_log = "Em Andamento"
            log_data_str = l.get("data_inicio", "")

            # --- 5. ADICIONAR À TABELA ---
            # normalizar_tempo converte todos os formatos legacy para HH:MM
            tempo_mostrar = ProducaoService.normalizar_tempo(l)
            # Compatibilidade legacy: "quantidade" era o nome antigo de "quantidade_consumida"
            qtd_mostrar = (
                l.get("quantidade_real") or
                l.get("quantidade_consumida") or
                l.get("quantidade") or
                0.0
            )

            # Formata a data para a tabela (esconde a hora se existir)
            data_tabela = log_data_str.split(" ")[0] if " " in log_data_str else log_data_str

            # "—" para produções ainda por fechar, para distinguir de um campo em branco
            # Compatibilidade legacy: "responsavel" era o nome antigo de "operador"
            operador_log = l.get("operador") or l.get("responsavel") or "—"
            verificado_log = l.get("verificado_por", "") or "—"

            tag_linha = "tag_" + _VARIANTE_ESTADO.get(estado_log, "neutral")
            self.tab_tree.insert("", "end", tags=(tag_linha,), values=(
                ProducaoService.formatar_codigo(l.get("id")), data_tabela, projeto_final, maquina_log,
                material_final, qtd_mostrar, tempo_mostrar, estado_log, operador_log, verificado_log
            ))


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

    def gerar_resumo_diario(self):
        """Abre a janela do resumo do dia — a mesma que surge automaticamente
        no arranque da app, mas disponível a qualquer momento a pedido."""
        from gui.dialogs.resumo_diario import JanelaResumoDiario
        JanelaResumoDiario(self.parent.winfo_toplevel(), abertura_automatica=False)

    def gerar_pdf_ordem(self):
        """Gera o PDF da ordem de produção selecionada e abre a pasta de saída."""
        sel = self.tab_tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Seleciona uma produção na tabela primeiro.")
            return
        id_reg = ProducaoService.extrair_id(self.tab_tree.item(sel[0])['values'][0])

        producao = None
        for p in ProducaoService.obter_todos():
            if p.get("id") == id_reg:
                producao = p
                break
        if not producao:
            messagebox.showerror("Erro", "Produção não encontrada.")
            return

        vinculos = producao.get("pedidos_vinculados", [])
        pedidos_vinculados = [p for p in PedidoService.obter_todos() if p.get("id") in vinculos]
        id_para_nome = MaquinaService.obter_lookup_id_nome()

        pasta_saida = filedialog.askdirectory(title="Escolher pasta para guardar o PDF")
        if not pasta_saida:
            return

        codigo = ProducaoService.formatar_codigo(producao.get("id"))
        caminho = os.path.join(pasta_saida, f"Ordem_{codigo}.pdf")

        try:
            from services.pdf_service import PDFService
            PDFService.gerar_ordem_producao(producao, pedidos_vinculados, id_para_nome, caminho)
            messagebox.showinfo("Sucesso", f"PDF gerado:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Erro ao gerar PDF", str(e))

    def exportar_csv(self):
        caminho_salvar = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not caminho_salvar: return

        # Exporta os registos completos por trás das linhas atualmente visíveis
        # na tabela (respeita os filtros ativos), não só as colunas mostradas.
        ids_visiveis = {ProducaoService.extrair_id(self.tab_tree.item(i)['values'][0]) for i in self.tab_tree.get_children()}
        producoes = [p for p in ProducaoService.obter_todos() if p.get("id") in ids_visiveis]
        pedidos_db = PedidoService.obter_todos()

        if ExportService.exportar_historico_csv(caminho_salvar, producoes, pedidos_db):
            messagebox.showinfo("Sucesso", "Exportação de auditoria concluída.")
        else:
            messagebox.showerror("Erro", "Falha ao salvar CSV.")

    def clonar_log(self):
        sel = self.tab_tree.selection()
        if not sel: return
        id_reg = ProducaoService.extrair_id(self.tab_tree.item(sel[0])['values'][0])

        if ProducaoService.clonar_producao(id_reg):
            self.carregar_combos_filtro()
            self.atualizar_tabela()
            messagebox.showinfo("Clonado", "Nova impressão registada com base na anterior.")

    def abrir_tratamento_ordem(self, event=None):
        sel = self.tab_tree.selection()
        if not sel: return
        id_reg = ProducaoService.extrair_id(self.tab_tree.item(sel[0])['values'][0])
        log = ProducaoService.obter_por_id(id_reg)
        if log:
            JanelaFecharOrdem(self.master_app, log, self.salvar_estado_final_ordem)

    def salvar_estado_final_ordem(self, log_atualizado):
        # Guarda a atualização na base de dados. O estado dos pedidos vinculados
        # NÃO é alterado automaticamente aqui — um pedido pode ter mais do que uma
        # produção associada, e o sistema não sabe (ainda) se as quantidades pedidas
        # já foram todas satisfeitas. Mudar o estado do pedido é feito manualmente
        # em Gestão de Pedidos.
        ProducaoService.atualizar_producao(log_atualizado)
        self.atualizar_tabela()

    def remover_log(self):
        sel = self.tab_tree.selection()
        if not sel: return
        id_reg = ProducaoService.extrair_id(self.tab_tree.item(sel[0])['values'][0])
        if messagebox.askyesno("Aviso", "Remover do histórico local permanentemente?"):
            ProducaoService.remover_producao(id_reg)
            self.carregar_combos_filtro()
            self.atualizar_tabela()