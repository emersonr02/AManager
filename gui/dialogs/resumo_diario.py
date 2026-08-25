"""
JanelaResumoDiario — janela que mostra o resumo do dia (produções, NCs,
máquinas paradas). Abre automaticamente uma vez por dia no arranque da
app, e também pode ser aberta manualmente a partir do dashboard.
"""
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from datetime import datetime

from services.resumo_diario_service import ResumoDiarioService
from services.producao_service import ProducaoService
from services.nc_service import NCService
from gui import theme


class JanelaResumoDiario(ctk.CTkToplevel):
    def __init__(self, parent, abertura_automatica: bool = False):
        super().__init__(parent)
        self.abertura_automatica = abertura_automatica

        self.title("Resumo do Dia")
        self.geometry("680x740")
        self.minsize(600, 480)
        self.configure(fg_color=theme.BG)
        self.resizable(False, True)

        self.transient(parent)
        self.grab_set()

        self.dados = ResumoDiarioService.coletar()

        # Se abriu automaticamente no arranque, já marca como visto — não
        # volta a interromper o operador noutro reinício da app hoje.
        if self.abertura_automatica:
            ResumoDiarioService.marcar_visto(self.dados["data_referencia"])

        self.construir_layout()

    # ------------------------------------------------------------------ #
    #  LAYOUT                                                              #
    # ------------------------------------------------------------------ #

    def construir_layout(self):
        # --- RODAPÉ FIXO: botões sempre acessíveis, mesmo que o corpo
        # cresça bastante (muitas NCs, muitas produções em curso, etc.) ---
        frm_rodape = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=0,
                                  border_width=1, border_color=theme.BORDER)
        frm_rodape.pack(side="bottom", fill="x")

        frm_botoes = ctk.CTkFrame(frm_rodape, fg_color="transparent")
        frm_botoes.pack(fill="x", padx=20, pady=16)

        theme.button_ghost(frm_botoes, text="📄 Exportar PDF", height=38,
                           command=self.exportar_pdf).pack(side="left")
        theme.button_primary(frm_botoes, text="Fechar", height=38, width=120,
                             command=self.destroy).pack(side="right")

        # --- CABEÇALHO FIXO ---
        data_fmt = theme.data_extensa_pt(datetime.strptime(self.dados["data_referencia"], "%Y-%m-%d"))
        ctk.CTkLabel(self, text="Resumo do Dia", font=theme.font_display(18),
                     text_color=theme.ACCENT).pack(side="top", pady=(20, 2))
        ctk.CTkLabel(self, text=data_fmt, font=theme.font_body(12),
                     text_color=theme.TEXT_MUTED).pack(side="top", pady=(0, 10))

        # --- CORPO SCROLLÁVEL ---
        corpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
        corpo.pack(side="top", fill="both", expand=True, padx=0, pady=0)

        self._construir_kpis(corpo)
        self._construir_em_curso(corpo)
        self._construir_nao_conformidades(corpo)
        self._construir_maquinas_paradas(corpo)

    # ------------------------------------------------------------------ #
    #  SECÇÕES                                                             #
    # ------------------------------------------------------------------ #

    def _construir_kpis(self, corpo):
        frm_kpis = ctk.CTkFrame(corpo, fg_color="transparent")
        frm_kpis.pack(fill="x", padx=20, pady=(0, 15))

        theme.kpi_card(frm_kpis, "Concluídas", str(len(self.dados["concluidas"])),
                       value_color=theme.SUCCESS[0])
        theme.kpi_card(frm_kpis, "Canceladas", str(len(self.dados["canceladas"])),
                       value_color=theme.CRITICAL[0] if self.dados["canceladas"] else None)
        theme.kpi_card(frm_kpis, "Em Curso", str(len(self.dados["em_curso_hoje"])))
        theme.kpi_card(frm_kpis, "NCs Hoje", str(len(self.dados["com_nc"])),
                       value_color=theme.WARNING[0] if self.dados["com_nc"] else None)

        frm_horas = ctk.CTkFrame(corpo, fg_color=theme.SURFACE_ALT, border_width=1,
                                 border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm_horas.pack(fill="x", padx=20, pady=(0, 15))
        horas_fmt = ProducaoService.converter_para_string(self.dados["total_horas"])
        ctk.CTkLabel(frm_horas, text=f"⏱  Horas de máquina hoje: {horas_fmt}",
                     font=theme.font_body(12, "bold"), text_color=theme.TEXT
                     ).pack(anchor="w", padx=15, pady=10)

    def _construir_em_curso(self, corpo):
        em_curso = self.dados["em_curso_geral"]
        id_para_nome = self.dados["id_para_nome"]

        frm = ctk.CTkFrame(corpo, fg_color=theme.SURFACE, border_width=1,
                           border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(frm, text=f"EM CURSO NESTE MOMENTO ({len(em_curso)})",
                     font=theme.font_eyebrow(10), text_color=theme.TEAL[0]
                     ).pack(anchor="w", padx=15, pady=(12, 6))

        if not em_curso:
            ctk.CTkLabel(frm, text="Nenhuma produção em curso.",
                         font=theme.font_body(11), text_color=theme.TEXT_MUTED
                         ).pack(anchor="w", padx=15, pady=(0, 12))
            return

        for p in em_curso[:15]:
            maquina = ProducaoService.normalizar_maquina(p, id_para_nome)
            codigo = ProducaoService.formatar_codigo(p.get("id"))
            texto = f"{codigo}  ·  {maquina}  ·  início: {p.get('data_inicio', 'N/A')}"
            ctk.CTkLabel(frm, text=texto, font=theme.font_mono(10), text_color=theme.TEXT,
                        anchor="w").pack(anchor="w", padx=15, pady=1)

        if len(em_curso) > 15:
            ctk.CTkLabel(frm, text=f"... e mais {len(em_curso) - 15} produção(ões) em curso.",
                        font=theme.font_body(10), text_color=theme.TEXT_MUTED
                        ).pack(anchor="w", padx=15, pady=(2, 0))

        ctk.CTkLabel(frm, text="", height=1).pack(pady=(0, 8))  # respiro final

    def _construir_nao_conformidades(self, corpo):
        com_nc = self.dados["com_nc"]
        if not com_nc:
            return  # sem NCs hoje — não mostra a secção, evita ruído visual

        frm = ctk.CTkFrame(corpo, fg_color=theme.SURFACE, border_width=1,
                           border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(frm, text=f"NÃO-CONFORMIDADES DE HOJE ({len(com_nc)})",
                     font=theme.font_eyebrow(10), text_color=theme.CRITICAL[0]
                     ).pack(anchor="w", padx=15, pady=(12, 6))

        for p in com_nc:
            codigo = ProducaoService.formatar_codigo(p.get("id"))
            nc_cod = p.get("nc_codigo", "")
            desc = NCService.obter_descricao(nc_cod)
            fechado = bool(p.get("acoes_aplicadas"))

            linha = ctk.CTkFrame(frm, fg_color="transparent")
            linha.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(linha, text=f"{codigo}  ·  {nc_cod} ({desc})",
                        font=theme.font_mono(10), text_color=theme.TEXT
                        ).pack(side="left")
            theme.pill(linha, "CAPA fechado" if fechado else "Sem ação",
                      "ok" if fechado else "bad").pack(side="right")

        ctk.CTkLabel(frm, text="", height=1).pack(pady=(0, 8))

    def _construir_maquinas_paradas(self, corpo):
        paradas = self.dados["maquinas_paradas"]

        frm = ctk.CTkFrame(corpo, fg_color=theme.SURFACE, border_width=1,
                           border_color=theme.BORDER, corner_radius=theme.RADIUS_M)
        frm.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkLabel(frm, text=f"MÁQUINAS FORA DE OPERAÇÃO ({len(paradas)})",
                     font=theme.font_eyebrow(10), text_color=theme.WARNING[0]
                     ).pack(anchor="w", padx=15, pady=(12, 6))

        if not paradas:
            ctk.CTkLabel(frm, text="Todas as máquinas operacionais. ✓",
                         font=theme.font_body(11), text_color=theme.SUCCESS[0]
                         ).pack(anchor="w", padx=15, pady=(0, 12))
            return

        for m in paradas:
            nota = m.get("manutencao", "")
            sufixo = f"  —  {nota}" if nota and nota != "OK" else ""
            texto = f"{m.get('nome', m.get('id', 'N/A'))}  ·  {m.get('estado', '')}{sufixo}"
            ctk.CTkLabel(frm, text=texto, font=theme.font_body(11), text_color=theme.TEXT,
                        anchor="w").pack(anchor="w", padx=15, pady=1)

        ctk.CTkLabel(frm, text="", height=1).pack(pady=(0, 8))

    # ------------------------------------------------------------------ #
    #  AÇÕES                                                               #
    # ------------------------------------------------------------------ #

    def exportar_pdf(self):
        pasta_saida = filedialog.askdirectory(title="Escolher pasta para guardar o resumo")
        if not pasta_saida:
            return

        data_ref = self.dados["data_referencia"]
        caminho = os.path.join(pasta_saida, f"Resumo_Diario_{data_ref}.pdf")

        try:
            from services.pdf_service import PDFService
            PDFService.gerar_resumo_diario(caminho, data_referencia=data_ref)
            messagebox.showinfo("Sucesso", f"Resumo diário exportado:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Erro ao exportar", str(e))
