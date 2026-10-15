"""
Análise — gráficos sobre os dados de produção (matplotlib embutido no Tk).

Regras de cor: verde/vermelho/teal só quando representam estados (concluída,
cancelada, em curso). Métricas sem estado (horas por máquina, taxa por
tecnologia, ocorrências de NC) usam uma só cor — antes uma máquina aparecia a
vermelho e a SLS com 100% de sucesso também, o que lia como "problema".
"""
from collections import defaultdict
from datetime import datetime, timedelta

import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator

from services.producao_service import ProducaoService
from services.nc_service import NCService
from services.maquina_service import MaquinaService
from gui import theme

_COR_METRICA = theme.ACCENT[0]
_TAM_TEXTO = 9


class AnalyticsTab:
    def __init__(self, parent_frame, f_padrao=None, f_titulo=None, master_app=None):
        self.parent = parent_frame
        self.parent.configure(fg_color=theme.BG)
        self.construir_layout()
        self.atualizar_tabela()   # chamado pelo app ao mudar de tab

    # ------------------------------------------------------------------ #
    #  LAYOUT                                                              #
    # ------------------------------------------------------------------ #
    def construir_layout(self):
        cab = theme.page_header(self.parent, "Indicadores de produção", "Análise")
        cab.pack(fill="x", padx=24, pady=(18, 8))
        ctk.CTkLabel(cab.acoes, text="PERÍODO", font=theme.font_eyebrow(11), text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.cmb_periodo = theme.segmented(cab.acoes, values=["7 dias", "30 dias", "90 dias", "Tudo"],
                                           command=self._ao_mudar_periodo)
        self.cmb_periodo.set("30 dias")
        self.cmb_periodo.pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=19, pady=(0, 16))
        self.scroll.grid_columnconfigure(0, weight=1, uniform="g")
        self.scroll.grid_columnconfigure(1, weight=1, uniform="g")

        self._fig_frames = {}
        self._graficos = {}   # key -> widget do gráfico atual (destruído ao redesenhar)
        posicoes = [
            ("volume", "Ordens por semana", "por estado no fecho", 0, 0),
            ("sucesso", "Taxa de sucesso por tecnologia", "concluídas ÷ (concluídas + canceladas)", 0, 1),
            ("maquinas", "Horas por máquina", "8 máquinas com mais horas", 1, 0),
            ("nc_pareto", "Pareto de não-conformidades", "ocorrências e % acumulada", 1, 1),
        ]
        for key, titulo, sub, row, col in posicoes:
            frm = theme.card(self.scroll)
            frm.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            cab_g = ctk.CTkFrame(frm, fg_color="transparent")
            cab_g.pack(fill="x", padx=14, pady=(12, 0))
            ctk.CTkLabel(cab_g, text=titulo, font=theme.font_body(13, "bold"), text_color=theme.TEXT, anchor="w").pack(fill="x")
            ctk.CTkLabel(cab_g, text=sub, font=theme.font_body(11), text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x")
            self._fig_frames[key] = frm

    # ------------------------------------------------------------------ #
    #  DADOS                                                               #
    # ------------------------------------------------------------------ #
    def _filtrar_por_periodo(self, logs: list) -> list:
        periodo = self.cmb_periodo.get()
        if periodo == "Tudo":
            return logs
        limite = datetime.now() - timedelta(days={"7 dias": 7, "30 dias": 30, "90 dias": 90}[periodo])
        resultado = []
        for log in logs:
            raw = str(log.get("data_inicio", "")).strip()
            dt = None
            # Formato completo primeiro; registos legacy podem não ter hora.
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
            if dt and dt >= limite:
                resultado.append(log)
        return resultado

    def atualizar_tabela(self):
        """Ponto de entrada chamado pelo app ao navegar para esta tab."""
        logs = self._filtrar_por_periodo(ProducaoService.obter_todos())
        id_para_nome = MaquinaService.obter_lookup_id_nome()
        self._desenhar_volume(logs)
        self._desenhar_sucesso_tech(logs)
        self._desenhar_horas_maquina(logs, id_para_nome)
        self._desenhar_nc_pareto(logs)

    def _ao_mudar_periodo(self, _):
        self.atualizar_tabela()

    # ------------------------------------------------------------------ #
    #  GRÁFICOS                                                            #
    # ------------------------------------------------------------------ #
    def _criar_fig(self, key: str):
        """Limpa o frame (mantendo o cabeçalho) e devolve (fig, ax)."""
        anterior = self._graficos.pop(key, None)
        if anterior is not None:
            anterior.destroy()
        fig = Figure(figsize=(5.2, 3.1), dpi=96, facecolor=theme.SURFACE[0])
        ax = fig.add_subplot(111, facecolor=theme.SURFACE[0])
        ax.tick_params(colors=theme.TEXT_MUTED[0], labelsize=_TAM_TEXTO)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(theme.BORDER[0])
        return fig, ax

    def _embed(self, fig, key: str, rect=None):
        fig.tight_layout(pad=1.2, rect=rect)
        canvas = FigureCanvasTkAgg(fig, master=self._fig_frames[key])
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(fill="both", expand=True, padx=8, pady=(4, 12))
        self._graficos[key] = widget

    def _sem_dados(self, fig, ax, key, texto="Sem dados no período"):
        ax.set_axis_off()
        ax.text(0.5, 0.5, texto, ha="center", va="center", color=theme.TEXT_MUTED[0], fontsize=11, transform=ax.transAxes)
        self._embed(fig, key)

    # ── 1. Volume semanal ─────────────────────────────────────────────────
    def _desenhar_volume(self, logs: list):
        fig, ax = self._criar_fig("volume")
        semanas = defaultdict(lambda: {"ok": 0, "bad": 0, "wip": 0})
        for log in logs:
            try:
                dt = datetime.strptime(str(log.get("data_inicio", ""))[:10], "%Y-%m-%d")
            except ValueError:
                continue
            segunda = (dt - timedelta(days=dt.weekday())).date()
            estado = log.get("estado", "")
            if estado in ("Concluída", "Entregue"):
                semanas[segunda]["ok"] += 1
            elif estado in ("Cancelada", "Falha"):
                semanas[segunda]["bad"] += 1
            else:
                semanas[segunda]["wip"] += 1

        if not semanas:
            return self._sem_dados(fig, ax, "volume")

        chaves = sorted(semanas)
        x = range(len(chaves))
        ok = [semanas[k]["ok"] for k in chaves]
        bad = [semanas[k]["bad"] for k in chaves]
        wip = [semanas[k]["wip"] for k in chaves]
        ax.bar(x, ok, color=theme.SUCCESS[0], label="Concluídas", width=0.6)
        ax.bar(x, bad, bottom=ok, color=theme.CRITICAL[0], label="Canceladas", width=0.6)
        ax.bar(x, wip, bottom=[o + b for o, b in zip(ok, bad)], color=theme.TEAL[0], label="Em andamento", width=0.6)
        ax.set_xticks(list(x))
        # Semana identificada pela data de segunda-feira (antes "W37", sem data)
        ax.set_xticklabels([k.strftime("%d/%m") for k in chaves], fontsize=_TAM_TEXTO)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend(fontsize=_TAM_TEXTO, frameon=False, labelcolor=theme.TEXT[0], ncol=3,
                  loc="lower left", bbox_to_anchor=(0, 1.0))
        self._embed(fig, "volume")

    # ── 2. Taxa de sucesso por tecnologia ─────────────────────────────────
    def _desenhar_sucesso_tech(self, logs: list):
        fig, ax = self._criar_fig("sucesso")
        techs = defaultdict(lambda: {"ok": 0, "total": 0})
        for log in logs:
            estado = log.get("estado", "")
            if estado in ("Em Andamento", "A Imprimir"):
                continue
            tech = log.get("tecnologia", "?")
            techs[tech]["total"] += 1
            if estado in ("Concluída", "Entregue"):
                techs[tech]["ok"] += 1

        if not techs:
            return self._sem_dados(fig, ax, "sucesso", "Sem ordens fechadas no período")

        labels = sorted(techs)
        taxas = [techs[t]["ok"] / techs[t]["total"] * 100 if techs[t]["total"] else 0 for t in labels]
        bars = ax.barh(labels, taxas, color=_COR_METRICA, height=0.5)
        ax.set_xlim(0, 112)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
        ax.set_xlabel("%", color=theme.TEXT_MUTED[0], fontsize=_TAM_TEXTO)
        for bar, taxa, t in zip(bars, taxas, labels):
            ax.text(taxa + 1.5, bar.get_y() + bar.get_height() / 2,
                    f"{taxa:.0f}%  ({techs[t]['ok']}/{techs[t]['total']})", va="center", fontsize=_TAM_TEXTO, color=theme.TEXT[0])
        self._embed(fig, "sucesso")

    # ── 3. Horas por máquina ──────────────────────────────────────────────
    def _desenhar_horas_maquina(self, logs: list, id_para_nome: dict):
        fig, ax = self._criar_fig("maquinas")
        horas = defaultdict(float)
        for log in logs:
            nome = ProducaoService.normalizar_maquina(log, id_para_nome)
            if not nome or nome.startswith("Desconhecida"):
                continue
            horas[nome] += ProducaoService.converter_para_horas(ProducaoService.normalizar_tempo(log))

        if not horas:
            return self._sem_dados(fig, ax, "maquinas")

        # Rótulos curtos e sem cortes: o ID do ativo (antes o nome truncado, ex: "rm 3#1")
        nome_para_id = {nome: mid for mid, nome in id_para_nome.items()}
        top = sorted(horas.items(), key=lambda x: -x[1])[:8][::-1]
        labels = [nome_para_id.get(n, n if len(n) <= 14 else n[:13] + "…") for n, _ in top]
        valores = [v for _, v in top]
        bars = ax.barh(labels, valores, color=theme.TEAL[0], height=0.55)
        ax.set_xlim(0, max(valores) * 1.25)
        ax.set_xlabel("horas", color=theme.TEXT_MUTED[0], fontsize=_TAM_TEXTO)
        for bar, v in zip(bars, valores):
            ax.text(v + max(valores) * 0.02, bar.get_y() + bar.get_height() / 2,
                    ProducaoService.converter_para_string(v), va="center", fontsize=_TAM_TEXTO, color=theme.TEXT[0])
        self._embed(fig, "maquinas")

    # ── 4. Pareto de NCs ──────────────────────────────────────────────────
    def _desenhar_nc_pareto(self, logs: list):
        fig, ax = self._criar_fig("nc_pareto")
        contagem = defaultdict(int)
        for log in logs:
            # NC da ordem e NC de cada peça (às vezes só uma peça falha)
            for nc in ProducaoService.ncs_da_producao(log):
                contagem[nc] += 1

        if not contagem:
            return self._sem_dados(fig, ax, "nc_pareto", "Sem não-conformidades no período")

        top = sorted(contagem.items(), key=lambda x: -x[1])
        valores = [v for _, v in top]
        total = sum(valores)
        acumulado = [sum(valores[:i + 1]) / total * 100 for i in range(len(valores))]
        x = range(len(top))
        ax.bar(x, valores, color=_COR_METRICA, width=0.6)
        ax.set_xticks(list(x))
        ax.set_xticklabels([k for k, _ in top], fontsize=_TAM_TEXTO)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylabel("ocorrências", color=theme.TEXT_MUTED[0], fontsize=_TAM_TEXTO)

        ax2 = ax.twinx()
        ax2.plot(x, acumulado, color=theme.WARNING[0], marker="o", markersize=4, linewidth=1.5)
        ax2.axhline(80, color=theme.TEXT_MUTED[0], linestyle="--", linewidth=0.8)
        ax2.set_ylim(0, 110)
        ax2.set_ylabel("% acumulada", color=theme.TEXT_MUTED[0], fontsize=_TAM_TEXTO)
        ax2.tick_params(colors=theme.TEXT_MUTED[0], labelsize=_TAM_TEXTO)
        ax2.spines[["top"]].set_visible(False)
        ax2.spines[["right"]].set_color(theme.BORDER[0])

        # Descrições dos códigos numa linha por baixo (em vez de rótulos cortados no eixo)
        legenda = "   ".join(f"{k}: {NCService.obter_descricao(k)}" for k, _ in top[:4])
        fig.text(0.02, 0.01, legenda, fontsize=8, color=theme.TEXT_MUTED[0], ha="left", va="bottom", wrap=True)
        self._embed(fig, "nc_pareto", rect=(0, 0.1, 1, 1))
