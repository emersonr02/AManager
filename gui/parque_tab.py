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
        row = col = 0
        for m in maquinas:
            self._criar_card(m, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1

    def _criar_card(self, m: dict, row: int, col: int):
        estado = m.get("estado", "Operacional")
        notas  = m.get("manutencao", "OK")
        url    = m.get("url_img", "")

        variante = ("ok" if estado == "Operacional"
                    else "warn" if "Manutenção" in estado
                    else "neutral")

        card = ctk.CTkFrame(self.scroll_container, fg_color=theme.SURFACE,
                            corner_radius=theme.RADIUS_M, border_width=1,
                            border_color=theme.BORDER)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")

        # Placeholder enquanto a imagem carrega
        lbl_img = ctk.CTkLabel(card, text="⏳ A carregar…",
                               font=theme.font_body(10), text_color=theme.TEXT_MUTED)
        lbl_img.pack(pady=(15, 5))

        if url and urlparse(url).scheme in ("http", "https"):
            # Download assíncrono — nunca bloqueia a main thread
            threading.Thread(
                target=self._download_imagem_bg,
                args=(url, lbl_img),
                daemon=True,
            ).start()
        else:
            lbl_img.configure(text="")  # sem imagem, sem ruído

        theme.pill(card, estado.upper(), variante).pack(anchor="e", padx=15, pady=(15, 0))
        ctk.CTkLabel(card, text=m.get("id"), font=theme.font_mono(17, "bold"),
                     text_color=theme.ACCENT).pack(anchor="w", padx=15, pady=(8, 0))
        ctk.CTkLabel(card, text=m.get("nome"), font=self.f_padrao,
                     text_color=theme.TEXT).pack(anchor="w", padx=15, pady=(0, 5))
        ctk.CTkLabel(card, text=f"Tecnologia: {m.get('tech')}",
                     font=theme.font_body(11), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=15)

        texto_notas = f"🔧 {notas}" if notas != "OK" else "✓ Sistemas OK"
        cor_notas   = theme.WARNING if notas != "OK" else theme.TEXT_MUTED
        ctk.CTkLabel(card, text=texto_notas, font=theme.font_body(12),
                     text_color=cor_notas).pack(anchor="w", padx=15, pady=(10, 15))

        theme.button_ghost(card, text="Editar Ativo", font=theme.font_body(11),
                           height=28,
                           command=lambda idx=m: self.abrir_formulario_edicao(idx)
                           ).pack(fill="x", padx=15, pady=(0, 15))

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
            # Falha silenciosa — o placeholder já está no lugar
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
