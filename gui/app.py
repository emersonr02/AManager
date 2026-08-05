import os
import queue
import threading
import customtkinter as ctk
from tkinter import ttk
from config.paths import BASE_DIR, DATA_DIR
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
        self.lbl_status_texto = ctk.CTkLabel(frm_foot, text=" Rede CEiiA · a verificar…", text_color=theme.SIDEBAR_TEXT_MUTED, font=theme.font_mono(9))
        self.lbl_status_texto.pack(side="left")

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

        # Verificação periódica de acesso à pasta de dados (rede)
        self._fila_rede = queue.Queue()
        self._processar_fila_rede()
        self._agendar_verificacao_rede()

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

    # --- ESTADO DA REDE (rodapé da sidebar) ---
    # Nota de concorrência: Tkinter não é thread-safe — a thread de fundo nunca
    # chama métodos do Tk (nem `self.after`); só faz I/O puro e põe o resultado
    # numa queue.Queue (essa sim, segura entre threads). Quem lê a fila e mexe em
    # widgets é sempre a thread principal, através do polling de `_processar_fila_rede`.
    def _agendar_verificacao_rede(self):
        """Testa o acesso à pasta de dados (potencialmente numa unidade de rede) numa
        thread à parte, para uma rede lenta/em baixo nunca bloquear a interface."""
        threading.Thread(target=self._testar_acesso_dados_bg, daemon=True).start()
        self.after(15000, self._agendar_verificacao_rede)

    def _testar_acesso_dados_bg(self):
        ok = self._pasta_dados_acessivel()
        self._fila_rede.put(ok)

    def _processar_fila_rede(self):
        try:
            while True:
                ok = self._fila_rede.get_nowait()
                self._atualizar_indicador_rede(ok)
        except queue.Empty:
            pass
        self.after(200, self._processar_fila_rede)

    def _pasta_dados_acessivel(self):
        """Confirma escrita real (não só que o caminho 'existe'), com um ficheiro
        marcador próprio do processo para não colidir com outros postos na rede."""
        marcador = os.path.join(DATA_DIR, f".rede_ok_{os.getpid()}")
        try:
            if not os.path.isdir(DATA_DIR):
                return False
            with open(marcador, "w") as f:
                f.write("ok")
            os.remove(marcador)
            return True
        except OSError:
            return False

    def _atualizar_indicador_rede(self, ok):
        if ok:
            self.lbl_status_dot.configure(text_color=theme.SUCCESS[0])
            self.lbl_status_texto.configure(text=" Rede CEiiA · sincronizado")
        else:
            self.lbl_status_dot.configure(text_color=theme.CRITICAL[0])
            self.lbl_status_texto.configure(text=" Rede CEiiA · sem acesso")