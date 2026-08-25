import io
import queue
import threading
from urllib.parse import urlparse
import urllib.request
from PIL import Image
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from services.maquina_service import MaquinaService
from services.producao_service import ProducaoService
from gui.dialogs.logistica_maquina import JanelaLogisticaMaquina
from gui import theme


class ParqueTab:
    def __init__(self, parent_frame, f_padrao, f_titulo):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo
        self.parent.configure(fg_color=theme.BG)

        # Fila thread-safe: threads de download colocam (lbl_widget, CTkImage)
        # aqui; o polling na main thread aplica-as sem bloquear a UI.
        self._fila_imagens: queue.Queue = queue.Queue()

        self.construir_layout()
        self.atualizar_grid_maquinas()
        self._processar_fila_imagens()

    def construir_layout(self):
        theme.page_header(self.parent, "Parque de Máquinas", "Impressoras").pack(
            fill="x", padx=24, pady=(22, 10))
        frm_acoes = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes.pack(fill="x", padx=24, pady=(0, 10))
        theme.button_action(frm_acoes, text="+ Adicionar Ativo",
                            command=self.abrir_formulario_cadastro).pack(side="right")
        self.scroll_container = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        self.scroll_container.pack(fill="both", expand=True, padx=19, pady=(0, 18))

    # ------------------------------------------------------------------ #
    #  GRID DE MÁQUINAS                                                    #
    # ------------------------------------------------------------------ #

    def atualizar_grid_maquinas(self):
        for w in self.scroll_container.winfo_children():
            w.destroy()

        for i in range(4):
            self.scroll_container.grid_columnconfigure(i, weight=1, minsize=240)

        maquinas = MaquinaService.obter_todas()
        id_para_nome = MaquinaService.obter_lookup_id_nome()
        fila_por_maquina = self._construir_fila(id_para_nome)

        row = col = 0
        for m in maquinas:
            producao_ativa = fila_por_maquina.get(m.get("id"))
            self._criar_card(m, row, col, producao_ativa)
            col += 1
            if col > 3:
                col = 0
                row += 1

    def _construir_fila(self, id_para_nome: dict) -> dict:
        """Devolve {id_maquina: producao_dict} para máquinas com job ativo
        (estado 'Em Andamento' ou 'A Imprimir'). Mostra a mais recente em
        caso de dados legacy com mais do que um job 'aberto' na mesma máquina."""
        ativos = {}
        for p in ProducaoService.obter_todos():
            if p.get("estado") not in ("Em Andamento", "A Imprimir"):
                continue
            nome_maquina = ProducaoService.normalizar_maquina(p, id_para_nome)
            mid = p.get("id_maquina") or self._id_por_nome(nome_maquina, id_para_nome)
            if not mid:
                continue
            anterior = ativos.get(mid)
            if anterior is None or p.get("data_inicio", "") > anterior.get("data_inicio", ""):
                ativos[mid] = p
        return ativos

    @staticmethod
    def _id_por_nome(nome: str, id_para_nome: dict) -> str:
        for mid, n in id_para_nome.items():
            if n == nome:
                return mid
        return ""

    # ------------------------------------------------------------------ #
    #  CARD DA MÁQUINA                                                     #
    # ------------------------------------------------------------------ #

    def _criar_card(self, m: dict, row: int, col: int, producao_ativa: dict = None):
        estado = m.get("estado", "Operacional")
        notas  = m.get("manutencao", "OK")
        url    = m.get("url_img", "")

        # O pill reflete o job ativo quando existe — é mais útil saber
        # "está a imprimir" do que apenas "operacional" quando há fila.
        if producao_ativa:
            variante_pill = "run"
            texto_pill = "EM PRODUÇÃO"
        else:
            variante_pill = ("ok" if estado == "Operacional"
                             else "warn" if "Manutenção" in estado
                             else "neutral")
            texto_pill = estado.upper()

        card = ctk.CTkFrame(self.scroll_container, fg_color=theme.SURFACE,
                            corner_radius=theme.RADIUS_M, border_width=1,
                            border_color=(theme.TEAL if producao_ativa else theme.BORDER))
        card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")

        # Placeholder enquanto a imagem carrega
        lbl_img = ctk.CTkLabel(card, text="⏳ A carregar…",
                               font=theme.font_body(10), text_color=theme.TEXT_MUTED)
        lbl_img.pack(pady=(15, 5))

        if url and urlparse(url).scheme in ("http", "https"):
            threading.Thread(
                target=self._download_imagem_bg,
                args=(url, lbl_img),
                daemon=True,
            ).start()
        else:
            lbl_img.configure(text="")

        theme.pill(card, texto_pill, variante_pill).pack(anchor="e", padx=15, pady=(15, 0))
        ctk.CTkLabel(card, text=m.get("id"), font=theme.font_mono(17, "bold"),
                     text_color=theme.ACCENT).pack(anchor="w", padx=15, pady=(8, 0))
        ctk.CTkLabel(card, text=m.get("nome"), font=self.f_padrao,
                     text_color=theme.TEXT).pack(anchor="w", padx=15, pady=(0, 5))
        ctk.CTkLabel(card, text=f"Tecnologia: {m.get('tech')}",
                     font=theme.font_body(11), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=15)

        if producao_ativa:
            self._desenhar_bloco_job_ativo(card, producao_ativa)

        texto_notas = f"🔧 {notas}" if notas != "OK" else "✓ Sistemas OK"
        cor_notas   = theme.WARNING if notas != "OK" else theme.TEXT_MUTED
        ctk.CTkLabel(card, text=texto_notas, font=theme.font_body(12),
                     text_color=cor_notas).pack(anchor="w", padx=15, pady=(10, 15))

        theme.button_ghost(card, text="Editar Ativo", font=theme.font_body(11),
                           height=28,
                           command=lambda idx=m: self.abrir_formulario_edicao(idx)
                           ).pack(fill="x", padx=15, pady=(0, 15))

    def _desenhar_bloco_job_ativo(self, card, producao: dict):
        """Mostra o job em curso: projeto, tempo estimado e barra de
        progresso (calculada a partir de data_inicio vs tempo_estimado)."""
        frm = ctk.CTkFrame(card, fg_color=theme.SURFACE_ALT,
                           corner_radius=theme.RADIUS_S)
        frm.pack(fill="x", padx=15, pady=(8, 0))

        projeto = producao.get("nr_projeto", "") or "Sem projeto"
        vinculos = producao.get("pedidos_vinculados", [])
        if vinculos:
            from services.pedido_service import PedidoService
            pedidos = PedidoService.obter_todos()
            nomes = {p.get("nr_projeto", "") for p in pedidos if p.get("id") in vinculos}
            if nomes:
                projeto = " | ".join(sorted(n for n in nomes if n))

        ctk.CTkLabel(frm, text=f"🖨️ {projeto}", font=theme.font_body(11, "bold"),
                     text_color=theme.TEAL, wraplength=200, justify="left"
                     ).pack(anchor="w", padx=10, pady=(8, 2))

        tempo_est = ProducaoService.normalizar_tempo(producao)
        horas_est = ProducaoService.converter_para_horas(tempo_est)
        progresso, decorrido_str = self._calcular_progresso(
            producao.get("data_inicio", ""), horas_est)

        barra = ctk.CTkProgressBar(frm, height=6, progress_color=theme.TEAL,
                                   fg_color=theme.BORDER)
        barra.set(progresso)
        barra.pack(fill="x", padx=10, pady=(2, 4))

        ctk.CTkLabel(frm, text=f"{decorrido_str} / {tempo_est}h estimado",
                     font=theme.font_mono(9), text_color=theme.TEXT_MUTED
                     ).pack(anchor="w", padx=10, pady=(0, 8))

    @staticmethod
    def _calcular_progresso(data_inicio_str: str, horas_estimadas: float) -> tuple:
        """Calcula a fração decorrida do job (0.0-1.0) e uma string HH:MM
        do tempo já passado desde o início."""
        from datetime import datetime
        if not data_inicio_str or horas_estimadas <= 0:
            return 0.0, "00:00"
        inicio = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                inicio = datetime.strptime(data_inicio_str.strip(), fmt)
                break
            except ValueError:
                continue
        if inicio is None:
            return 0.0, "00:00"
        decorrido_h = max(0, (datetime.now() - inicio).total_seconds() / 3600)
        h = int(decorrido_h)
        mnt = int(round((decorrido_h - h) * 60))
        progresso = min(1.0, decorrido_h / horas_estimadas) if horas_estimadas else 0.0
        return progresso, f"{h:02d}:{mnt:02d}"

    # ------------------------------------------------------------------ #
    #  IMAGENS EM BACKGROUND                                               #
    # ------------------------------------------------------------------ #

    def _download_imagem_bg(self, url: str, lbl_widget):
        """Corre numa thread daemon — faz o download e coloca na fila."""
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))
            self._fila_imagens.put((lbl_widget, ctk_img))
        except Exception:
            self._fila_imagens.put((lbl_widget, None))

    def _processar_fila_imagens(self):
        """Polling na main thread — aplica imagens sem bloquear."""
        try:
            while True:
                lbl, ctk_img = self._fila_imagens.get_nowait()
                if lbl.winfo_exists():
                    if ctk_img:
                        lbl.configure(image=ctk_img, text="")
                    else:
                        lbl.configure(text="🖼️ Sem imagem", image=None)
        except queue.Empty:
            pass
        self.parent.after(150, self._processar_fila_imagens)

    # ------------------------------------------------------------------ #
    #  FORMULÁRIOS                                                         #
    # ------------------------------------------------------------------ #

    def abrir_formulario_cadastro(self):
        JanelaLogisticaMaquina(self.parent.winfo_toplevel(), None,
                               self.atualizar_grid_maquinas, self.f_padrao, self.f_titulo)

    def abrir_formulario_edicao(self, maquina_dados):
        JanelaLogisticaMaquina(self.parent.winfo_toplevel(), maquina_dados,
                               self.atualizar_grid_maquinas, self.f_padrao, self.f_titulo)
