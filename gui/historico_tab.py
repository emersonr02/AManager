"""Ordens de produção — registo de todas as ordens, com filtros, KPIs e as
ações sobre a ordem selecionada (fechar, clonar, PDF, anular).

(Era o ecrã "Dashboard"; o painel do dia passou para gui/painel_tab.py.)"""
import os
from datetime import datetime
from tkinter import messagebox, filedialog

import customtkinter as ctk

from services.maquina_service import MaquinaService
from services.producao_service import ProducaoService
from services.pedido_service import PedidoService
from services.export_service import ExportService
from services.nc_service import NCService
from gui.dialogs.fechar_ordem import JanelaFecharOrdem
from gui import theme

# Estado (já uniformizado) → variante de cor da linha. Concluída fica neutra:
# a cor assinala só o que pede atenção (cancelada) ou está a decorrer.
_VARIANTE_ESTADO = {
    "Concluída": "ok", "Entregue": "ok",
    "Em Andamento": "run",
    "Cancelada": "bad",
    "Pendente": "neutral",
}


def _parse_data(texto):
    """Aceita AAAA-MM-DD ou DD/MM/AAAA (com ou sem hora); None se inválida."""
    if not texto:
        return None
    texto = str(texto).strip().split(" ")[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def _estado_uniformizado(log):
    estado = log.get("estado", "Em Andamento")
    if estado == "Falha":
        return "Cancelada"
    if estado == "A Imprimir":
        return "Em Andamento"
    return estado


def concluir_fecho_ordem(widget, log):
    """Grava o fecho de uma ordem e fecha o ciclo com os pedidos vinculados:
    as peças aprovadas no controlo de qualidade (conformidade) passam a contar
    como produzidas no pedido, e — se o progresso o justificar — propõe mudar o
    estado do pedido (ex: todas as peças feitas → Concluído).

    O estado do pedido nunca muda sem confirmação: um pedido pode ter várias
    ordens e só o utilizador sabe se já está tudo pronto a entregar."""
    ProducaoService.atualizar_producao(log)
    codigo = ProducaoService.formatar_codigo(log.get("id"))
    theme.toast(widget, f"Ordem {codigo} guardada como {log.get('estado')}.")
    if log.get("estado") != "Concluída":
        return []

    conformes = [chave for chave, qa in (log.get("qa_por_peca") or {}).items() if qa.get("conformidade")]
    alterados = PedidoService.registar_pecas_produzidas(conformes)
    sugestoes = []
    for p in alterados:
        novo = PedidoService.estado_sugerido(p)
        if novo != p.get("estado"):
            sugestoes.append((p, novo))
    if not sugestoes:
        return []

    linhas = []
    for p, novo in sugestoes:
        feitas, total = PedidoService.progresso(p)
        linhas.append(f"• {PedidoService.formatar_codigo(p['id'])}: {p.get('estado')} → {novo}  ({feitas}/{total} unidades)")
    if messagebox.askyesno("Atualizar pedidos vinculados",
                           "Com as peças aprovadas nesta ordem:\n\n" + "\n".join(linhas) +
                           "\n\nAtualizar o estado destes pedidos?"):
        for p, novo in sugestoes:
            PedidoService.alterar_estado(p["id"], novo)
        return sugestoes
    return []


class JanelaAnularOrdem(theme.Dialogo):
    """Anular (em vez de apagar): o registo fica no ficheiro para rastreabilidade."""

    def __init__(self, parent, producao, ao_anular):
        self.producao = producao
        self._ao_anular = ao_anular
        codigo = ProducaoService.formatar_codigo(producao.get("id"))
        super().__init__(parent, f"Anular ordem {codigo}", largura=480, altura=320, texto_acao="Anular ordem",
                         estilo_acao="danger", scroll=False,
                         subtitulo="A ordem deixa de contar em listas, KPIs e análises, mas o registo fica guardado "
                                   "(com quem anulou e porquê) para efeitos de auditoria.")
        theme.rotulo_campo(self.corpo, "Motivo", True).pack(anchor="w", pady=(8, 2))
        self.ent_motivo = theme.entry(self.corpo, placeholder_text="ex.: registo duplicado, lançada na máquina errada")
        self.ent_motivo.pack(fill="x")
        self.ent_motivo.focus_set()

    def confirmar(self):
        motivo = self.ent_motivo.get().strip()
        if not motivo:
            messagebox.showwarning("Motivo em falta", "Indique o motivo da anulação.")
            return
        ProducaoService.anular_producao(self.producao.get("id"), motivo)
        theme.toast(self, f"Ordem {ProducaoService.formatar_codigo(self.producao.get('id'))} anulada.", "info")
        self._ao_anular()
        self.destroy()


class HistoricoTab:
    def __init__(self, parent_frame, f_padrao=None, f_titulo=None, master_app=None):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.master_app = master_app
        self.parent.configure(fg_color=theme.BG)

        self._sort_col = "data"   # coluna atualmente ordenada
        self._sort_asc = False    # False = mais recente primeiro (padrão)

        self.construir_layout()
        self.carregar_combos_filtro()
        self.atualizar_tabela()

    # ------------------------------------------------------------------ #
    #  LAYOUT                                                              #
    # ------------------------------------------------------------------ #
    def construir_layout(self):
        cab = theme.page_header(self.parent, "Registo de produção", "Ordens de produção")
        cab.pack(fill="x", padx=24, pady=(18, 8))
        theme.button_ghost(cab.acoes, text="Exportar CSV", height=34, command=self.exportar_csv).pack(side="left", padx=(0, 10))
        theme.button_action(cab.acoes, text="+ Nova ordem", height=34,
                            command=lambda: self.master_app and self.master_app.abrir_nova_ordem()).pack(side="left")

        # FILTROS — quebram de linha em ecrãs estreitos
        frm_flt = theme.card(self.parent)
        frm_flt.pack(fill="x", padx=24, pady=4)
        frm_flt_inner = ctk.CTkFrame(frm_flt, fg_color="transparent")
        frm_flt_inner.pack(fill="x", padx=16, pady=10)
        campos_filtro = []

        def _campo(texto, widget_builder, width):
            col = ctk.CTkFrame(frm_flt_inner, fg_color="transparent")
            campos_filtro.append(col)
            ctk.CTkLabel(col, text=texto.upper(), font=theme.font_eyebrow(11), text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", pady=(0, 3))
            widget = widget_builder(col, width)
            widget.pack(fill="x")
            return widget

        self.flt_data_ini = _campo("Data início", lambda p, w: theme.entry(p, width=w, placeholder_text="DD/MM/AAAA", font=theme.font_mono(12)), 112)
        self.flt_data_ini.bind("<KeyRelease>", lambda e: self.atualizar_tabela())
        self.flt_data_fim = _campo("Data fim", lambda p, w: theme.entry(p, width=w, placeholder_text="DD/MM/AAAA", font=theme.font_mono(12)), 112)
        self.flt_data_fim.bind("<KeyRelease>", lambda e: self.atualizar_tabela())
        self.flt_maq = _campo("Máquina", lambda p, w: theme.combobox(p, values=["Todas"], width=w, state="readonly", command=lambda e: self.atualizar_tabela()), 160)
        self.flt_estado = _campo("Estado", lambda p, w: theme.combobox(p, values=["Todos", "Em Andamento", "Concluída", "Cancelada"], width=w, state="readonly", command=lambda e: self.atualizar_tabela()), 140)
        self.flt_estado.set("Todos")
        self.flt_p = _campo("Projeto", lambda p, w: theme.entry(p, width=w), 120)
        self.flt_p.bind("<KeyRelease>", lambda e: self.atualizar_tabela())
        self.flt_m = _campo("Material", lambda p, w: theme.entry(p, width=w), 120)
        self.flt_m.bind("<KeyRelease>", lambda e: self.atualizar_tabela())
        self.flt_cod = _campo("Cód. falha", lambda p, w: theme.entry(p, width=w, placeholder_text="ex.: COD001", font=theme.font_mono(12)), 110)
        self.flt_cod.bind("<KeyRelease>", lambda e: self.atualizar_tabela())

        col_limpar = ctk.CTkFrame(frm_flt_inner, fg_color="transparent")
        campos_filtro.append(col_limpar)
        ctk.CTkLabel(col_limpar, text=" ", font=theme.font_eyebrow(11)).pack(fill="x", pady=(0, 3))
        theme.button_secondary(col_limpar, text="Limpar", width=80, command=self.limpar_filtros).pack()
        # Espaço 12: a 1300px todos os filtros cabem numa linha; num portátil quebram.
        theme.fluxo_horizontal(frm_flt_inner, campos_filtro, espaco=12)

        # Resumo das ordens filtradas numa linha (eram 3 cartões de ~90px — num
        # portátil a tabela ficava com 3 linhas visíveis).
        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=26, pady=(8, 4))

        def _metrica(rotulo):
            ctk.CTkLabel(frm_kpi, text=rotulo, font=theme.font_body(12), text_color=theme.TEXT_MUTED).pack(side="left")
            valor = ctk.CTkLabel(frm_kpi, text="0", font=theme.font_mono(15, "bold"), text_color=theme.TEXT)
            valor.pack(side="left", padx=(6, 22))
            return valor
        self.lbl_kpi_total = _metrica("Ordens filtradas")
        self.lbl_kpi_taxa = _metrica("Taxa de sucesso")
        self.lbl_kpi_horas = _metrica("Horas de máquina")

        # Barra de ações sobre a ordem selecionada + detalhe — reservadas antes
        # da tabela (side="bottom"): num ecrã baixo é a tabela que encolhe.
        frm_detalhe = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_detalhe.pack(side="bottom", fill="x", padx=24, pady=(0, 16))
        self.lbl_detalhe = ctk.CTkLabel(frm_detalhe, text="Selecione uma ordem para ver o detalhe e as ações.",
                                        font=theme.font_body(12), text_color=theme.TEXT_MUTED, anchor="w", justify="left",
                                        wraplength=900)
        self.lbl_detalhe.pack(fill="x", pady=(0, 6))
        frm_acoes = ctk.CTkFrame(frm_detalhe, fg_color="transparent")
        frm_acoes.pack(fill="x")
        self.btn_fechar = theme.button_primary(frm_acoes, text="Fechar ordem", height=36, width=140, command=self.abrir_tratamento_ordem)
        self.btn_fechar.pack(side="left", padx=(0, 8))
        self.btn_clonar = theme.button_ghost(frm_acoes, text="Clonar", height=36, width=90, command=self.clonar_log)
        self.btn_clonar.pack(side="left", padx=(0, 8))
        self.btn_pdf = theme.button_ghost(frm_acoes, text="Gerar PDF", height=36, width=110, command=self.gerar_pdf_ordem)
        self.btn_pdf.pack(side="left")
        self.btn_anular = theme.button_danger(frm_acoes, text="Anular ordem", height=36, width=120, command=self.anular_ordem)
        self.btn_anular.pack(side="right")

        # TABELA
        frm_conteudo = theme.card(self.parent)
        frm_conteudo.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        colunas = [
            ("id", "Ordem", 96, "w", False), ("data", "Data", 92, "center", False),
            ("projeto", "Projeto", 200, "w"), ("maquina", "Máquina", 160, "w"),
            ("material", "Material", 160, "w"), ("qnt", "Qtd", 70, "e", False),
            ("tempo", "Tempo", 70, "center", False), ("estado", "Estado", 120, "w", False),
        ]
        frm_tab, self.tab_tree = theme.tabela(frm_conteudo, colunas)
        frm_tab.pack(fill="both", expand=True, padx=8, pady=8)
        self._titulos_colunas = {c[0]: c[1] for c in colunas}
        for col in self._titulos_colunas:
            self.tab_tree.heading(col, command=lambda c=col: self._ordenar_por(c))
        self.tab_tree.bind("<Double-1>", self.abrir_tratamento_ordem)
        self.tab_tree.bind("<<TreeviewSelect>>", self._mostrar_detalhe, add="+")
        self._atualizar_botoes = theme.ligar_a_selecao(self.tab_tree, [self.btn_fechar, self.btn_clonar, self.btn_pdf, self.btn_anular])

    # ------------------------------------------------------------------ #
    #  FILTROS                                                             #
    # ------------------------------------------------------------------ #
    def carregar_combos_filtro(self):
        logs = ProducaoService.obter_todos()
        _id_para_nome = MaquinaService.obter_lookup_id_nome()
        nomes_maquinas = set()
        for log in logs:
            nome = ProducaoService.normalizar_maquina(log, _id_para_nome)
            if nome and not nome.startswith("Desconhecida"):
                nomes_maquinas.add(nome)
        self.flt_maq.configure(values=["Todas"] + sorted(nomes_maquinas))
        self.flt_maq.set("Todas")

    def limpar_filtros(self):
        for ent in (self.flt_data_ini, self.flt_data_fim, self.flt_p, self.flt_m, self.flt_cod):
            ent.delete(0, "end")
        self.flt_maq.set("Todas")
        self.flt_estado.set("Todos")
        self.atualizar_tabela()

    def parse_data_segura(self, data_str):
        return _parse_data(data_str)

    def _ordenar_por(self, coluna: str):
        """Inverte a ordenação se a mesma coluna; caso contrário ordena pela nova."""
        if self._sort_col == coluna:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = coluna
            self._sort_asc = True
        for c, titulo in self._titulos_colunas.items():
            seta = (" ↑" if self._sort_asc else " ↓") if c == coluna else ""
            self.tab_tree.heading(c, text=titulo + seta)
        self.atualizar_tabela()

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #
    def _resolver_projeto_material(self, log: dict, pedidos_db: list) -> tuple[str, str]:
        """Devolve (projeto, material) de uma ordem, com suporte a dados legacy."""
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
                    nr = p.get("nr_projeto", "")
                    nom = p.get("nome_projeto", "")
                    proj_str = f"{nr} - {nom}" if nom else str(nr)
                    if proj_str:
                        projetos_set.add(proj_str)
                    for peca in p.get("pecas", []):
                        if peca.get("material"):
                            materiais_set.add(peca["material"])
            return (
                " | ".join(sorted(projetos_set)) if projetos_set else "Sem projeto",
                " | ".join(sorted(materiais_set)) if materiais_set else "N/A",
            )
        # Legacy
        projeto = str(log.get("nr_projeto") or log.get("projeto") or log.get("projeto_nr") or "")
        nome_leg = log.get("nome_projeto", "")
        if projeto and nome_leg:
            projeto = f"{projeto} - {nome_leg}"
        material = str(log.get("material") or log.get("material_tipo") or log.get("filamento") or "")
        return projeto, material

    def _passa_filtros(self, log: dict, projeto: str, material: str, filtros: dict, id_para_nome: dict) -> bool:
        if filtros["proj"] and filtros["proj"] not in projeto.lower():
            return False
        if filtros["mat"] and filtros["mat"] not in material.lower():
            return False
        if filtros["cod"] and filtros["cod"] not in (str(log.get("erro", "")) + " " + str(log.get("nc_codigo", ""))).lower():
            return False
        if filtros["maq"] not in ("Todas", "") and ProducaoService.normalizar_maquina(log, id_para_nome) != filtros["maq"]:
            return False
        if filtros["est"] not in ("Todos", "") and _estado_uniformizado(log) != filtros["est"]:
            return False
        log_data = _parse_data(log.get("data_inicio", ""))
        if log_data:
            if filtros["d_ini"] and log_data < filtros["d_ini"]:
                return False
            if filtros["d_fim"] and log_data > filtros["d_fim"]:
                return False
        return True

    # ------------------------------------------------------------------ #
    #  TABELA                                                              #
    # ------------------------------------------------------------------ #
    def atualizar_tabela(self):
        for i in self.tab_tree.get_children():
            self.tab_tree.delete(i)

        filtros = {
            "proj": self.flt_p.get().lower(),
            "mat": self.flt_m.get().lower(),
            "cod": self.flt_cod.get().lower(),
            "maq": self.flt_maq.get(),
            "est": self.flt_estado.get(),
            "d_ini": _parse_data(self.flt_data_ini.get()),
            "d_fim": _parse_data(self.flt_data_fim.get()),
        }

        logs = ProducaoService.obter_todos()
        pedidos_db = PedidoService.obter_todos()
        id_para_nome = MaquinaService.obter_lookup_id_nome()
        self._logs_por_id = {log.get("id"): log for log in logs}

        _COL_KEY = {
            "id": lambda l: int(l.get("id", 0)),
            "data": lambda l: str(l.get("data_inicio", "")),
            "projeto": lambda l: str(l.get("nr_projeto", "")),
            "maquina": lambda l: ProducaoService.normalizar_maquina(l, id_para_nome),
            "material": lambda l: str(l.get("material", "")),
            "qnt": lambda l: float(str(l.get("quantidade_real") or ProducaoService.estimar_quantidade(l) or l.get("quantidade") or 0).replace(",", ".")),
            "tempo": lambda l: ProducaoService.converter_para_horas(ProducaoService.normalizar_tempo(l)),
            "estado": lambda l: _estado_uniformizado(l),
        }
        key_fn = _COL_KEY.get(self._sort_col, _COL_KEY["data"])
        logs = sorted(logs, key=key_fn, reverse=not self._sort_asc)

        total = sucesso = finalizadas = 0
        total_horas = 0.0
        for log in logs:
            projeto, material = self._resolver_projeto_material(log, pedidos_db)
            if not self._passa_filtros(log, projeto, material, filtros, id_para_nome):
                continue

            estado = _estado_uniformizado(log)
            tempo = ProducaoService.normalizar_tempo(log)
            # Quantidade real quando a ordem já fechou; senão a estimativa (para
            # SLS deriva de altura_cuba/percentagem_po_novo).
            qtd = log.get("quantidade_real") or ProducaoService.estimar_quantidade(log) or log.get("quantidade") or 0.0
            data = str(log.get("data_inicio", "")).split(" ")[0]
            data_fmt = data
            d = _parse_data(data)
            if d:
                data_fmt = d.strftime("%d/%m/%Y")

            self.tab_tree.insert("", "end",
                                 tags=("tag_" + _VARIANTE_ESTADO.get(estado, "neutral"),), values=(
                ProducaoService.formatar_codigo(log.get("id")), data_fmt, projeto,
                ProducaoService.normalizar_maquina(log, id_para_nome), material, qtd, tempo, estado,
            ))

            # KPIs só sobre as ordens listadas
            total += 1
            if estado in ("Concluída", "Entregue"):
                sucesso += 1
            if estado in ("Concluída", "Entregue", "Cancelada"):
                finalizadas += 1
            total_horas += ProducaoService.converter_para_horas(str(tempo))

        # Taxa de sucesso ignora as ordens ainda em andamento
        taxa = (sucesso / finalizadas * 100) if finalizadas > 0 else 0.0
        self.lbl_kpi_total.configure(text=str(total))
        self.lbl_kpi_taxa.configure(text=f"{taxa:.1f}%")
        self.lbl_kpi_horas.configure(text=ProducaoService.converter_para_string(total_horas))
        self._atualizar_botoes()
        self._mostrar_detalhe()

    def _producao_selecionada(self):
        sel = self.tab_tree.selection()
        if not sel:
            return None
        id_reg = ProducaoService.extrair_id(self.tab_tree.item(sel[0])["values"][0])
        return ProducaoService.obter_por_id(id_reg)

    def _mostrar_detalhe(self, event=None):
        """Linha de detalhe da ordem selecionada: quem lançou, quem verificou e
        a NC (antes eram colunas extra que não cabiam na tabela)."""
        log = self._producao_selecionada()
        if not log:
            self.lbl_detalhe.configure(text="Selecione uma ordem para ver o detalhe e as ações.", text_color=theme.TEXT_MUTED)
            return
        partes = [ProducaoService.formatar_codigo(log.get("id"))]
        vinc = log.get("pedidos_vinculados", [])
        if vinc:
            partes.append("pedidos " + ", ".join(PedidoService.formatar_codigo(v) for v in vinc))
        partes.append(f"lançada por {log.get('operador') or log.get('responsavel') or '—'}")
        if log.get("verificado_por"):
            partes.append(f"verificada por {log['verificado_por']} em {str(log.get('data_fecho', ''))[:16]}")
        if log.get("nc_codigo"):
            nc = log["nc_codigo"]
            acoes = NCService.formatar_acoes_aplicadas(log.get("acoes_aplicadas"))
            partes.append(f"NC {nc} {NCService.obter_descricao(nc)}" + (f" — ações: {acoes}" if acoes else " — sem ação corretiva"))
        self.lbl_detalhe.configure(text="  ·  ".join(partes), text_color=theme.TEXT)

    # ------------------------------------------------------------------ #
    #  AÇÕES                                                               #
    # ------------------------------------------------------------------ #
    def gerar_pdf_ordem(self):
        """Gera o PDF da ordem de produção selecionada."""
        producao = self._producao_selecionada()
        if not producao:
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
            theme.toast(self.parent, f"PDF gerado: {caminho}")
        except Exception as e:
            messagebox.showerror("Não foi possível gerar o PDF", str(e))

    def exportar_csv(self):
        caminho_salvar = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not caminho_salvar:
            return
        # Exporta os registos completos por trás das linhas visíveis (respeita
        # os filtros ativos), não só as colunas mostradas.
        ids_visiveis = {ProducaoService.extrair_id(self.tab_tree.item(i)["values"][0]) for i in self.tab_tree.get_children()}
        producoes = [p for p in ProducaoService.obter_todos() if p.get("id") in ids_visiveis]
        if ExportService.exportar_historico_csv(caminho_salvar, producoes, PedidoService.obter_todos()):
            theme.toast(self.parent, f"{len(producoes)} ordens exportadas para CSV.")
        else:
            messagebox.showerror("Não foi possível exportar", "Falha ao gravar o ficheiro CSV.")

    def clonar_log(self):
        producao = self._producao_selecionada()
        if not producao:
            return
        clone = ProducaoService.clonar_producao(producao.get("id"))
        if clone:
            self.carregar_combos_filtro()
            self.atualizar_tabela()
            theme.toast(self.parent, f"Ordem {ProducaoService.formatar_codigo(clone['id'])} criada a partir de "
                                     f"{ProducaoService.formatar_codigo(producao.get('id'))}.")

    def abrir_tratamento_ordem(self, event=None):
        log = self._producao_selecionada()
        if log:
            JanelaFecharOrdem(self.parent.winfo_toplevel(), log, self.salvar_estado_final_ordem)

    def salvar_estado_final_ordem(self, log_atualizado):
        concluir_fecho_ordem(self.parent, log_atualizado)
        self.atualizar_tabela()

    def anular_ordem(self):
        producao = self._producao_selecionada()
        if producao:
            def _depois():
                self.carregar_combos_filtro()
                self.atualizar_tabela()
            JanelaAnularOrdem(self.parent.winfo_toplevel(), producao, _depois)
