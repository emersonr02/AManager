import io
from urllib.parse import urlparse
import urllib.request
from PIL import Image, ImageTk
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from services.maquina_service import MaquinaService
from gui.dialogs.logistica_maquina import JanelaLogisticaMaquina

class ParqueTab:
    def __init__(self, parent_frame, f_padrao, f_titulo):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.f_titulo = f_titulo

        # Fundo cinza claro para destacar os cartões
        self.parent.configure(fg_color="#f0f2f5")

        self.construir_layout()
        self.atualizar_grid_maquinas()

    def construir_layout(self):
        # 1. HEADER (Título e Botão de Ação)
        frm_header = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(frm_header, text="Parque de Impressoras", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1f538d").pack(side="left")
        ctk.CTkButton(frm_header, text="+ Adicionar Ativo", fg_color="#1f538d", text_color="white", font=self.f_padrao, command=self.abrir_formulario_cadastro).pack(side="right")

        # 2. CONTAINER SCROLLABLE (Onde os Cards vão morar)
        # Substitui a Treeview antiga por um container moderno com scroll nativo
        self.scroll_container = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        self.scroll_container.pack(fill="both", expand=True, padx=15, pady=10)

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
                cor_status = "#28a745"
                bg_status_light = "#e8f5e9"
            elif "Manutenção" in estado:
                cor_status = "#dc3545"
                bg_status_light = "#fbe9e7"
            else:
                cor_status = "#6c757d"
                bg_status_light = "#f5f5f5"

            # --- CARD PRINCIPAL ---
            card = ctk.CTkFrame(self.scroll_container, fg_color="white", corner_radius=12, border_width=1, border_color="#e0e0e0")
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
                    lbl_img_erro = ctk.CTkLabel(card, text="🖼️ Erro ao carregar imagem", font=("Arial", 10, "italic"), text_color="gray")
                    lbl_img_erro.pack(pady=(15, 5))
            elif url_imagem:
                lbl_img_erro = ctk.CTkLabel(card, text="🖼️ URL de imagem inválido", font=("Arial", 10, "italic"), text_color="gray")
                lbl_img_erro.pack(pady=(15, 5))

            # --- TAG DE STATUS ---
            lbl_status = ctk.CTkLabel(card, text=estado.upper(), font=ctk.CTkFont(size=10, weight="bold"), text_color=cor_status, fg_color=bg_status_light, corner_radius=6)
            lbl_status.pack(anchor="e", padx=15, pady=(5, 0))

            # Identificação
            ctk.CTkLabel(card, text=m.get("id"), font=ctk.CTkFont(size=18, weight="bold"), text_color="#1f538d").pack(anchor="w", padx=15)
            ctk.CTkLabel(card, text=m.get("nome"), font=self.f_padrao, text_color="black").pack(anchor="w", padx=15, pady=(0, 5))
            
            lbl_tech = ctk.CTkLabel(card, text=f"Tecnologia: {m.get('tech')}", font=ctk.CTkFont(size=11), text_color="gray50")
            lbl_tech.pack(anchor="w", padx=15)

            texto_notas = f"🔧 {manutencao_notas}" if manutencao_notas != "OK" else "✓ Sistemas OK"
            cor_texto_notas = "#dc3545" if manutencao_notas != "OK" else "gray40"
            lbl_notas = ctk.CTkLabel(card, text=texto_notas, font=("Arial", 12, "italic"), text_color=cor_texto_notas)
            lbl_notas.pack(anchor="w", padx=15, pady=(10, 15))

            btn_editar = ctk.CTkButton(card, text="Editar Ativo", font=ctk.CTkFont(size=11), fg_color="#f0f2f5", text_color="black", hover_color="#e0e0e0", height=28, command=lambda idx=m: self.abrir_formulario_edicao(idx))
            btn_editar.pack(fill="x", padx=15, pady=(0, 15))

            col += 1
            if col > 3:
                col = 0
                row += 1

    def abrir_formulario_cadastro(self):
        JanelaLogisticaMaquina(self.parent.winfo_toplevel(), None, self.atualizar_grid_maquinas, self.f_padrao, self.f_titulo)

    def abrir_formulario_edicao(self, maquina_dados):
        JanelaLogisticaMaquina(self.parent.winfo_toplevel(), maquina_dados, self.atualizar_grid_maquinas, self.f_padrao, self.f_titulo)