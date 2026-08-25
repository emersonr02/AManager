"""
Analytics Tab — gráficos interativos sobre os dados de produção.
Usa matplotlib embutido no Tkinter via FigureCanvasTkAgg.
"""
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import defaultdict
from datetime import datetime

from services.producao_service import ProducaoService
from services.pedido_service import PedidoService
from services.nc_service import NCService
from services.maquina_service import MaquinaService
from gui import theme

# Paleta consistente com o tema da app
_CORES = ["#0A7E8C", "#1F9D55", "#C43D26", "#D97706", "#6366F1",
          "#EC4899", "#14B8A6", "#F59E0B", "#8B5CF6", "#10B981"]


class AnalyticsTab:
    def __init__(self, parent_frame, f_padrao, f_titulo, master_app=None):
        self.parent = parent_frame
        self.parent.configure(fg_color=theme.BG)

        self.construir_layout()
        self.atualizar_tabela()   # chamado pelo app ao mudar de tab

    # ------------------------------------------------------------------ #
    #  LAYOUT                                                              #
    # ------------------------------------------------------------------ #

    def construir_layout(self):
        theme.page_header(self.parent, "Análise", "Analytics").pack(
            fill="x", padx=24, pady=(22, 6))

        # Selector de período
        frm_ctrl = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_ctrl.pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkLabel(frm_ctrl, text="PERÍODO", font=theme.font_eyebrow(10),
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.cmb_periodo = ctk.CTkSegmentedButton(
            frm_ctrl,
            values=["7 dias", "30 dias", "90 dias", "Tudo"],
            command=self._ao_mudar_periodo,
            fg_color=theme.SURFACE_ALT,
            selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.SURFACE_ALT,
            text_color=theme.TEXT,
        )
        self.cmb_periodo.set("30 dias")
        self.cmb_periodo.pack(side="left")

        # Canvas scrollável com os 4 gráficos
        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self.scroll.grid_columnconfigure(0, weight=1)
        self.scroll.grid_columnconfigure(1, weight=1)

        # Cria os 4 frames de gráfico
        self._fig_frames = {}
        posicoes = [
            ("volume",    "Volume de Produções por Semana",   0, 0),
            ("sucesso",   "Taxa de Sucesso por Tecnologia",   0, 1),
            ("maquinas",  "Horas por Máquina",                1, 0),
            ("nc_pareto", "Pareto de Não-Conformidades",      1, 1),
        ]
        for key, titulo, row, col in posicoes:
            frm = ctk.CTkFrame(self.scroll, fg_color=theme.SURFACE,
                               corner_radius=theme.RADIUS_M, border_width=1,
                               border_color=theme.BORDER)
            frm.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(frm, text=titulo, font=theme.font_body(12, "bold"),
                         text_color=theme.ACCENT).pack(anchor="w", padx=14, pady=(12, 4))
            self._fig_frames[key] = frm

    # ------------------------------------------------------------------ #
    #  DADOS                                                               #
    # ------------------------------------------------------------------ #

    def _filtrar_por_periodo(self, logs: list) -> list:
        periodo = self.cmb_periodo.get()
        if periodo == "Tudo":
            return logs
        dias = {"7 dias": 7, "30 dias": 30, "90 dias": 90}[periodo]
        from datetime import timedelta
        limite = datetime.now() - timedelta(days=dias)
        resultado = []
        for l in logs:
            raw = l.get("data_inicio", "")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    if datetime.strptime(raw[:len(fmt)], fmt) >= limite:
                        resultado.append(l)
                    break
                except ValueError:
                    continue
        return resultado

    def atualizar_tabela(self):
        """Ponto de entrada chamado pelo app ao navegar para esta tab."""
        logs_todos = ProducaoService.obter_todos()
        logs = self._filtrar_por_periodo(logs_todos)
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
        """Limpa o frame e devolve (fig, ax) prontos a usar."""
        frm = self._fig_frames[key]
        # Remove canvas anterior
        for w in frm.winfo_children():
            if hasattr(w, "get_tk_widget") or str(type(w)) == "<class 'tkinter.Canvas'>":
                w.destroy()
            elif isinstance(w, ctk.CTkLabel):
                continue   # mantém o título
            else:
                try: w.destroy()
                except Exception: pass

        fig = Figure(figsize=(5.2, 3.4), dpi=96, facecolor=theme.SURFACE[0])
        ax  = fig.add_subplot(111, facecolor=theme.SURFACE[0])
        ax.tick_params(colors=theme.TEXT_MUTED[0], labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(theme.BORDER[0])
        fig.tight_layout(pad=1.8)
        return fig, ax

    def _embed(self, fig, key: str):
        canvas = FigureCanvasTkAgg(fig, master=self._fig_frames[key])
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 12))

    # ── 1. Volume semanal ─────────────────────────────────────────────────
    def _desenhar_volume(self, logs: list):
        fig, ax = self._criar_fig("volume")

        semanas: dict = defaultdict(lambda: {"ok": 0, "bad": 0})
        for l in logs:
            raw = l.get("data_inicio", "")
            try:
                dt = datetime.strptime(raw[:10], "%Y-%m-%d")
                key = dt.strftime("%Y-W%W")
            except ValueError:
                continue
            estado = l.get("estado", "")
            if estado in ("Concluída", "Entregue"):
                semanas[key]["ok"] += 1
            elif estado == "Cancelada":
                semanas[key]["bad"] += 1
            else:
                semanas[key].setdefault("wip", 0)
                semanas[key]["wip"] = semanas[key].get("wip", 0) + 1

        if not semanas:
            ax.text(0.5, 0.5, "Sem dados no período", ha="center", va="center",
                    color=theme.TEXT_MUTED[0], transform=ax.transAxes)
            self._embed(fig, "volume"); return

        chaves = sorted(semanas)
        x = range(len(chaves))
        ok  = [semanas[k]["ok"]  for k in chaves]
        bad = [semanas[k]["bad"] for k in chaves]
        wip = [semanas[k].get("wip", 0) for k in chaves]

        ax.bar(x, ok,  color=theme.SUCCESS[0],   label="Concluídas", width=0.6)
        ax.bar(x, bad, bottom=ok, color=theme.CRITICAL[0], label="Canceladas", width=0.6)
        ax.bar(x, wip, bottom=[o+b for o,b in zip(ok,bad)], color=theme.TEAL[0], label="Em Andamento", width=0.6)
        ax.set_xticks(list(x))
        ax.set_xticklabels([k[-3:] for k in chaves], rotation=45, ha="right", fontsize=7)
        ax.legend(fontsize=7, frameon=False, labelcolor=theme.TEXT[0])
        ax.set_ylabel("Produções", color=theme.TEXT_MUTED[0], fontsize=8)
        self._embed(fig, "volume")

    # ── 2. Taxa de sucesso por tecnologia ─────────────────────────────────
    def _desenhar_sucesso_tech(self, logs: list):
        fig, ax = self._criar_fig("sucesso")

        techs: dict = defaultdict(lambda: {"ok": 0, "total": 0})
        for l in logs:
            tech  = l.get("tecnologia", "?")
            estado = l.get("estado", "")
            if estado in ("Em Andamento", "A Imprimir"): continue
            techs[tech]["total"] += 1
            if estado in ("Concluída", "Entregue"):
                techs[tech]["ok"] += 1

        if not techs:
            ax.text(0.5, 0.5, "Sem dados no período", ha="center", va="center",
                    color=theme.TEXT_MUTED[0], transform=ax.transAxes)
            self._embed(fig, "sucesso"); return

        labels = sorted(techs)
        taxas  = [techs[t]["ok"] / techs[t]["total"] * 100 if techs[t]["total"] else 0
                  for t in labels]
        bars = ax.barh(labels, taxas, color=_CORES[:len(labels)], height=0.5)
        ax.set_xlim(0, 105)
        ax.set_xlabel("Taxa de sucesso (%)", color=theme.TEXT_MUTED[0], fontsize=8)
        for bar, taxa in zip(bars, taxas):
            ax.text(taxa + 1, bar.get_y() + bar.get_height()/2,
                    f"{taxa:.1f}%", va="center", fontsize=9, color=theme.TEXT[0])
        self._embed(fig, "sucesso")

    # ── 3. Horas por máquina ──────────────────────────────────────────────
    def _desenhar_horas_maquina(self, logs: list, id_para_nome: dict):
        fig, ax = self._criar_fig("maquinas")

        horas: dict = defaultdict(float)
        for l in logs:
            nome = ProducaoService.normalizar_maquina(l, id_para_nome)
            if not nome or nome.startswith("Desconhecida"): continue
            horas[nome] += ProducaoService.converter_para_horas(
                ProducaoService.normalizar_tempo(l))

        if not horas:
            ax.text(0.5, 0.5, "Sem dados no período", ha="center", va="center",
                    color=theme.TEXT_MUTED[0], transform=ax.transAxes)
            self._embed(fig, "maquinas"); return

        # Top 8 máquinas
        top = sorted(horas.items(), key=lambda x: -x[1])[:8]
        labels = [t[0].replace("Bambu Lab ", "BL ").replace("3D Systems ", "").replace(" #", "#") for t in top]
        valores = [t[1] for t in top]
        bars = ax.barh(labels, valores, color=_CORES[:len(labels)], height=0.55)
        ax.set_xlabel("Horas totais", color=theme.TEXT_MUTED[0], fontsize=8)
        for bar, v in zip(bars, valores):
            ax.text(v + 0.3, bar.get_y() + bar.get_height()/2,
                    ProducaoService.converter_para_string(v),
                    va="center", fontsize=8, color=theme.TEXT[0])
        self._embed(fig, "maquinas")

    # ── 4. Pareto de NCs ──────────────────────────────────────────────────
    def _desenhar_nc_pareto(self, logs: list):
        fig, ax = self._criar_fig("nc_pareto")
        ax2 = ax.twinx()

        contagem: dict = defaultdict(int)
        for l in logs:
            nc = l.get("nc_codigo", "")
            if nc: contagem[nc] += 1

        if not contagem:
            ax.text(0.5, 0.5, "Sem NCs no período 🎉", ha="center", va="center",
                    color=theme.SUCCESS[0], fontsize=11, transform=ax.transAxes)
            ax2.set_visible(False)
            self._embed(fig, "nc_pareto"); return

        top = sorted(contagem.items(), key=lambda x: -x[1])
        labels = [f"{k}\n{NCService.obter_descricao(k)[:18]}" for k, _ in top]
        valores = [v for _, v in top]
        total = sum(valores)
        acumulado = [sum(valores[:i+1]) / total * 100 for i in range(len(valores))]

        x = range(len(top))
        ax.bar(x, valores, color=_CORES[:len(top)], width=0.6)
        ax2.plot(x, acumulado, color=theme.ACCENT[0], marker="o",
                 markersize=4, linewidth=1.5)
        ax2.axhline(80, color=theme.TEXT_MUTED[0], linestyle="--", linewidth=0.8)
        ax2.set_ylim(0, 110)
        ax2.set_ylabel("% acumulada", color=theme.TEXT_MUTED[0], fontsize=8)
        ax2.tick_params(colors=theme.TEXT_MUTED[0], labelsize=8)
        ax2.spines[["top"]].set_visible(False)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=7)
        ax.set_ylabel("Ocorrências", color=theme.TEXT_MUTED[0], fontsize=8)
        self._embed(fig, "nc_pareto")
