"""Gera PNGs de todas as telas e diálogos do AManager, para revisão visual
antes/depois de alterações de UI.

NUNCA lê nem escreve em data/ real: copia o código (config/ database/ gui/
services/ main.py) para uma pasta temporária, escreve lá data/*.json com
dados FICTÍCIOS e arranca a app a partir dessa cópia. Como
config/paths.BASE_DIR deriva da localização do ficheiro, a cópia só usa o
seu próprio data/. Já houve um incidente de dados de cliente a vazar para o
git (ver .gitignore) — este script não pode ser mais um caminho para isso.

Uso:
    python tools/capturar_telas.py                     # os dois perfis
    python tools/capturar_telas.py --perfil desktop    # 1300x800, escala 1.0
    python tools/capturar_telas.py --perfil portatil   # 1366x728, escala 1.25
    python tools/capturar_telas.py --perfil portatil --saida capturas/antes

Cada perfil corre num subprocesso próprio, com uma sandbox nova: um único
Tk() por processo (ver o comentário de app_sessao em tests/conftest.py sobre
o segundo Tk() instável no mesmo processo).
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parent.parent
CODIGO_A_COPIAR = ["config", "database", "gui", "services", "main.py"]

# "portatil" simula um portátil 1366x768 a 125%: a área útil (ecrã menos a
# barra de tarefas) com os widgets à escala que o Windows lhes daria. É neste
# perfil que aparecem as ações empurradas para fora do ecrã.
PERFIS = {
    "desktop": {"geometria": (1300, 800), "escala": 1.0},
    "portatil": {"geometria": (1366, 728), "escala": 1.25},
}

# Um messagebox ou diálogo modal inesperado bloquearia o subprocesso para
# sempre — o timeout garante que o script termina e reporta a falha.
TIMEOUT_PERFIL_S = 240
ESPERA_CAPTURA_S = 0.7


# ── PROCESSO PRINCIPAL ────────────────────────────────────────────────────

def main(argv=None) -> int:
    # A consola do Windows (cp1252) rebenta com caracteres fora da página de
    # código quando a saída é redirecionada — melhor um "?" do que um crash.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        description="Captura PNGs de todas as telas e diálogos do AManager "
                    "a partir de uma cópia do código com dados fictícios.")
    parser.add_argument("--perfil", choices=[*PERFIS, "todos"], default="todos",
                        help="desktop (1300x800, escala 1.0), portatil (1366x728, "
                             "escala 1.25) ou todos (por omissão)")
    parser.add_argument("--saida", type=Path,
                        help="pasta de saída (por omissão capturas/<perfil>/); "
                             "com --perfil todos é criada uma subpasta por perfil")
    parser.add_argument("--manter-sandbox", action="store_true",
                        help="não apaga a cópia temporária no fim (para inspecionar "
                             "os dados fictícios)")
    parser.add_argument("--interno-sandbox", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.interno_sandbox:
        return _capturar_na_sandbox(args.interno_sandbox, args.perfil, args.saida)

    perfis = list(PERFIS) if args.perfil == "todos" else [args.perfil]
    codigos = []
    for perfil in perfis:
        if args.saida is None:
            saida = RAIZ_REPO / "capturas" / perfil
        elif len(perfis) > 1:
            saida = args.saida / perfil
        else:
            saida = args.saida
        saida = saida.resolve()
        if saida.is_relative_to(RAIZ_REPO / "data"):
            parser.error("--saida não pode ficar dentro de data/")
        codigos.append(_correr_perfil(perfil, saida, args.manter_sandbox))
    return max(codigos)


def _correr_perfil(perfil: str, saida: Path, manter_sandbox: bool) -> int:
    sandbox = Path(tempfile.mkdtemp(prefix=f"amanager_capturas_{perfil}_"))
    print(f"[{perfil}] sandbox: {sandbox}", flush=True)
    try:
        for nome in CODIGO_A_COPIAR:
            origem = RAIZ_REPO / nome
            if origem.is_dir():
                shutil.copytree(origem, sandbox / nome,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(origem, sandbox / nome)

        # Sem PYTHONPATH herdado: nada pode fazer o subprocesso importar o
        # config/ real (e com ele o data/ real) em vez da cópia. USERNAME
        # fictício porque a app o mostra (ex.: "verificado por" no Fechar Ordem).
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["USERNAME"] = "operador.demo"
        cmd = [sys.executable, str(Path(__file__).resolve()),
               "--perfil", perfil, "--saida", str(saida),
               "--interno-sandbox", str(sandbox)]
        try:
            return subprocess.run(cmd, cwd=sandbox, env=env,
                                  timeout=TIMEOUT_PERFIL_S).returncode
        except subprocess.TimeoutExpired:
            print(f"[{perfil}] ERRO: excedeu {TIMEOUT_PERFIL_S}s — provavelmente um "
                  "messagebox ou diálogo modal ficou à espera de input.")
            return 1
    finally:
        if manter_sandbox:
            print(f"[{perfil}] sandbox mantida em {sandbox}")
        else:
            shutil.rmtree(sandbox, ignore_errors=True)


# ── SUBPROCESSO (corre dentro da sandbox) ─────────────────────────────────

def _capturar_na_sandbox(sandbox: Path, perfil: str, saida: Path) -> int:
    sandbox = sandbox.resolve()
    sys.path[:] = [p for p in sys.path
                   if p and Path(p).resolve() != RAIZ_REPO]
    sys.path.insert(0, str(sandbox))
    os.chdir(sandbox)

    from config import paths
    if Path(paths.DATA_DIR).resolve() != sandbox / "data":
        print(f"ERRO: config.paths.DATA_DIR aponta para {paths.DATA_DIR}, fora da "
              "sandbox — abortado antes de tocar em qualquer dado.")
        return 2

    alvos = _escrever_dados_ficticios(sandbox / "data")
    saida.mkdir(parents=True, exist_ok=True)

    import tkinter
    import customtkinter as ctk
    from services.resumo_diario_service import ResumoDiarioService

    # O marcador "resumo já visto hoje" vive por omissão em ~/.amanager.
    ResumoDiarioService._MARCADOR_DIR = str(sandbox / ".amanager")
    avisos = _neutralizar_messageboxes()

    # A titlebar fica fora da área capturada; desligar o hack de DWM evita a
    # corrida descrita em tests/conftest.py ao abrir muitos CTkToplevel seguidos.
    ctk.CTk._deactivate_windows_window_header_manipulation = True
    ctk.CTkToplevel._deactivate_windows_window_header_manipulation = True

    cfg = PERFIS[perfil]
    ctk.set_widget_scaling(cfg["escala"])
    if perfil == "portatil":
        # Simulação fiel de um portátil 1366x768 a 125%: a escala aplica-se também
        # às janelas, e o "ecrã" que a app vê tem 1366x768 — assim a janela
        # principal e os diálogos dimensionam-se sozinhos (theme.dimensionar_janela)
        # exatamente como num portátil real, em vez de herdarem o monitor desta máquina.
        ctk.set_window_scaling(cfg["escala"])
        tkinter.Misc.winfo_screenwidth = lambda self: 1366
        tkinter.Misc.winfo_screenheight = lambda self: 768

    from gui.app import AppIndustrialI3D
    app = AppIndustrialI3D()

    # Neutraliza a escala DPI do monitor (o customtkinter multiplica-a por cima
    # da nossa), para as capturas terem o mesmo tamanho em qualquer máquina.
    dpi = ctk.ScalingTracker.get_window_dpi_scaling(app)
    if dpi != 1.0:
        ctk.set_widget_scaling(cfg["escala"] / dpi)
        ctk.set_window_scaling((cfg["escala"] if perfil == "portatil" else 1.0) / dpi)
    largura, altura = cfg["geometria"]
    if perfil == "desktop":
        app.geometry(f"{largura}x{altura}+0+0")
    else:
        app.update_idletasks()
        largura, altura = app.winfo_width(), app.winfo_height()
    app.attributes("-topmost", True)

    ecra = (app.winfo_screenwidth(), app.winfo_screenheight())
    print(f"[{perfil}] ecrã {ecra[0]}x{ecra[1]}, DPI {dpi:g}, janela {largura}x{altura}, "
          f"escala {cfg['escala']:g} -> {saida}")
    if largura > ecra[0] or altura > ecra[1]:
        print(f"[{perfil}] AVISO: a janela não cabe no ecrã — as capturas ficam cortadas.")

    cap = _Capturador(app, saida)
    try:
        _percorrer_telas(app, cap, alvos)
    finally:
        app.destroy()

    falhas = cap.falhas + [f"messagebox inesperada: {a}" for a in avisos]
    print(f"[{perfil}] {len(cap.feitas)} capturas em {saida}")
    for f in falhas:
        print(f"[{perfil}] FALHA: {f}")
    return 1 if falhas else 0


def _percorrer_telas(app, cap: "_Capturador", alvos: dict):
    # ── Ecrãs da navegação ──
    cap.tela("00_painel", lambda: app.selecionar_tela("painel"))
    cap.tela("01_ordens", lambda: app.selecionar_tela("ordens"))
    cap.tela("02_pedidos", lambda: app.selecionar_tela("pedidos"))
    cap.tela("03_maquinas", lambda: app.selecionar_tela("parque"))
    cap.tela("04_analise", lambda: app.selecionar_tela("analytics"), espera=1.0)

    def nova_ordem(tech):
        from services.pedido_service import PedidoService
        app.abrir_nova_ordem(tech)
        ui = app._uis["producao"]
        abertos = [p["id"] for p in PedidoService.obter_todos()
                   if p.get("tecnologia") == tech and p.get("estado") in PedidoService.ESTADOS_ABERTOS]
        ui._definir_pedidos(abertos[:1])   # mostra o resumo dos pedidos à direita
    cap.tela("05_nova_ordem_fdm", lambda: nova_ordem("FDM"))
    cap.tela("05b_nova_ordem_sls", lambda: nova_ordem("SLS"))

    def manutencao(aba):
        app.selecionar_tela("manutencao")
        app._uis["manutencao"].tabview.set(aba)
    cap.tela("06_manutencao_agenda", lambda: manutencao("Agenda"))
    cap.tela("06b_manutencao_tarefas", lambda: manutencao("Tarefas periódicas"))
    cap.tela("06c_manutencao_historico", lambda: manutencao("Histórico"))

    def configuracao(aba):
        app.selecionar_tela("configuracao")
        app._uis["configuracao"].tabview.set(aba)
    cap.tela("07_configuracao_projetos", lambda: configuracao("Projetos"))
    cap.tela("07b_configuracao_materiais", lambda: configuracao("Materiais"))
    cap.tela("07c_configuracao_templates", lambda: configuracao("Templates"))
    cap.tela("07d_configuracao_codigos_nc", lambda: configuracao("Códigos NC"))

    # ── Diálogos ──
    def selecionar_pedidos():
        app.abrir_nova_ordem("FDM")
        app._uis["producao"].abrir_pop_up_selecao_pedidos()
    cap.dialogo("10_selecionar_pedidos", selecionar_pedidos)

    app.selecionar_tela("pedidos")
    pedidos = app._uis["pedidos"]
    cap.dialogo("11_novo_pedido", pedidos.abrir_novo_pedido)

    def com_pedido_selecionado(acao):
        def abrir():
            tree = pedidos.tree_pedidos
            tree.selection_set(tree.get_children()[0])
            acao()
        return abrir
    cap.dialogo("12_editar_pedido", com_pedido_selecionado(pedidos.abrir_edicao))
    cap.dialogo("13_alterar_estado", com_pedido_selecionado(pedidos.abrir_dialogo_estado))
    cap.dialogo("14_email_resposta", com_pedido_selecionado(pedidos.abrir_email_resposta))

    def editar_projeto():
        configuracao("Projetos")
        gestao = app._uis["configuracao"].gestao
        gestao.tree_proj.selection_set(gestao.tree_proj.get_children()[0])
        gestao.editar_projeto_selecionado()
    cap.dialogo("15_editar_projeto", editar_projeto)

    def editar_maquina():
        from services.maquina_service import MaquinaService
        app.selecionar_tela("parque")
        maquina = next(m for m in MaquinaService.obter_todas()
                       if m.get("id") == alvos["maquina_editar"])
        app._uis["parque"].abrir_formulario_edicao(maquina)
    cap.dialogo("16_editar_maquina", editar_maquina)

    def com_ordem_selecionada(acao_nome):
        def abrir():
            from services.producao_service import ProducaoService
            app.selecionar_tela("ordens")
            ordens = app._uis["ordens"]
            linha = next(i for i in ordens.tab_tree.get_children()
                         if ProducaoService.extrair_id(ordens.tab_tree.item(i)["values"][0])
                         == alvos["producao_fecho"])
            ordens.tab_tree.selection_set(linha)
            getattr(ordens, acao_nome)()
        return abrir
    cap.dialogo("17_fechar_ordem", com_ordem_selecionada("abrir_tratamento_ordem"))
    cap.dialogo("18_anular_ordem", com_ordem_selecionada("anular_ordem"))

    def registar_manutencao():
        manutencao("Agenda")
        ui = app._uis["manutencao"]
        ui.tree_agenda.selection_set(ui.tree_agenda.get_children()[0])
        ui.marcar_concluida()
    cap.dialogo("19_registar_manutencao", registar_manutencao)

    def editar_tarefa():
        manutencao("Tarefas periódicas")
        ui = app._uis["manutencao"]
        ui.tree_tarefas.selection_set(ui.tree_tarefas.get_children()[0])
        ui.editar_tarefa_selecionada()
    cap.dialogo("20_editar_tarefa", editar_tarefa)


class _Capturador:
    def __init__(self, app, saida: Path):
        self.app = app
        self.saida = saida
        self.feitas: list[str] = []
        self.falhas: list[str] = []

    def tela(self, nome, preparar=None, espera=0.0):
        try:
            if preparar:
                preparar()
            _bombear(self.app, espera)
            self._guardar(self.app, nome)
        except Exception:
            self._falhou(nome)

    def dialogo(self, nome, abrir, extras=()):
        """abrir=None: o diálogo já foi agendado pela própria app (Resumo do Dia)
        e pode até já estar aberto — qualquer janela conta como nova."""
        antes = set(_toplevels(self.app)) if abrir else set()
        try:
            if abrir:
                abrir()
            janela = self._esperar_nova_janela(antes)
            self._guardar(janela, nome)
            for nome_extra, acao in extras:
                acao(janela)
                self._guardar(janela, nome_extra)
        except Exception:
            self._falhou(nome)
        finally:
            for janela in set(_toplevels(self.app)) - antes:
                janela.destroy()
            _bombear(self.app, 0.2)

    def _esperar_nova_janela(self, antes, timeout=5.0):
        fim = time.monotonic() + timeout
        while time.monotonic() < fim:
            self.app.update()
            novas = [t for t in _toplevels(self.app) if t not in antes and t.winfo_viewable()]
            if novas:
                return novas[0]
            time.sleep(0.02)
        raise RuntimeError("nenhum diálogo novo abriu")

    def _guardar(self, janela, nome):
        from PIL import ImageGrab
        janela.lift()
        janela.attributes("-topmost", True)
        _bombear(self.app, ESPERA_CAPTURA_S)
        x, y = janela.winfo_rootx(), janela.winfo_rooty()
        w, h = janela.winfo_width(), janela.winfo_height()
        ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(
            self.saida / f"{nome}.png")
        self.feitas.append(nome)
        print(f"  {nome}.png  {w}x{h}")

    def _falhou(self, nome):
        self.falhas.append(f"{nome}: {traceback.format_exc().strip().splitlines()[-1]}")
        traceback.print_exc()


def _bombear(app, segundos):
    fim = time.monotonic() + segundos
    while True:
        app.update()
        if time.monotonic() >= fim:
            return
        time.sleep(0.02)


def _toplevels(widget):
    import tkinter as tk
    for filho in widget.winfo_children():
        if isinstance(filho, tk.Toplevel):
            yield filho
        yield from _toplevels(filho)


def _neutralizar_messageboxes() -> list:
    """Um messagebox real bloquearia o processo à espera de um clique. Nenhum
    passo do percurso deve abrir um; se abrir, fica registado como falha."""
    from tkinter import messagebox
    avisos = []

    def substituto(nome, resposta):
        def _f(title=None, message=None, **_kw):
            avisos.append(f"{nome}({title!r}, {message!r})")
            return resposta
        return _f

    for nome in ("showinfo", "showwarning", "showerror"):
        setattr(messagebox, nome, substituto(nome, "ok"))
    for nome in ("askyesno", "askokcancel", "askretrycancel"):
        setattr(messagebox, nome, substituto(nome, False))
    messagebox.askquestion = substituto("askquestion", "no")
    messagebox.askyesnocancel = substituto("askyesnocancel", None)
    return avisos


# ── DADOS FICTÍCIOS ───────────────────────────────────────────────────────

def _escrever_dados_ficticios(pasta: Path) -> dict:
    """Escreve data/*.json fictícios na sandbox. Determinístico (seed fixa),
    com datas relativas a hoje para o Resumo do Dia e a agenda terem conteúdo.
    Devolve os IDs que o percurso de capturas usa."""
    from config.constantes import DICIONARIO_NC

    rnd = random.Random(7)
    agora = datetime.now().replace(microsecond=0)
    meia_noite = agora.replace(hour=0, minute=0, second=0)

    def fmt(dt):
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def hoje_ha(horas):
        # Nunca antes da meia-noite: de manhã cedo continua a contar como "hoje".
        return max(agora - timedelta(hours=horas), meia_noite + timedelta(minutes=5))

    projetos = [
        {"id": "100201", "nome": "Suporte Drone"},
        {"id": "100322", "nome": "Caixa Sensor IoT"},
        {"id": "100415", "nome": "Molde Teste Termoformagem"},
        {"id": "100517", "nome": "Protótipo Pega Ergonómica"},
        {"id": "100630", "nome": "Gabarito de Montagem"},
    ]
    materiais = [
        {"nome": "PLA Preto", "fabricante": "Prusament"},
        {"nome": "PETG Branco", "fabricante": "Bambu Lab"},
        {"nome": "Resina Grey V4", "fabricante": "Formlabs"},
        {"nome": "PA12", "fabricante": "EOS"},
    ]
    mat = {m["nome"]: f"{m['nome']} - {m['fabricante']}" for m in materiais}
    material_por_tech = {"FDM": [mat["PLA Preto"], mat["PETG Branco"]],
                         "SLA": [mat["Resina Grey V4"]], "SLS": [mat["PA12"]]}

    maquinas = [
        {"id": "X1C-1", "nome": "Bambu Lab X1C #1", "modelo": "Bambu Lab X1C", "tech": "FDM",
         "estado": "Operacional", "manutencao": "OK", "url_img": ""},
        {"id": "X1C-2", "nome": "Bambu Lab X1C #2", "modelo": "Bambu Lab X1C", "tech": "FDM",
         "estado": "Operacional", "manutencao": "OK", "url_img": ""},
        {"id": "MK4-1", "nome": "Prusa MK4 #1", "modelo": "Prusa MK4", "tech": "FDM",
         "estado": "Manutenção - Parado", "manutencao": "Troca de hotend agendada", "url_img": ""},
        {"id": "F3-1", "nome": "Formlabs Form 3 #1", "modelo": "Formlabs Form 3", "tech": "SLA",
         "estado": "Operacional", "manutencao": "OK", "url_img": ""},
        {"id": "P396-1", "nome": "EOS P396 #1", "modelo": "EOS P396", "tech": "SLS",
         "estado": "Operacional", "manutencao": "OK", "url_img": ""},
        {"id": "MK3-OLD", "nome": "Prusa MK3 (antiga)", "modelo": "Prusa MK3", "tech": "FDM",
         "estado": "Desativado", "manutencao": "OK", "url_img": ""},
    ]
    maq_por_tech = {"FDM": ["Bambu Lab X1C #1", "Bambu Lab X1C #2", "Prusa MK4 #1"],
                    "SLA": ["Formlabs Form 3 #1"], "SLS": ["EOS P396 #1"]}

    requerentes = ["ana.costa@exemplo.pt", "rui.mendes@exemplo.pt", "lab.testes@exemplo.pt"]
    estados_e_tech = [("Pendente", "FDM"), ("Em Andamento", "FDM"), ("Em Andamento", "FDM"),
                      ("Em Andamento", "SLA"), ("Concluído", "FDM"), ("Entregue", "SLS"),
                      ("Pendente", "SLA"), ("Pendente", "FDM"), ("Cancelado", "FDM")]
    pedidos = []
    for i, (estado, tech) in enumerate(estados_e_tech, start=1):
        projeto = projetos[i % len(projetos)]
        material = material_por_tech[tech][i % len(material_por_tech[tech])]
        feito = estado in ("Concluído", "Entregue")
        pecas = [{"pn": f"PN-{i:03d}-{sufixo}", "material": material,
                  "qtd_solicitada": qtd, "qtd_produzida": qtd if feito else 0}
                 for sufixo, qtd in (("A", 4), ("B", 2))]
        pedidos.append({
            "id": i, "requerente_email": requerentes[i % len(requerentes)],
            "nr_projeto": projeto["id"], "nome_projeto": projeto["nome"],
            "tecnologia": tech, "observacoes": "Entregar em saco individual.",
            "data_pedido": (agora - timedelta(days=40 - i * 4)).strftime("%Y-%m-%d"),
            "data_entrega": (agora + timedelta(days=i * 2)).strftime("%Y-%m-%d"),
            "data_atualizacao": agora.strftime("%Y-%m-%d"),
            "link_arquivos": r"\\servidor\projetos\exemplo",
            "estado": estado, "pecas": pecas, "producoes_vinculadas": [],
        })
    pedidos_com_producao = {tech: [p["id"] for p in pedidos if p["tecnologia"] == tech
                                   and p["estado"] not in ("Pendente", "Cancelado")]
                            for tech in maq_por_tech}

    ncs_por_tech = {"FDM": ["COD001", "COD002", "COD003", "COD004"],
                    "SLA": ["COD010", "COD011"], "SLS": ["COD017"]}

    def producao(tech, inicio, estado, maquina=None, nc=None, acoes=(), horas=None):
        horas = horas or rnd.randint(1, 14)
        p = {
            "tecnologia": tech, "maquina": maquina or rnd.choice(maq_por_tech[tech]),
            "data_inicio": fmt(inicio),
            "tempo_estimado": f"{horas:02d}:{rnd.choice([0, 15, 30, 45]):02d}",
            "estado": estado, "operador": rnd.choice(["jsilva", "mferreira"]),
            "pedidos_vinculados": [rnd.choice(pedidos_com_producao[tech])],
        }
        if tech == "SLS":
            p.update({"altura_cuba": "320", "percentagem_po_novo": "0.3", "lote_po": "L-2026-07"})
        else:
            p["quantidade_consumida"] = str(rnd.randint(30, 400))
        if estado != "Em Andamento":
            p.update({"tempo_real": p["tempo_estimado"],
                      "quantidade_real": p.get("quantidade_consumida", "12.5"),
                      "verificado_por": "mferreira",
                      "data_fecho": fmt(inicio + timedelta(hours=horas))})
        if nc:
            p.update({"nc_codigo": nc, "acoes_aplicadas": list(acoes),
                      "notas_acao_corretiva": "Ação aplicada antes da reimpressão." if acoes else ""})
        return p

    # ~30 produções históricas nos últimos 60 dias (uma a cada 2 dias), algumas com NC.
    producoes = []
    for dias_atras in range(58, 1, -2):
        tech = rnd.choice(["FDM", "FDM", "FDM", "SLA", "SLS"])
        inicio = agora - timedelta(days=dias_atras, hours=rnd.randint(1, 8))
        estado = "Concluída" if rnd.random() < 0.85 else "Cancelada"
        nc = None
        if estado == "Cancelada" or rnd.random() < 0.12:
            nc = rnd.choice(ncs_por_tech[tech])
        acoes = ["ACT01"] if nc and rnd.random() < 0.4 else []
        producoes.append(producao(tech, inicio, estado, nc=nc, acoes=acoes))

    # NC recorrente sem ação corretiva (alerta CAPA) na X1C #2 esta semana.
    for dias_atras in (5, 3):
        producoes.append(producao("FDM", agora - timedelta(days=dias_atras, hours=2), "Cancelada",
                                  maquina="Bambu Lab X1C #2", nc="COD002"))

    # Alvo do diálogo Fechar Ordem: FDM com NC, ação aplicada e QA parcial.
    fecho = producao("FDM", agora - timedelta(days=1, hours=6), "Concluída",
                     maquina="Bambu Lab X1C #1", nc="COD001", acoes=["ACT01"], horas=5)
    pedido_fecho = next(p for p in pedidos if p["id"] in fecho["pedidos_vinculados"])
    fecho["qa_por_peca"] = {
        f"{pedido_fecho['id']}:{peca['pn']}:{idx}": {
            "inspecao_visual": True, "controlo_dimensional": idx == 0, "conformidade": idx == 0}
        for idx, peca in enumerate(pedido_fecho["pecas"])
    }
    producoes.append(fecho)

    # Hoje: uma concluída de manhã e três em curso.
    producoes.append(producao("FDM", hoje_ha(9), "Concluída", maquina="Bambu Lab X1C #2", horas=3))
    producoes.append(producao("FDM", hoje_ha(3), "Em Andamento", maquina="Bambu Lab X1C #1"))
    producoes.append(producao("SLA", hoje_ha(2), "Em Andamento"))
    producoes.append(producao("SLS", hoje_ha(1), "Em Andamento"))

    producoes.sort(key=lambda p: p["data_inicio"])
    for id_prod, p in enumerate(producoes, start=1):
        p["id"] = id_prod
        for pedido in pedidos:
            if pedido["id"] in p["pedidos_vinculados"]:
                pedido["producoes_vinculadas"].append(id_prod)

    nc_falhas = [{"cod": linha.split(" - ", 1)[0], "descricao": linha.split(" - ", 1)[1],
                  "tecnologia": tech}
                 for tech, linhas in DICIONARIO_NC.items() for linha in linhas]
    acoes_corretivas = [
        {"act": "ACT01", "acao": "Limpar/substituir bico e fazer cold pull",
         "codigos_aplicaveis": ["COD001", "COD004"]},
        {"act": "ACT02", "acao": "Limpar mesa com IPA e reaplicar adesivo",
         "codigos_aplicaveis": ["COD002", "COD003"]},
        {"act": "ACT03", "acao": "Recalibrar nivelamento automático",
         "codigos_aplicaveis": ["COD002", "COD008"]},
        {"act": "ACT04", "acao": "Aumentar temperatura da câmara",
         "codigos_aplicaveis": ["COD003"]},
    ]
    tarefas = [
        {"id": 1, "modelo": "Bambu Lab X1C", "nome": "Lubrificar eixos", "descricao": "",
         "frequencia_dias": 30, "frequencia_horas": 200, "ativo": True},
        {"id": 2, "modelo": "Bambu Lab X1C", "nome": "Limpeza do bico", "descricao": "",
         "frequencia_dias": None, "frequencia_horas": 60, "ativo": True},
        {"id": 3, "modelo": "Formlabs Form 3", "nome": "Substituir tanque de resina",
         "descricao": "", "frequencia_dias": 90, "frequencia_horas": None, "ativo": True},
        {"id": 4, "modelo": "EOS P396", "nome": "Limpeza filtros", "descricao": "",
         "frequencia_dias": 14, "frequencia_horas": None, "ativo": True},
        {"id": 5, "modelo": "Prusa MK4", "nome": "Verificar correias", "descricao": "",
         "frequencia_dias": 60, "frequencia_horas": None, "ativo": False},
    ]
    manutencoes = [
        {"id": 1, "tarefa_id": 1, "maquina_id": "X1C-1", "operador": "jsilva", "notas": "",
         "data_realizacao": fmt(agora - timedelta(days=40))},
        {"id": 2, "tarefa_id": 1, "maquina_id": "X1C-2", "operador": "mferreira", "notas": "",
         "data_realizacao": fmt(agora - timedelta(days=24))},
        {"id": 3, "tarefa_id": 3, "maquina_id": "F3-1", "operador": "mferreira",
         "notas": "Tanque novo lote T-88", "data_realizacao": fmt(agora - timedelta(days=20))},
        {"id": 4, "tarefa_id": 4, "maquina_id": "P396-1", "operador": "jsilva", "notas": "",
         "data_realizacao": fmt(agora - timedelta(days=12))},
    ]
    templates = [{"id": 1, "nome": "X1C PETG padrão", "tecnologia": "FDM",
                  "id_maquina": "Bambu Lab X1C #1", "tempo_estimado": "04:30", "uso_count": 3}]

    for nome, dados in [
        ("projetos.json", projetos), ("materiais.json", materiais),
        ("parque_maquinas.json", maquinas), ("pedidos.json", pedidos),
        ("producao_i3D.json", producoes), ("nc_falhas.json", nc_falhas),
        ("acoes_corretivas.json", acoes_corretivas),
        ("tarefas_manutencao.json", tarefas), ("manutencoes.json", manutencoes),
        ("templates_producao.json", templates),
    ]:
        (pasta / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=4),
                                  encoding="utf-8")

    return {"producao_fecho": fecho["id"], "maquina_editar": "MK4-1"}


if __name__ == "__main__":
    sys.exit(main())
