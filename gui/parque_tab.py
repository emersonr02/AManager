import io
import queue
import threading
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

import customtkinter as ctk
from PIL import Image

from services.maquina_service import MaquinaService
from services.manutencao_service import ManutencaoService
from services.producao_service import ProducaoService
from services.pedido_service import PedidoService
from gui.dialogs.logistica_maquina import JanelaLogisticaMaquina
from gui import theme

_LARGURA_CARTAO = 250  # largura mínima de um cartão; o nº de colunas segue a largura do ecrã


def estado_cartao(maquina: dict, producao_ativa) -> tuple:
    """Estado principal a mostrar no cartão, por prioridade (um só, para não
    cortar texto): Desativada > Parada > Em produção > Disponível."""
    estado = maquina.get("estado", "Operacional")
    if estado == "Desativado":
        return "DESATIVADA", "neutral"
    if not MaquinaService.esta_disponivel(maquina):
        return "PARADA", "warn"
    if producao_ativa:
        return "EM PRODUÇÃO", "run"
    return "DISPONÍVEL", "ok"


class ParqueTab:
    def __init__(self, parent_frame, f_padrao=None, f_titulo=None, master_app=None):
        self.parent = parent_frame
        self.f_padrao = f_padrao
        self.master_app = master_app
        self.parent.configure(fg_color=theme.BG)

        # Fila thread-safe: threads de download colocam (lbl_widget, CTkImage)
        # aqui; o polling na main thread aplica-as sem bloquear a UI.
        self._fila_imagens: queue.Queue = queue.Queue()
        self._cartoes = []
        self._n_colunas = 0

        self.construir_layout()
        self.atualizar_grid_maquinas()
        self._processar_fila_imagens()

    def construir_layout(self):
        cab = theme.page_header(self.parent, "Parque de máquinas", "Máquinas")
        cab.pack(fill="x", padx=24, pady=(18, 8))
        theme.button_action(cab.acoes, text="+ Adicionar máquina", height=34,
                            command=self.abrir_formulario_cadastro).pack(side="left")

        frm_flt = ctk.CTkFrame(self.parent, fg_color="transparent")
        frm_flt.pack(fill="x", padx=24, pady=(0, 6))
        self.seg_tech = theme.segmented(frm_flt, values=["Todas", "FDM", "SLA", "SLS"],
                                        command=lambda _: self.atualizar_grid_maquinas())
        self.seg_tech.set("Todas")
        self.seg_tech.pack(side="left")
        self.lbl_resumo = ctk.CTkLabel(frm_flt, text="", font=theme.font_body(12), text_color=theme.TEXT_MUTED)
        self.lbl_resumo.pack(side="right")

        self.scroll_container = ctk.CTkScrollableFrame(self.parent, fg_color="transparent")
        self.scroll_container.pack(fill="both", expand=True, padx=19, pady=(0, 16))
        self.scroll_container.bind("<Configure>", lambda e: self._dispor_cartoes(), add="+")

    # ------------------------------------------------------------------ #
    #  GRELHA                                                              #
    # ------------------------------------------------------------------ #
    def atualizar_grid_maquinas(self):
        for w in self.scroll_container.winfo_children():
            w.destroy()
        self._cartoes = []
        self._n_colunas = 0

        # Calculados uma vez para toda a grelha (são joins sobre todas as
        # máquinas/tarefas/produções — repeti-los por cartão seria N vezes).
        maquinas_atrasadas = {l["maquina_id"] for l in ManutencaoService.calcular_proximas_tarefas() if l["estado"] == "atrasada"}
        id_para_nome = MaquinaService.obter_lookup_id_nome()
        fila_por_maquina = self._construir_fila(id_para_nome)
        projetos = {p.get("id"): p.get("nr_projeto", "") for p in PedidoService.obter_todos()}

        filtro = self.seg_tech.get()
        maquinas = [m for m in MaquinaService.obter_todas() if isinstance(m, dict)]
        n_disponiveis = n_producao = n_paradas = 0
        for m in maquinas:
            if filtro != "Todas" and m.get("tech") != filtro:
                continue
            producao_ativa = fila_por_maquina.get(m.get("id"))
            texto, _ = estado_cartao(m, producao_ativa)
            n_disponiveis += texto == "DISPONÍVEL"
            n_producao += texto == "EM PRODUÇÃO"
            n_paradas += texto == "PARADA"
            self._cartoes.append(self._criar_card(m, producao_ativa, m.get("id") in maquinas_atrasadas, projetos))
        self.lbl_resumo.configure(text=f"{n_disponiveis} disponíveis · {n_producao} em produção · {n_paradas} paradas")
        self._dispor_cartoes()

    def _dispor_cartoes(self):
        """Número de colunas a partir da largura disponível (antes: 4 fixas)."""
        if not self._cartoes:
            return
        try:
            escala = ctk.ScalingTracker.get_widget_scaling(self.scroll_container)
        except Exception:
            escala = 1.0
        largura = self.scroll_container.winfo_width()
        n = max(1, int(largura / (_LARGURA_CARTAO * escala))) if largura > 1 else 4
        if n == self._n_colunas:
            return
        self._n_colunas = n
        for i in range(8):
            self.scroll_container.grid_columnconfigure(i, weight=1 if i < n else 0, uniform="col" if i < n else "")
        for idx, card in enumerate(self._cartoes):
            card.grid(row=idx // n, column=idx % n, padx=6, pady=6, sticky="nsew")

    def _construir_fila(self, id_para_nome: dict) -> dict:
        """{id_maquina: produção} para máquinas com uma ordem ativa (a mais recente)."""
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
    #  CARTÃO                                                              #
    # ------------------------------------------------------------------ #
    def _criar_card(self, m: dict, producao_ativa: dict = None, atrasada: bool = False, projetos: dict = None):
        texto_pill, variante_pill = estado_cartao(m, producao_ativa)
        card = ctk.CTkFrame(self.scroll_container, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_M, border_width=1,
                            border_color=(theme.TEAL if producao_ativa else theme.BORDER))

        url = m.get("url_img", "")
        if url and urlparse(url).scheme in ("http", "https"):
            # Só reserva espaço para imagem quando há uma (antes: ~50px vazios em todos os cartões)
            lbl_img = ctk.CTkLabel(card, text="A carregar imagem…", font=theme.font_body(11), text_color=theme.TEXT_MUTED, height=120)
            lbl_img.pack(pady=(12, 0))
            threading.Thread(target=self._download_imagem_bg, args=(url, lbl_img), daemon=True).start()

        topo = ctk.CTkFrame(card, fg_color="transparent")
        topo.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(topo, text=m.get("id"), font=theme.font_mono(16, "bold"), text_color=theme.ACCENT).pack(side="left")
        theme.pill(topo, texto_pill, variante_pill).pack(side="right")

        ctk.CTkLabel(card, text=m.get("nome"), font=theme.font_body(13, "bold"), text_color=theme.TEXT, anchor="w").pack(fill="x", padx=14)
        detalhe = " · ".join(x for x in (m.get("modelo", ""), m.get("tech", "")) if x)
        ctk.CTkLabel(card, text=detalhe or "—", font=theme.font_body(12), text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", padx=14)

        if atrasada:
            frm_alerta = ctk.CTkFrame(card, fg_color="transparent")
            frm_alerta.pack(fill="x", padx=14, pady=(6, 0))
            theme.pill(frm_alerta, "MANUTENÇÃO ATRASADA", "bad").pack(side="left")

        if producao_ativa:
            self._desenhar_bloco_job_ativo(card, producao_ativa, projetos or {})

        notas = m.get("manutencao", "OK")
        if notas and notas != "OK":
            ctk.CTkLabel(card, text=f"Nota: {notas}", font=theme.font_body(12), text_color=theme.WARNING, anchor="w",
                         wraplength=230, justify="left").pack(fill="x", padx=14, pady=(6, 0))

        frm_botoes = ctk.CTkFrame(card, fg_color="transparent")
        frm_botoes.pack(side="bottom", fill="x", padx=14, pady=(10, 14))
        if texto_pill == "DISPONÍVEL" and self.master_app is not None:
            theme.button_action(frm_botoes, text="Iniciar ordem", height=30, font=theme.font_body(12, "bold"),
                                command=lambda mm=m: self.master_app.abrir_nova_ordem(mm.get("tech"), mm.get("nome"))
                                ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        theme.button_ghost(frm_botoes, text="Editar", height=30, width=80,
                           command=lambda mm=m: self.abrir_formulario_edicao(mm)).pack(side="right")
        return card

    def _desenhar_bloco_job_ativo(self, card, producao: dict, projetos: dict):
        """Ordem em curso: projeto, tempo decorrido vs estimado e barra de progresso."""
        frm = ctk.CTkFrame(card, fg_color=theme.TEAL_BG, corner_radius=theme.RADIUS_S)
        frm.pack(fill="x", padx=14, pady=(8, 0))

        nomes = sorted({projetos.get(v, "") for v in ProducaoService.ids_pedidos_vinculados(producao)} - {""})
        projeto = " | ".join(nomes) or producao.get("nr_projeto", "") or "Sem projeto"
        ctk.CTkLabel(frm, text=f"{ProducaoService.formatar_codigo(producao.get('id'))} · {projeto}",
                     font=theme.font_body(12, "bold"), text_color=theme.TEAL, wraplength=220, justify="left",
                     anchor="w").pack(fill="x", padx=10, pady=(8, 2))

        tempo_est = ProducaoService.normalizar_tempo(producao)
        progresso, decorrido_str = self._calcular_progresso(producao.get("data_inicio", ""), ProducaoService.converter_para_horas(tempo_est))
        barra = ctk.CTkProgressBar(frm, height=6, progress_color=theme.TEAL, fg_color=theme.BORDER)
        barra.set(progresso)
        barra.pack(fill="x", padx=10, pady=(2, 4))
        ctk.CTkLabel(frm, text=f"{decorrido_str} decorridas de {tempo_est} estimadas", font=theme.font_body(11),
                     text_color=theme.TEXT_MUTED, anchor="w").pack(fill="x", padx=10, pady=(0, 8))

    @staticmethod
    def _calcular_progresso(data_inicio_str: str, horas_estimadas: float) -> tuple:
        """Fração decorrida do job (0.0-1.0) e HH:MM do tempo já passado."""
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
                        lbl.configure(text="Imagem indisponível", image=None)
        except queue.Empty:
            pass
        if self.parent.winfo_exists():
            self.parent.after(150, self._processar_fila_imagens)

    # ------------------------------------------------------------------ #
    #  FORMULÁRIOS                                                         #
    # ------------------------------------------------------------------ #
    def abrir_formulario_cadastro(self):
        JanelaLogisticaMaquina(self.parent.winfo_toplevel(), None, self.atualizar_grid_maquinas)

    def abrir_formulario_edicao(self, maquina_dados):
        JanelaLogisticaMaquina(self.parent.winfo_toplevel(), maquina_dados, self.atualizar_grid_maquinas)
