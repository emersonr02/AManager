"""Painel — ecrã inicial. Responde a "o que está a acontecer e o que precisa
de mim hoje?" sem interromper ninguém.

Substitui o antigo pop-up modal "Resumo do Dia" que abria no arranque: os
mesmos dados (ResumoDiarioService) passam a estar sempre visíveis aqui, com
atalhos para onde cada problema se resolve, e o PDF do dia exporta-se daqui."""
import os
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from services.resumo_diario_service import ResumoDiarioService
from services.producao_service import ProducaoService
from services.pedido_service import PedidoService
from services.manutencao_service import ManutencaoService
from services.nc_service import NCService
from gui import theme

# Quantos dias antes do prazo um pedido aberto passa a "requer atenção".
DIAS_AVISO_PRAZO = 2


class PainelTab:
    def __init__(self, parent_frame, f_padrao=None, f_titulo=None, master_app=None):
        self.parent = parent_frame
        self.master_app = master_app
        self.parent.configure(fg_color=theme.BG)
        self.construir_layout()
        self.atualizar()

    # ------------------------------------------------------------------ #
    def _ir(self, tela):
        if self.master_app is not None:
            self.master_app.selecionar_tela(tela)

    def construir_layout(self):
        hoje = theme.data_extensa_pt(datetime.now()).capitalize()
        cab = theme.page_header(self.parent, "Painel do dia", "Painel", hoje)
        cab.pack(fill="x", padx=24, pady=(18, 8))
        theme.button_ghost(cab.acoes, text="Exportar resumo (PDF)", height=34, command=self.exportar_pdf).pack(side="left", padx=(0, 10))
        theme.button_action(cab.acoes, text="+ Nova ordem", height=34,
                            command=lambda: self.master_app and self.master_app.abrir_nova_ordem()).pack(side="left")

        frm_kpi = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_kpi.pack(fill="x", padx=19, pady=(4, 10))
        self.lbl_kpi_em_curso = theme.kpi_card(frm_kpi, "Em curso agora", "0", theme.TEAL)
        self.lbl_kpi_concluidas = theme.kpi_card(frm_kpi, "Concluídas hoje", "0")
        self.lbl_kpi_horas = theme.kpi_card(frm_kpi, "Horas de máquina hoje", "00:00")
        self.lbl_kpi_atencao = theme.kpi_card(frm_kpi, "Requer atenção", "0")

        corpo = ctk.CTkFrame(self.parent, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        corpo.columnconfigure(0, weight=3, uniform="col")
        corpo.columnconfigure(1, weight=2, uniform="col")
        corpo.rowconfigure(0, weight=1)

        # Esquerda: ordens em curso (duplo clique abre o fecho da ordem)
        esq = theme.card(corpo)
        esq.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        cab_esq = ctk.CTkFrame(esq, fg_color="transparent")
        cab_esq.pack(fill="x", padx=16, pady=(12, 6))
        self.lbl_titulo_em_curso = ctk.CTkLabel(cab_esq, text="EM CURSO AGORA", font=theme.font_eyebrow(11),
                                                text_color=theme.TEXT_MUTED)
        self.lbl_titulo_em_curso.pack(side="left")
        ctk.CTkLabel(cab_esq, text="duplo clique para fechar a ordem", font=theme.font_body(11),
                     text_color=theme.TEXT_MUTED).pack(side="right")
        frm_tab, self.tree_em_curso = theme.tabela(esq, [
            ("codigo", "Ordem", 96, "w", False), ("maquina", "Máquina", 150, "w"),
            ("projeto", "Projeto", 90, "w"), ("progresso", "Decorrido / previsto", 150, "center", False)])
        frm_tab.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree_em_curso.bind("<Double-1>", self._abrir_fecho)

        # Direita: o que requer atenção, com atalho para onde se resolve
        dir_ = theme.card(corpo)
        dir_.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(dir_, text="REQUER ATENÇÃO", font=theme.font_eyebrow(11), text_color=theme.TEXT_MUTED,
                     anchor="w").pack(fill="x", padx=16, pady=(12, 6))
        self.lista_atencao = ctk.CTkScrollableFrame(dir_, fg_color="transparent")
        self.lista_atencao.pack(fill="both", expand=True, padx=6, pady=(0, 10))
        self._textos_atencao = []
        self.lista_atencao.bind("<Configure>", self._ajustar_quebra_texto, add="+")

    def _largura_texto_atencao(self):
        try:
            escala = ctk.ScalingTracker.get_widget_scaling(self.lista_atencao)
        except Exception:
            escala = 1.0
        largura = self.lista_atencao.winfo_width()
        return max(200, int(largura / escala) - 30) if largura > 1 else 300

    def _ajustar_quebra_texto(self, event=None):
        largura = self._largura_texto_atencao()
        for lbl in self._textos_atencao:
            if lbl.winfo_exists():
                lbl.configure(wraplength=largura)

    # ------------------------------------------------------------------ #
    def atualizar(self):
        dados = ResumoDiarioService.coletar()
        self._dados = dados
        id_para_nome = dados["id_para_nome"]

        # KPIs
        self.lbl_kpi_em_curso.configure(text=str(len(dados["em_curso_geral"])))
        self.lbl_kpi_concluidas.configure(text=str(len(dados["concluidas"])))
        self.lbl_kpi_horas.configure(text=ProducaoService.converter_para_string(dados["total_horas"]))

        # Em curso
        for i in self.tree_em_curso.get_children():
            self.tree_em_curso.delete(i)
        projetos = {p.get("id"): p.get("nr_projeto", "") for p in PedidoService.obter_todos()}
        self._em_curso_por_item = {}
        for p in dados["em_curso_geral"]:
            vinc = [projetos.get(v, "") for v in p.get("pedidos_vinculados", [])]
            projeto = " | ".join(sorted({v for v in vinc if v})) or "—"
            item = self.tree_em_curso.insert("", "end", tags=("tag_run",), values=(
                ProducaoService.formatar_codigo(p.get("id")),
                ProducaoService.normalizar_maquina(p, id_para_nome),
                projeto,
                self._progresso(p),
            ))
            self._em_curso_por_item[item] = p.get("id")
        self.lbl_titulo_em_curso.configure(text=f"EM CURSO AGORA ({len(dados['em_curso_geral'])})")

        # Requer atenção
        itens = self._itens_atencao(dados)
        for w in self.lista_atencao.winfo_children():
            w.destroy()
        if not itens:
            ctk.CTkLabel(self.lista_atencao, text="Nada a assinalar. Prazos, qualidade, máquinas e manutenção em dia.",
                         font=theme.font_body(12), text_color=theme.SUCCESS, wraplength=320, justify="left",
                         anchor="w").pack(fill="x", padx=10, pady=8)
        self._textos_atencao = []
        for variante, etiqueta, texto, tela in itens:
            # Etiqueta + "Abrir" numa linha, texto por baixo com toda a largura
            # (lado a lado, o texto ficava cortado na coluna estreita).
            bloco = ctk.CTkFrame(self.lista_atencao, fg_color="transparent")
            bloco.pack(fill="x", padx=6, pady=(4, 2))
            topo = ctk.CTkFrame(bloco, fg_color="transparent")
            topo.pack(fill="x")
            theme.pill(topo, etiqueta, variante).pack(side="left")
            if tela:
                ctk.CTkButton(topo, text="Abrir →", width=64, height=24, font=theme.font_body(11, "bold"),
                              fg_color="transparent", hover_color=theme.SURFACE_ALT, text_color=theme.TEAL,
                              command=lambda t=tela: self._ir(t)).pack(side="right")
            lbl = ctk.CTkLabel(bloco, text=texto, font=theme.font_body(12), text_color=theme.TEXT, anchor="w",
                               justify="left", wraplength=self._largura_texto_atencao())
            lbl.pack(fill="x", padx=(2, 0), pady=(2, 4))
            self._textos_atencao.append(lbl)
        self.itens_atencao = itens
        n_criticos = sum(1 for i in itens if i[0] == "bad")
        self.lbl_kpi_atencao.configure(text=str(len(itens)),
                                       text_color=theme.CRITICAL if n_criticos else (theme.WARNING if itens else theme.SUCCESS))

    @staticmethod
    def _progresso(producao):
        tempo_est = ProducaoService.normalizar_tempo(producao)
        try:
            inicio = datetime.strptime(str(producao.get("data_inicio", ""))[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return f"— / {tempo_est}"
        decorrido = max(0.0, (datetime.now() - inicio).total_seconds() / 3600)
        return f"{ProducaoService.converter_para_string(decorrido)} / {tempo_est}"

    @staticmethod
    def _itens_atencao(dados):
        """[(variante, etiqueta, texto, tela_destino)] ordenados por gravidade."""
        itens = []

        # Prazos de pedidos abertos
        for p in PedidoService.obter_todos():
            if p.get("ativo") is False or p.get("estado") not in PedidoService.ESTADOS_ABERTOS:
                continue
            dias = PedidoService.dias_ate_prazo(p)
            if dias is None or dias > DIAS_AVISO_PRAZO:
                continue
            codigo = PedidoService.formatar_codigo(p.get("id"))
            projeto = p.get("nr_projeto", "")
            if dias < 0:
                itens.append(("bad", "Atrasado", f"{codigo} · {projeto} — prazo passou há {-dias} dia(s)", "pedidos"))
            else:
                quando = "hoje" if dias == 0 else ("amanhã" if dias == 1 else f"em {dias} dias")
                itens.append(("warn", "Prazo", f"{codigo} · {projeto} — entrega {quando}", "pedidos"))

        # NCs de hoje sem ação corretiva registada
        for p in dados["com_nc"]:
            if p.get("acoes_aplicadas"):
                continue
            cod = p.get("nc_codigo", "")
            desc = NCService.obter_descricao(cod)
            itens.append(("bad", "NC", f"{ProducaoService.formatar_codigo(p.get('id'))} · {cod} {desc} — sem ação corretiva",
                          "ordens"))

        # Máquinas paradas (desativadas não contam: é um estado intencional)
        for m in dados["maquinas_paradas"]:
            if m.get("estado") == "Desativado":
                continue
            nota = m.get("manutencao", "")
            sufixo = f" — {nota}" if nota and nota != "OK" else ""
            itens.append(("warn", "Parada", f"{m.get('nome', m.get('id'))}{sufixo}", "parque"))

        # Manutenção preventiva atrasada
        for t in ManutencaoService.calcular_proximas_tarefas():
            if t["estado"] == "atrasada":
                itens.append(("bad", "Manutenção", f"{t['maquina_nome']} · {t['tarefa_nome']}", "manutencao"))

        ordem = {"bad": 0, "warn": 1}
        itens.sort(key=lambda i: ordem.get(i[0], 2))
        return itens

    # ------------------------------------------------------------------ #
    def _abrir_fecho(self, event=None):
        sel = self.tree_em_curso.selection()
        if not sel:
            return
        id_reg = self._em_curso_por_item.get(sel[0])
        log = ProducaoService.obter_por_id(id_reg)
        if log:
            from gui.dialogs.fechar_ordem import JanelaFecharOrdem
            from gui.historico_tab import concluir_fecho_ordem
            JanelaFecharOrdem(self.parent.winfo_toplevel(), log,
                              lambda l: (concluir_fecho_ordem(self.parent, l), self.atualizar()))

    def exportar_pdf(self):
        pasta_saida = filedialog.askdirectory(title="Escolher pasta para guardar o resumo do dia")
        if not pasta_saida:
            return
        data_ref = self._dados["data_referencia"]
        caminho = os.path.join(pasta_saida, f"Resumo_Diario_{data_ref}.pdf")
        try:
            from services.pdf_service import PDFService
            PDFService.gerar_resumo_diario(caminho, data_referencia=data_ref)
            theme.toast(self.parent, f"Resumo exportado: {caminho}")
        except Exception as e:
            messagebox.showerror("Não foi possível exportar", str(e))
