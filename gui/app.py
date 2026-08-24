import os
import queue
import threading
import customtkinter as ctk
from tkinter import ttk
from config.paths import BASE_DIR, DATA_DIR
from gui import theme

ctk.set_appearance_mode("light")

# Tabs instanciadas apenas quando o utilizador visita pela primeira vez (lazy).
# Evita ler ficheiros da rede no arranque para tabs que nunca são abertas.
_TAB_CLASSES = {}  # preenchido abaixo após os imports dinâmicos


class AppIndustrialI3D(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gestão de Produção i3D | CEiiA")
        self.geometry("1300x800")
        self.configure(fg_color=theme.BG)

        icon_path = os.path.join(BASE_DIR, "logo_ceiia.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.f_padrao = theme.font_body(13)
        self.f_titulo = theme.font_display(18)
        self.bind("<Configure>", self.redimensionar_fontes)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── SIDEBAR ──────────────────────────────────────────────────────
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0,
                                          fg_color=theme.ACCENT_STRONG)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        frm_brand = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        frm_brand.grid(row=0, column=0, padx=20, pady=(28, 34), sticky="w")
        ctk.CTkLabel(frm_brand, text="i3D", text_color="white",
                     font=theme.font_display(22)).pack(side="left")
        ctk.CTkLabel(frm_brand, text="  MES · CEiiA",
                     text_color=theme.SIDEBAR_TEXT_MUTED,
                     font=theme.font_mono(10)).pack(side="left")

        _btn_cfg = dict(fg_color="transparent", text_color=theme.SIDEBAR_TEXT,
                        hover_color=theme.ACCENT_HOVER, anchor="w",
                        font=self.f_padrao, height=38, corner_radius=theme.RADIUS_S)

        self.btn_dash = ctk.CTkButton(self.sidebar_frame, text="📊  Dashboard",
                                      command=lambda: self.selecionar_tela("dash"),
                                      **_btn_cfg)
        self.btn_dash.grid(row=1, column=0, padx=10, pady=3, sticky="ew")

        self.btn_pedidos = ctk.CTkButton(self.sidebar_frame, text="📋  Gestão de Pedidos",
                                         command=lambda: self.selecionar_tela("pedidos"),
                                         **_btn_cfg)
        self.btn_pedidos.grid(row=2, column=0, padx=10, pady=3, sticky="ew")

        self.btn_parque = ctk.CTkButton(self.sidebar_frame, text="🖨️  Impressoras",
                                        command=lambda: self.selecionar_tela("parque"),
                                        **_btn_cfg)
        self.btn_parque.grid(row=3, column=0, padx=10, pady=3, sticky="ew")

        self.btn_producao = ctk.CTkButton(
            self.sidebar_frame, text="➕  Nova Produção",
            command=lambda: self.selecionar_tela("producao"),
            fg_color=theme.TEAL, text_color="white",
            hover_color=theme.TEAL_HOVER, anchor="w",
            font=theme.font_body(13, "bold"), height=38,
            corner_radius=theme.RADIUS_S,
        )
        self.btn_producao.grid(row=4, column=0, padx=10, pady=(18, 3), sticky="ew")

        # Rodapé — estado da rede
        frm_foot = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        frm_foot.grid(row=7, column=0, padx=16, pady=16, sticky="sw")
        self.lbl_status_dot = ctk.CTkLabel(frm_foot, text="●",
                                           text_color=theme.SUCCESS[0],
                                           font=theme.font_body(10))
        self.lbl_status_dot.pack(side="left")
        self.lbl_status_texto = ctk.CTkLabel(frm_foot, text=" Rede CEiiA · a verificar…",
                                             text_color=theme.SIDEBAR_TEXT_MUTED,
                                             font=theme.font_mono(9))
        self.lbl_status_texto.pack(side="left")

        # ── ÁREA DE CONTEÚDO — lazy ───────────────────────────────────────
        # Cada tab só é instanciada na primeira visita; depois apenas
        # o frame é mostrado/ocultado e os dados são refrescados.
        self._frames: dict[str, ctk.CTkFrame] = {}
        self._uis:    dict[str, object]        = {}

        # Mapa nome → (classe, args_extra)
        self._tab_registry = {
            "dash":     ("HistoricoTab", (self,)),
            "pedidos":  ("PedidosTab",   ()),
            "producao": ("ProducaoTab",  (self,)),
            "parque":   ("ParqueTab",    ()),
        }

        # Botão atualmente ativo — para reset com um único .configure()
        self._btn_ativo: ctk.CTkButton | None = None
        self._tela_ativa: str | None = None

        self.selecionar_tela("dash")

        # Verificação periódica da rede
        self._fila_rede: queue.Queue = queue.Queue()
        self._processar_fila_rede()
        self._agendar_verificacao_rede()

    # ── NAVEGAÇÃO ─────────────────────────────────────────────────────────

    def selecionar_tela(self, nome_tela: str):
        # 1. Oculta frame anterior
        if self._tela_ativa and self._tela_ativa in self._frames:
            self._frames[self._tela_ativa].grid_forget()

        # 2. Reset visual do botão anterior (1 operação, não 4)
        if self._btn_ativo:
            if self._btn_ativo is self.btn_producao:
                self._btn_ativo.configure(fg_color=theme.TEAL)
            else:
                self._btn_ativo.configure(fg_color="transparent")

        # 3. Lazy-init: cria a tab só na primeira visita
        if nome_tela not in self._frames:
            self._inicializar_tab(nome_tela)

        # 4. Mostra o frame e refresca os dados
        self._frames[nome_tela].grid(row=0, column=1, sticky="nsew")
        self._refresh_tab(nome_tela)
        self._tela_ativa = nome_tela

        # 5. Destaca botão ativo
        btn_map = {"dash": self.btn_dash, "pedidos": self.btn_pedidos,
                   "parque": self.btn_parque, "producao": self.btn_producao}
        btn = btn_map.get(nome_tela)
        if btn:
            btn.configure(fg_color=theme.TEAL_HOVER if nome_tela == "producao"
                          else theme.ACCENT_HOVER)
            self._btn_ativo = btn

    def _inicializar_tab(self, nome: str):
        """Instancia o frame e a UI de uma tab pela primeira vez."""
        from gui.historico_tab import HistoricoTab
        from gui.pedidos_tab import PedidosTab
        from gui.producao_tab import ProducaoTab
        from gui.parque_tab import ParqueTab
        classes = {"HistoricoTab": HistoricoTab, "PedidosTab": PedidosTab,
                   "ProducaoTab": ProducaoTab, "ParqueTab": ParqueTab}

        cls_name, extra_args = self._tab_registry[nome]
        cls = classes[cls_name]

        frm = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._frames[nome] = frm
        self._uis[nome] = cls(frm, self.f_padrao, self.f_titulo, *extra_args)

    def _refresh_tab(self, nome: str):
        """Refresca os dados quando o utilizador volta a uma tab — garante
        que alterações feitas noutro PC (ficheiros partilhados em rede) são
        visíveis sem reiniciar a app."""
        ui = self._uis.get(nome)
        if ui is None:
            return
        if nome == "dash" and hasattr(ui, "atualizar_tabela"):
            ui.atualizar_tabela()
        elif nome == "pedidos" and hasattr(ui, "atualizar_tabela"):
            ui.atualizar_tabela()
        elif nome == "parque" and hasattr(ui, "atualizar_grid_maquinas"):
            ui.atualizar_grid_maquinas()
        # "producao" não tem dados para refrescar (é um formulário)

    # ── FONTES RESPONSIVAS ────────────────────────────────────────────────

    def redimensionar_fontes(self, event):
        if event.widget is self:
            w = self.winfo_width()
            base = max(11, int(w / 110))
            self.f_padrao.configure(size=base)
            self.f_titulo.configure(size=int(base * 1.3))
            style = ttk.Style()
            style.configure("Treeview", font=("Cascadia Mono", base - 1),
                            rowheight=int(base * 2.2))
            style.configure("Treeview.Heading",
                            font=("Segoe UI", int(base * 0.95), "bold"))

    # ── ESTADO DA REDE ────────────────────────────────────────────────────

    def _agendar_verificacao_rede(self):
        threading.Thread(target=self._testar_acesso_dados_bg, daemon=True).start()
        self.after(15_000, self._agendar_verificacao_rede)

    def _testar_acesso_dados_bg(self):
        self._fila_rede.put(self._pasta_dados_acessivel())

    def _processar_fila_rede(self):
        try:
            while True:
                self._atualizar_indicador_rede(self._fila_rede.get_nowait())
        except queue.Empty:
            pass
        self.after(200, self._processar_fila_rede)

    def _pasta_dados_acessivel(self) -> bool:
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

    def _atualizar_indicador_rede(self, ok: bool):
        if ok:
            self.lbl_status_dot.configure(text_color=theme.SUCCESS[0])
            self.lbl_status_texto.configure(text=" Rede CEiiA · sincronizado")
        else:
            self.lbl_status_dot.configure(text_color=theme.CRITICAL[0])
            self.lbl_status_texto.configure(text=" Rede CEiiA · sem acesso")
