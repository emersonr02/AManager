import io
from urllib.parse import urlparse
import urllib.request
from PIL import Image, ImageTk
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

        self.construir_layout()
        self.atualizar_grid_maquinas()

    def construir_layout(self):
        # 1. HEADER (Título e Botão de Ação)
        theme.page_header(self.parent, "Parque de Máquinas", "Impressoras").pack(fill="x", padx=24, pady=(22, 10))

        frm_acoes_header = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_acoes_header.pack(fill="x", padx=24, pady=(0, 10))
        theme.button_action(frm_acoes_header, text="+ Adicionar Ativo", command=self.abrir_formulario_cadastro).pack(side="right")

        # 2. CONTAINER SCROLLABLE (Onde os Cards vão morar)
        self.scroll_container = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        self.scroll_container.pack(fill="both", expand=True, padx=19, pady=(0, 18))

    def atualizar_grid_maquinas(self):
        for widget in self.scroll_container.winfo_children():
            widget.destroy()

        maquinas = MaquinaService.obter_todas()
        
        for i in range(4):
            self.scroll_container.grid_columnconfigure(i, weight=1, minsize=240)

        row = 0
        col = 0

        for m in maquinas:
            estado = m.get("estado", "Operacional")
            manutencao_notas = m.get("manutencao", "OK")
            url_imagem = m.get("url_img") # Puxa o URL do JSON

            if estado == "Operacional":
                variante_estado = "ok"
            elif "Manutenção" in estado:
                variante_estado = "warn"
            else:
                variante_estado = "neutral"

            # --- CARD PRINCIPAL ---
            card = ctk.CTkFrame(self.scroll_container, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_M, border_width=1, border_color=theme.BORDER)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")

            # --- RENDERIZAR MINIATURA POR URL ---
            if url_imagem and urlparse(url_imagem).scheme in ("http", "https"):
                try:
                    # Faz o download dos bytes da imagem em memória
                    with urllib.request.urlopen(url_imagem, timeout=3) as url_response:
                        img_data = url_response.read()

                    # Processa a imagem com o Pillow e redimensiona para tamanho miniatura (ex: 120x120)
                    img_original = Image.open(io.BytesIO(img_data))
                    ctk_img = ctk.CTkImage(light_image=img_original, dark_image=img_original, size=(120, 120))

                    lbl_img = ctk.CTkLabel(card, image=ctk_img, text="")
                    lbl_img.pack(pady=(15, 5))
                except Exception as e:
                    # Se o URL falhar ou o PC estiver sem rede, mostra um aviso visual discreto em vez de quebrar o app
                    lbl_img_erro = ctk.CTkLabel(card, text="🖼️ Erro ao carregar imagem", font=theme.font_body(10, "normal"), text_color=theme.TEXT_MUTED)
                    lbl_img_erro.pack(pady=(15, 5))
            elif url_imagem:
                lbl_img_erro = ctk.CTkLabel(card, text="🖼️ URL de imagem inválido", font=theme.font_body(10, "normal"), text_color=theme.TEXT_MUTED)
                lbl_img_erro.pack(pady=(15, 5))

            # --- TAG DE STATUS ---
            theme.pill(card, estado.upper(), variante_estado).pack(anchor="e", padx=15, pady=(15, 0))

            # Identificação
            ctk.CTkLabel(card, text=m.get("id"), font=theme.font_mono(17, "bold"), text_color=theme.ACCENT).pack(anchor="w", padx=15, pady=(8, 0))
            ctk.CTkLabel(card, text=m.get("nome"), font=self.f_padrao, text_color=theme.TEXT).pack(anchor="w", padx=15, pady=(0, 5))

            lbl_tech = ctk.CTkLabel(card, text=f"Tecnologia: {m.get('tech')}", font=theme.font_body(11), text_color=theme.TEXT_MUTED)
            lbl_tech.pack(anchor="w", padx=15)

            texto_notas = f"🔧 {manutencao_notas}" if manutencao_notas != "OK" else "✓ Sistemas OK"
            cor_texto_notas = theme.WARNING if manutencao_notas != "OK" else theme.TEXT_MUTED
            lbl_notas = ctk.CTkLabel(card, text=texto_notas, font=theme.font_body(12), text_color=cor_texto_notas)
            lbl_notas.pack(anchor="w", padx=15, pady=(10, 15))

            btn_editar = theme.button_ghost(card, text="Editar Ativo", font=theme.font_body(11), height=28, command=lambda idx=m: self.abrir_formulario_edicao(idx))
            btn_editar.pack(fill="x", padx=15, pady=(0, 15))

            col += 1
            if col > 3:
                col = 0
                row += 1

    def abrir_formulario_cadastro(self):
        JanelaLogisticaMaquina(self.parent.winfo_toplevel(), None, self.atualizar_grid_maquinas, self.f_padrao, self.f_titulo)

    def abrir_formulario_edicao(self, maquina_dados):
        JanelaLogisticaMaquina(self.parent.winfo_toplevel(), maquina_dados, self.atualizar_grid_maquinas, self.f_padrao, self.f_titulo)