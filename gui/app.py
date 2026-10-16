import os
import queue
import threading
from datetime import datetime
import customtkinter as ctk
from config.paths import BASE_DIR, DATA_DIR
from config.versao import obter_versao
from gui import theme
from services.backup_service import BackupService

ctk.set_appearance_mode("light")

# Cor do item ativo da navegação — distinta do fundo da sidebar (antes o ativo
# usava ACCENT_HOVER, que é a MESMA cor do fundo, e não se via qual estava ativo).
_NAV_ATIVO = "#1C4A72"
_NAV_HOVER = "#143857"

# Ecrãs da navegação principal: (chave, rótulo). "producao" (Nova ordem) não
# está aqui: é uma ação, aberta a partir de Painel, Ordens e Máquinas.
_NAVEGACAO = [
    ("painel", "Painel"),
    ("ordens", "Ordens de produção"),
    ("pedidos", "Pedidos"),
    ("parque", "Máquinas"),
    ("manutencao", "Manutenção"),
    ("analytics", "Análise"),
]


class AppIndustrialI3D(ctk.CTk):
    def __init__(self):
        super().__init__()
        # No executável, a versão (data e commit do build) aparece no título:
        # mostra logo se todos os PCs estão a usar o mesmo .exe.
        versao = obter_versao()
        self.title("Gestão de Produção i3D | CEiiA" + (f"  ·  v{versao}" if versao else ""))
        # Nunca maior do que o ecrã (já descontando a escala do Windows): num
        # portátil 1366x768 a 125%, 1300x800 ocupava 1625x1000 px físicos.
        largura, altura = theme.dimensionar_janela(self, 1300, 800, fracao_altura=0.88)
        self.minsize(min(900, largura), min(520, altura))
        self.configure(fg_color=theme.BG)

        icon_path = os.path.join(BASE_DIR, "logo_ceiia.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.f_padrao = theme.font_body(13)
        self.f_titulo = theme.font_display(17)
        self.bind("<Configure>", self.redimensionar_fontes)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── SIDEBAR ──────────────────────────────────────────────────────
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0,
                                          fg_color=theme.ACCENT_STRONG)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        frm_brand = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        frm_brand.pack(fill="x", padx=20, pady=(24, 26))
        ctk.CTkLabel(frm_brand, text="i3D", text_color="white",
                     font=theme.font_display(22)).pack(side="left")
        ctk.CTkLabel(frm_brand, text="  MES · CEiiA",
                     text_color=theme.SIDEBAR_TEXT_MUTED,
                     font=theme.font_body(11)).pack(side="left", pady=(6, 0))

        _btn_cfg = dict(fg_color="transparent", text_color=theme.SIDEBAR_TEXT,
                        hover_color=_NAV_HOVER, anchor="w",
                        font=theme.font_body(13), height=38, corner_radius=theme.RADIUS_S)

        self._botoes_nav: dict[str, ctk.CTkButton] = {}
        for chave, rotulo in _NAVEGACAO:
            btn = ctk.CTkButton(self.sidebar_frame, text=rotulo,
                                command=lambda c=chave: self.selecionar_tela(c), **_btn_cfg)
            btn.pack(fill="x", padx=10, pady=2)
            self._botoes_nav[chave] = btn

        # Rodapé — estado da rede + estado do backup automático
        frm_foot = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        frm_foot.pack(side="bottom", fill="x", padx=16, pady=16)

        frm_rede = ctk.CTkFrame(frm_foot, fg_color="transparent")
        frm_rede.pack(anchor="w")
        self.lbl_status_dot = ctk.CTkLabel(frm_rede, text="●",
                                           text_color=theme.SUCCESS[1],
                                           font=theme.font_body(11))
        self.lbl_status_dot.pack(side="left")
        self.lbl_status_texto = ctk.CTkLabel(frm_rede, text=" Pasta de dados · a verificar…",
                                             text_color=theme.SIDEBAR_TEXT_MUTED,
                                             font=theme.font_body(11))
        self.lbl_status_texto.pack(side="left")

        self.lbl_backup_texto = ctk.CTkLabel(frm_foot, text="Backup · a verificar…",
                                             text_color=theme.SIDEBAR_TEXT_MUTED,
                                             font=theme.font_body(11))
        self.lbl_backup_texto.pack(anchor="w", pady=(2, 0))

        # Configuração fica separada da navegação diária, por cima do rodapé.
        btn_cfg = ctk.CTkButton(self.sidebar_frame, text="Configuração",
                                command=lambda: self.selecionar_tela("configuracao"), **_btn_cfg)
        btn_cfg.pack(side="bottom", fill="x", padx=10, pady=(0, 8))
        self._botoes_nav["configuracao"] = btn_cfg

        # Atalhos de teclado para os ecrãs mais usados
        self.bind_all("<Control-n>", lambda e: self.abrir_nova_ordem())
        self.bind_all("<F5>", lambda e: self._tela_ativa and self._refresh_tab(self._tela_ativa))

        # ── ÁREA DE CONTEÚDO — lazy ───────────────────────────────────────
        # Cada tab só é instanciada na primeira visita; depois apenas
        # o frame é mostrado/ocultado e os dados são refrescados.
        self._frames: dict[str, ctk.CTkFrame] = {}
        self._uis: dict[str, object] = {}

        # Mapa nome → (módulo, classe, recebe_master_app)
        self._tab_registry = {
            "painel":       ("gui.painel_tab", "PainelTab"),
            "ordens":       ("gui.historico_tab", "HistoricoTab"),
            "pedidos":      ("gui.pedidos_tab", "PedidosTab"),
            "producao":     ("gui.producao_tab", "ProducaoTab"),
            "parque":       ("gui.parque_tab", "ParqueTab"),
            "analytics":    ("gui.analytics_tab", "AnalyticsTab"),
            "manutencao":   ("gui.manutencao_tab", "ManutencaoTab"),
            "configuracao": ("gui.configuracao_tab", "ConfiguracaoTab"),
        }

        self._btn_ativo: ctk.CTkButton | None = None
        self._tela_ativa: str | None = None

        self.selecionar_tela("painel")

        # Verificação periódica da rede
        self._fila_rede: queue.Queue = queue.Queue()
        self._processar_fila_rede()
        self._agendar_verificacao_rede()

        # Backup automático diário — corre uma vez no arranque, em
        # background, sem bloquear a UI. Idempotente: não duplica backups
        # se a app for reiniciada várias vezes no mesmo dia.
        self._fila_backup: queue.Queue = queue.Queue()
        self._processar_fila_backup()
        threading.Thread(target=self._executar_backup_inicial_bg, daemon=True).start()

        # O antigo pop-up "Resumo do Dia" no arranque deixou de existir: o Painel
        # (ecrã inicial) mostra a mesma informação sem interromper o operador, e
        # exporta o mesmo PDF.

    # ── NAVEGAÇÃO ─────────────────────────────────────────────────────────

    def selecionar_tela(self, nome_tela: str):
        # 1. Oculta frame anterior
        if self._tela_ativa and self._tela_ativa in self._frames:
            self._frames[self._tela_ativa].grid_forget()

        # 2. Lazy-init: cria a tab só na primeira visita
        if nome_tela not in self._frames:
            self._inicializar_tab(nome_tela)

        # 3. Mostra o frame e refresca os dados
        self._frames[nome_tela].grid(row=0, column=1, sticky="nsew")
        self._tela_ativa = nome_tela
        self._refresh_tab(nome_tela)

        # 4. Destaca o item da navegação (Nova ordem pertence a "Ordens")
        if self._btn_ativo is not None:
            self._btn_ativo.configure(fg_color="transparent", font=theme.font_body(13))
        btn = self._botoes_nav.get("ordens" if nome_tela == "producao" else nome_tela)
        if btn is not None:
            btn.configure(fg_color=_NAV_ATIVO, font=theme.font_body(13, "bold"))
            self._btn_ativo = btn

    def abrir_nova_ordem(self, tecnologia: str = None, maquina: str = None):
        """Abre o formulário de nova ordem de produção, opcionalmente já com a
        tecnologia/máquina escolhidas (ex: botão "Iniciar ordem" de um cartão)."""
        self.selecionar_tela("producao")
        ui = self._uis.get("producao")
        if ui is not None and hasattr(ui, "preselecionar"):
            ui.preselecionar(tecnologia, maquina)

    def _inicializar_tab(self, nome: str):
        """Instancia o frame e a UI de uma tab pela primeira vez."""
        import importlib
        modulo, classe = self._tab_registry[nome]
        cls = getattr(importlib.import_module(modulo), classe)

        frm = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._frames[nome] = frm
        self._uis[nome] = cls(frm, self.f_padrao, self.f_titulo, self)

    def _refresh_tab(self, nome: str):
        """Refresca os dados quando o utilizador volta a uma tab — garante
        que alterações feitas noutro PC (ficheiros partilhados em rede) são
        visíveis sem reiniciar a app."""
        ui = self._uis.get(nome)
        if ui is None:
            return
        metodo = {
            "painel": "atualizar",
            "ordens": "atualizar_tabela",
            "pedidos": "atualizar_tabela",
            "parque": "atualizar_grid_maquinas",
            "analytics": "atualizar_tabela",
            "configuracao": "atualizar",
            "producao": "atualizar_combos",
        }.get(nome)
        if metodo and hasattr(ui, metodo):
            getattr(ui, metodo)()
        if nome == "manutencao" and hasattr(ui, "atualizar_agenda"):
            ui.atualizar_agenda()
            ui.atualizar_lista_tarefas()
            ui.atualizar_historico()

    # ── FONTES RESPONSIVAS ────────────────────────────────────────────────

    def redimensionar_fontes(self, event):
        if event.widget is self:
            # winfo_width() está em píxeis físicos e o CTk volta a aplicar a escala
            # do Windows às fontes — sem dividir, a 125% a escala era aplicada duas
            # vezes (letras enormes num portátil). Limitado a 12–14.
            try:
                escala = ctk.ScalingTracker.get_window_scaling(self)
            except Exception:
                escala = 1.0
            largura = self.winfo_width() / escala
            base = max(12, min(14, int(largura / 100)))
            self.f_padrao.configure(size=base)
            self.f_titulo.configure(size=int(base * 1.3))

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
        # Texto honesto: o teste confirma que a pasta de dados está acessível
        # para escrita — não que esteja "sincronizado".
        if ok:
            self.lbl_status_dot.configure(text_color=theme.SUCCESS[1])
            self.lbl_status_texto.configure(text=" Pasta de dados acessível")
        else:
            self.lbl_status_dot.configure(text_color=theme.CRITICAL[1])
            self.lbl_status_texto.configure(text=" Pasta de dados sem acesso")

    # ── BACKUP AUTOMÁTICO ────────────────────────────────────────────────

    def _executar_backup_inicial_bg(self):
        """Corre em thread daemon: cria o backup diário se ainda não
        existir, e faz a rotação dos snapshots antigos. Resultado devolvido
        via fila para a main thread atualizar a UI em segurança."""
        try:
            caminho = BackupService.snapshot_automatico_diario()
            BackupService.limpar_backups_antigos(manter=30)
            self._fila_backup.put(("ok", caminho))
        except Exception as e:
            self._fila_backup.put(("erro", str(e)))

    def _processar_fila_backup(self):
        try:
            while True:
                estado, info = self._fila_backup.get_nowait()
                self._atualizar_indicador_backup(estado, info)
        except queue.Empty:
            pass
        self.after(500, self._processar_fila_backup)

    def _atualizar_indicador_backup(self, estado: str, info):
        if estado == "ok":
            hoje = datetime.now().strftime("%d/%m/%Y")
            self.lbl_backup_texto.configure(
                text=f"Backup de hoje feito · {hoje}", text_color=theme.SIDEBAR_TEXT_MUTED)
        else:
            self.lbl_backup_texto.configure(
                text="Backup falhou", text_color=theme.CRITICAL[1])
