import os
import customtkinter as ctk
from tkinter import ttk
from config.paths import BASE_DIR
from gui import theme

from gui.pedidos_tab import PedidosTab
from gui.producao_tab import ProducaoTab
from gui.historico_tab import HistoricoTab
from gui.parque_tab import ParqueTab

ctk.set_appearance_mode("light")

class AppIndustrialI3D(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gestão de Produção i3D | CEiiA")
        self.geometry("1300x800")
        self.configure(fg_color=theme.BG)

        icon_path = os.path.join(BASE_DIR, "logo_ceiia.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # Objetos de Fonte Dinâmica
        self.f_padrao = theme.font_body(13)
        self.f_titulo = theme.font_display(18)
        self.bind("<Configure>", self.redimensionar_fontes)

        # --- LAYOUT PRINCIPAL (GRID) ---
        # Configura a janela para ter 1 linha e 2 colunas
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1) # Apenas a coluna 1 (conteúdo) expande

        # --- MENU LATERAL (SIDEBAR) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=theme.ACCENT_STRONG)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        frm_brand = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        frm_brand.grid(row=0, column=0, padx=20, pady=(28, 34), sticky="w")
        ctk.CTkLabel(frm_brand, text="i3D", text_color="white", font=theme.font_display(22)).pack(side="left")
        ctk.CTkLabel(frm_brand, text="  MES · CEiiA", text_color=theme.SIDEBAR_TEXT_MUTED, font=theme.font_mono(10)).pack(side="left")

        # --- CONFIGURAÇÃO DOS BOTÕES DO MENU LATERAL ---

        # Estilo padrão para os botões de navegação normais
        config_btn_padrao = {
            "fg_color": "transparent",
            "text_color": theme.SIDEBAR_TEXT,
            "hover_color": theme.ACCENT_HOVER,
            "anchor": "w",
            "font": self.f_padrao,
            "height": 38,
            "corner_radius": theme.RADIUS_S,
        }

        # 1. Dashboard
        self.btn_dash = ctk.CTkButton(self.sidebar_frame, text="📊  Dashboard", command=lambda: self.selecionar_tela("dash"), **config_btn_padrao)
        self.btn_dash.grid(row=1, column=0, padx=10, pady=3, sticky="ew")

        # 2. Gestão de Pedidos
        self.btn_pedidos = ctk.CTkButton(self.sidebar_frame, text="📋  Gestão de Pedidos", command=lambda: self.selecionar_tela("pedidos"), **config_btn_padrao)
        self.btn_pedidos.grid(row=2, column=0, padx=10, pady=3, sticky="ew")

        # 3. Impressoras
        self.btn_parque = ctk.CTkButton(self.sidebar_frame, text="🖨️  Impressoras", command=lambda: self.selecionar_tela("parque"), **config_btn_padrao)
        self.btn_parque.grid(row=3, column=0, padx=10, pady=3, sticky="ew")

        # 4. Nova Produção (Botão de Ação com Cor de Destaque)
        self.btn_producao = ctk.CTkButton(
            self.sidebar_frame,
            text="➕  Nova Produção",
            command=lambda: self.selecionar_tela("producao"),
            fg_color=theme.TEAL,
            text_color="white",
            hover_color=theme.TEAL_HOVER,
            anchor="w",
            font=theme.font_body(13, "bold"),
            height=38,
            corner_radius=theme.RADIUS_S,
        )
        self.btn_producao.grid(row=4, column=0, padx=10, pady=(18, 3), sticky="ew") # Espaçamento extra acima para isolar o botão de ação

        # --- RODAPÉ: ESTADO DA REDE ---
        frm_foot = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        frm_foot.grid(row=7, column=0, padx=16, pady=16, sticky="sw")
        self.lbl_status_dot = ctk.CTkLabel(frm_foot, text="●", text_color=theme.SUCCESS[0], font=theme.font_body(10))
        self.lbl_status_dot.pack(side="left")
        ctk.CTkLabel(frm_foot, text=" Rede CEiiA · sincronizado", text_color=theme.SIDEBAR_TEXT_MUTED, font=theme.font_mono(9)).pack(side="left")

        # --- ÁREA DE CONTEÚDO CENTRAL ---
        # Criamos um frame vazio (container) para cada tela
        self.frame_dash = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_pedidos = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_producao = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frame_parque = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")

        # Instanciamos as UIs passando os seus respectivos containers
        self.historico_ui = HistoricoTab(self.frame_dash, self.f_padrao, self.f_titulo, self)
        self.pedidos_ui = PedidosTab(self.frame_pedidos, self.f_padrao, self.f_titulo)
        self.producao_ui = ProducaoTab(self.frame_producao, self.f_padrao, self.f_titulo, self)
        self.parque_ui = ParqueTab(self.frame_parque, self.f_padrao, self.f_titulo)

        # Iniciar a aplicação mostrando o Dashboard
        self.selecionar_tela("dash")

    def selecionar_tela(self, nome_tela):
        # 1. Oculta todos os frames principais
        self.frame_dash.grid_forget()
        self.frame_pedidos.grid_forget()
        self.frame_producao.grid_forget()
        self.frame_parque.grid_forget()

        # 2. Reseta a cor dos botões normais de navegação
        cor_padrao = {"fg_color": "transparent"}
        self.btn_dash.configure(**cor_padrao)
        self.btn_pedidos.configure(**cor_padrao)
        self.btn_parque.configure(**cor_padrao)

        # Reseta o botão de Nova Produção para a cor original dele
        self.btn_producao.configure(fg_color=theme.TEAL)

        # 3. Exibe o frame selecionado e altera o estado visual do botão ativo
        cor_ativo = {"fg_color": theme.ACCENT_HOVER}

        if nome_tela == "dash":
            self.frame_dash.grid(row=0, column=1, sticky="nsew")
            self.btn_dash.configure(**cor_ativo)
        elif nome_tela == "pedidos":
            self.frame_pedidos.grid(row=0, column=1, sticky="nsew")
            self.btn_pedidos.configure(**cor_ativo)
        elif nome_tela == "parque":
            self.frame_parque.grid(row=0, column=1, sticky="nsew")
            self.btn_parque.configure(**cor_ativo)
        elif nome_tela == "producao":
            self.frame_producao.grid(row=0, column=1, sticky="nsew")
            # Quando estiver na tela de produção, o botão ganha um destaque de seleção diferente
            self.btn_producao.configure(fg_color=theme.TEAL_HOVER)

    def redimensionar_fontes(self, event):
        if event.widget == self:
            w = self.winfo_width()
            base = max(11, int(w / 110))
            self.f_padrao.configure(size=base)
            self.f_titulo.configure(size=int(base * 1.3))
            
            style = ttk.Style()
            # Corpo em monoespaçada: as tabelas são sobretudo dados (IDs, datas, tempos,
            # quantidades) — alinhamento tabular ajuda a ler/comparar valores rapidamente.
            style.configure("Treeview", font=("Cascadia Mono", base - 1), rowheight=int(base * 2.2))
            style.configure("Treeview.Heading", font=("Segoe UI", int(base * 0.95), "bold"))