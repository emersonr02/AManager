"""Sistema de design central (cor, tipografia, componentes) do AManager.

Cores são definidas como tuplos (claro, escuro) — o CustomTkinter escolhe
automaticamente o valor certo consoante `ctk.set_appearance_mode()`, e
atualiza-os ao vivo quando o modo muda, sem código extra de repintura.

Regras do sistema (para manter a app coerente ao acrescentar telas):
- Cor com significado: texto neutro por omissão; cor só para exceções
  (cancelado/atrasado = CRITICAL, em curso = TEAL, aviso = WARNING).
- Texto nunca abaixo de 11px; monoespaçada só para dados (IDs, datas, números).
- Diálogos herdam de `Dialogo` (rodapé fixo, Cancelar/ação, Enter/Esc).
- Sucesso → `toast()` (não modal); erros e confirmações → messagebox.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import customtkinter as ctk

# ==========================================================================
# COR
# ==========================================================================
BG = ("#F3F6FA", "#12161C")
SURFACE = ("#FFFFFF", "#1A212A")
SURFACE_ALT = ("#EBF0F6", "#212932")
BORDER = ("#DCE3EB", "#2B3542")

TEXT = ("#15212E", "#E7ECF2")
TEXT_MUTED = ("#5C6B7D", "#93A2B4")          # 5,5:1 sobre branco

ACCENT = ("#123A5E", "#5C9CD6")           # ação primária / marca
ACCENT_STRONG = ("#0A2740", "#0A2740")    # fundo da sidebar (fixo, não segue o modo)
ACCENT_HOVER = ("#0A2740", "#7FB4E6")

TEAL = ("#0A7E8C", "#3FC1CE")             # ação secundária / "em produção" (4,8:1)
TEAL_BG = ("#E3F0F2", "#123339")
TEAL_HOVER = ("#08616C", "#59CDD8")

# SUCCESS e WARNING escurecidos para passar AA (4,5:1) como texto sobre branco:
# #1F9D55 dava 3,5:1 e #B4720A 3,9:1.
SUCCESS = ("#177A42", "#3BC17E")          # 5,4:1
SUCCESS_BG = ("#E6F5EC", "#1E3A2C")

WARNING = ("#8F5A06", "#E3A23D")          # 5,8:1
WARNING_BG = ("#FBEFDC", "#3A2E17")

CRITICAL = ("#C43D26", "#F0685A")         # 5,2:1
CRITICAL_BG = ("#FBE6E1", "#3A1F1B")

WHITE = "#FFFFFF"
SIDEBAR_TEXT = "#EAF1F8"
SIDEBAR_TEXT_MUTED = "#A9B9CB"

RADIUS_S = 4
RADIUS_M = 6

_MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro"]
_DIAS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"]


def data_extensa_pt(dt):
    """Formata uma data por extenso em português, sem depender do locale do SO."""
    return f"{_DIAS_PT[dt.weekday()]}, {dt.day} de {_MESES_PT[dt.month - 1]} de {dt.year}"


def resolve(color):
    """Resolve um par (claro, escuro) do tema para o valor concreto do modo atual —
    necessário para widgets tk/ttk nativos, que (ao contrário do CTk) não seguem
    `ctk.set_appearance_mode()` automaticamente."""
    if isinstance(color, tuple):
        return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
    return color


# ==========================================================================
# TIPOGRAFIA — escala 11 / 13 / 16 / 22, nunca abaixo de 11px
# ==========================================================================
_TAMANHO_MIN = 11


def font_display(size=22, weight="bold"):
    """Títulos de página e de diálogo."""
    return ctk.CTkFont(family="Segoe UI Semibold", size=max(size, _TAMANHO_MIN), weight=weight)


def font_body(size=13, weight="normal"):
    """Texto corrido, rótulos, botões."""
    return ctk.CTkFont(family="Segoe UI", size=max(size, _TAMANHO_MIN), weight=weight)


def font_mono(size=12, weight="normal"):
    """Só para dados: IDs, códigos, quantidades, datas, tempos (alinhamento tabular)."""
    return ctk.CTkFont(family="Cascadia Mono", size=max(size, _TAMANHO_MIN), weight=weight)


def font_eyebrow(size=11):
    """Rótulo pequeno em maiúsculas acima de um título, campo ou valor."""
    return ctk.CTkFont(family="Segoe UI", size=max(size, _TAMANHO_MIN), weight="bold")


# ==========================================================================
# COMPONENTES BÁSICOS
# ==========================================================================
_PILL_VARIANTS = {
    "ok": (SUCCESS_BG, SUCCESS),
    "run": (TEAL_BG, TEAL),
    "bad": (CRITICAL_BG, CRITICAL),
    "warn": (WARNING_BG, WARNING),
    "neutral": (SURFACE_ALT, TEXT_MUTED),
}


def pill(parent, text, variant="neutral"):
    """Chip de estado arredondado (ex: 'Concluída', 'Operacional')."""
    bg, fg = _PILL_VARIANTS.get(variant, _PILL_VARIANTS["neutral"])
    return ctk.CTkLabel(
        parent, text=f" {text} ", font=font_body(11, "bold"),
        fg_color=bg, text_color=fg, corner_radius=10, height=22,
    )


def kpi_card(parent, label, value="0", value_color=None):
    """Cartão de indicador (KPI): rótulo pequeno + valor grande em monoespaçada.
    Devolve o CTkLabel do valor, para o chamador atualizar o texto depois
    (`.configure(text=...)`) sem reconstruir o cartão.

    A largura pedida é pequena de propósito: com pack_propagate(False) o cartão
    fica com a largura pedida como mínimo, e o CTkFrame pede 200px por omissão —
    4 cartões numa janela estreita ficavam com o último cortado. O fill/expand
    reparte o espaço que sobra por igual."""
    card = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=RADIUS_M, border_width=1, border_color=BORDER, width=110, height=78)
    card.pack(side="left", fill="x", expand=True, padx=5)
    card.pack_propagate(False)

    ctk.CTkLabel(card, text=label.upper(), text_color=TEXT_MUTED, font=font_eyebrow(11), anchor="w").pack(anchor="w", padx=15, pady=(12, 0))
    lbl_valor = ctk.CTkLabel(card, text=value, text_color=value_color or TEXT, font=font_mono(24, "bold"), anchor="w")
    lbl_valor.pack(anchor="w", padx=15, pady=0)
    return lbl_valor


def entry(parent, **kwargs):
    """CTkEntry pré-estilizado consistente com o resto da app."""
    defaults = dict(fg_color=SURFACE_ALT, text_color=TEXT, border_color=BORDER, border_width=1, corner_radius=RADIUS_S,
                    placeholder_text_color=TEXT_MUTED, font=font_body(13))
    defaults.update(kwargs)
    return ctk.CTkEntry(parent, **defaults)


def combobox(parent, **kwargs):
    """CTkComboBox pré-estilizado consistente com o resto da app."""
    defaults = dict(fg_color=SURFACE_ALT, text_color=TEXT, border_color=BORDER, button_color=ACCENT,
                    button_hover_color=ACCENT_HOVER, font=font_body(13), dropdown_font=font_body(13))
    defaults.update(kwargs)
    return ctk.CTkComboBox(parent, **defaults)


def checkbox(parent, **kwargs):
    defaults = dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, checkmark_color=WHITE, border_color=TEXT_MUTED,
                    text_color=TEXT, font=font_body(12))
    defaults.update(kwargs)
    return ctk.CTkCheckBox(parent, **defaults)


def button_primary(parent, **kwargs):
    """Ação principal de uma tela ou diálogo (no máximo uma por contexto)."""
    defaults = dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=WHITE, corner_radius=RADIUS_S,
                    font=font_body(13, "bold"), text_color_disabled=("#C9D3DE", "#5C6B7D"))
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def button_action(parent, **kwargs):
    """Ação de criação/arranque (verbo positivo: nova ordem, iniciar fabrico) — teal."""
    defaults = dict(fg_color=TEAL, hover_color=TEAL_HOVER, text_color=WHITE, corner_radius=RADIUS_S,
                    font=font_body(13, "bold"), text_color_disabled=("#D5E9EC", "#5C6B7D"))
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def button_ghost(parent, **kwargs):
    """Ação secundária discreta (editar, clonar, exportar)."""
    defaults = dict(fg_color=TEAL_BG, hover_color=BORDER, text_color=TEAL, corner_radius=RADIUS_S,
                    font=font_body(12, "bold"), text_color_disabled=("#9DB9BE", "#4F6670"))
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def button_secondary(parent, **kwargs):
    """Neutro: Cancelar, Limpar, Fechar."""
    defaults = dict(fg_color=SURFACE_ALT, hover_color=BORDER, text_color=TEXT, corner_radius=RADIUS_S,
                    font=font_body(12), border_width=1, border_color=BORDER)
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def button_danger(parent, **kwargs):
    """Só para ações irreversíveis ou destrutivas (anular, eliminar)."""
    defaults = dict(fg_color=CRITICAL_BG, hover_color=("#F6CFC6", "#4A2722"), text_color=CRITICAL, corner_radius=RADIUS_S,
                    font=font_body(12, "bold"), text_color_disabled=("#E3A99E", "#6B3E37"))
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def card(parent, **kwargs):
    defaults = dict(fg_color=SURFACE, corner_radius=RADIUS_M, border_width=1, border_color=BORDER)
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


def secao(parent, titulo, cor_titulo=None):
    """Cartão com título pequeno em maiúsculas; devolve o frame onde pôr o conteúdo.
    O cartão já vem empacotado (fill x) — usar dentro de uma coluna/corpo."""
    frm = card(parent)
    frm.pack(fill="x", pady=(0, 12))
    ctk.CTkLabel(frm, text=titulo.upper(), font=font_eyebrow(11), text_color=cor_titulo or TEXT_MUTED,
                 anchor="w").pack(fill="x", padx=16, pady=(12, 4))
    corpo = ctk.CTkFrame(frm, fg_color="transparent")
    corpo.pack(fill="x", padx=16, pady=(0, 12))
    return corpo


def _texto_contrastado_por_estado(seg):
    """O CTkSegmentedButton só aceita UMA text_color para todos os botões. Com a
    seleção a navy (ACCENT) e as restantes opções claras, nenhuma cor única tem
    contraste nas duas — o texto escuro sobre navy ficava a ~1,4:1 (ilegível).
    Recolore o texto de cada botão sempre que a seleção muda: branco na opção
    selecionada, TEXT nas restantes.

    Usa os métodos internos de seleção do CTk; se uma versão futura os mudar de
    nome, sai sem fazer nada (o widget continua funcional, só sem este ajuste)."""
    if not all(hasattr(seg, a) for a in ("_select_button_by_value", "_unselect_button_by_value", "_buttons_dict")):
        return seg
    selecionar_orig = seg._select_button_by_value
    desselecionar_orig = seg._unselect_button_by_value

    def _selecionar(value):
        selecionar_orig(value)
        if value in seg._buttons_dict:
            seg._buttons_dict[value].configure(text_color=WHITE)

    def _desselecionar(value):
        desselecionar_orig(value)
        if value in seg._buttons_dict:
            seg._buttons_dict[value].configure(text_color=TEXT)

    seg._select_button_by_value = _selecionar
    seg._unselect_button_by_value = _desselecionar
    atual = seg.get()
    if atual in seg._buttons_dict:
        seg._buttons_dict[atual].configure(text_color=WHITE)
    return seg


def segmented(parent, values, command=None, **kwargs):
    """Seletor segmentado (período, estado, filtros) com a opção selecionada legível."""
    defaults = dict(fg_color=SURFACE_ALT, selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                    unselected_color=SURFACE_ALT, unselected_hover_color=BORDER, text_color=TEXT,
                    font=font_body(12))
    defaults.update(kwargs)
    return _texto_contrastado_por_estado(ctk.CTkSegmentedButton(parent, values=values, command=command, **defaults))


def tabview(parent, **kwargs):
    """CTkTabview com o mesmo estilo de abas do `segmented()`. Os separadores
    devem ser adicionados (.add) depois desta chamada — o ajuste de contraste
    tem de estar ativo antes de a primeira aba ser selecionada."""
    defaults = dict(fg_color=SURFACE, segmented_button_fg_color=SURFACE_ALT,
                    segmented_button_selected_color=ACCENT, segmented_button_selected_hover_color=ACCENT_HOVER,
                    segmented_button_unselected_color=SURFACE_ALT, segmented_button_unselected_hover_color=BORDER,
                    text_color=TEXT, border_width=1, border_color=BORDER)
    defaults.update(kwargs)
    tv = ctk.CTkTabview(parent, **defaults)
    seg = getattr(tv, "_segmented_button", None)
    if seg is not None:
        _texto_contrastado_por_estado(seg)
    return tv


# ==========================================================================
# LAYOUT
# ==========================================================================
def dimensionar_janela(janela, largura, altura, fracao_largura=0.95, fracao_altura=0.85):
    """Aplica `largura`x`altura` (unidades CTk, antes da escala do Windows) à
    janela, mas nunca maior do que a fração indicada do ecrã — e centra-a.

    O CTk multiplica a geometria pela escala do Windows (125%, 150%…), mas
    winfo_screen*() devolve píxeis físicos: um diálogo de 760 de altura num
    portátil 1366x768 a 125% ocupa 950px físicos e o rodapé (botão de gravar)
    fica fora do ecrã. Aqui o limite é calculado já descontando a escala.
    Devolve (largura, altura) efetivas, nas mesmas unidades CTk."""
    try:
        escala = ctk.ScalingTracker.get_window_scaling(janela)
    except Exception:
        escala = 1.0
    ecra_l, ecra_a = janela.winfo_screenwidth(), janela.winfo_screenheight()
    larg = min(largura, int(ecra_l * fracao_largura / escala))
    alt = min(altura, int(ecra_a * fracao_altura / escala))
    pos_x = max(0, (ecra_l - round(larg * escala)) // 2)
    pos_y = max(0, (ecra_a - round(alt * escala)) // 3)
    janela.geometry(f"{larg}x{alt}+{pos_x}+{pos_y}")
    return larg, alt


def fluxo_horizontal(container, filhos, espaco=16, espaco_linhas=8, max_linhas=3):
    """Dispõe `filhos` (já criados como filhos de `container`, sem gestor de
    geometria) lado a lado, passando para a linha seguinte quando já não cabem
    na largura — como texto a quebrar linha. Reorganiza ao redimensionar.

    Os filhos são empacotados dentro de frames-linha com `in_=` (o Tk permite
    gerir um widget dentro de um descendente do seu pai), por isso não é preciso
    recriá-los. Usado na barra de filtros das Ordens, que num portátil a 125%
    empurrava "Cód. falha" e "Limpar" para fora do ecrã."""
    linhas = [ctk.CTkFrame(container, fg_color="transparent") for _ in range(max_linhas)]
    for f in filhos:
        f.lift()  # acima dos frames-linha na ordem de empilhamento, senão ficavam tapados
    estado = {"atribuicao": None}

    def _reorganizar(event=None):
        largura = container.winfo_width()
        if largura <= 1:
            return
        try:
            escala = ctk.ScalingTracker.get_widget_scaling(container)
        except Exception:
            escala = 1.0
        esp = espaco * escala
        atribuicao, linha, x = [], 0, 0
        for f in filhos:
            w = f.winfo_reqwidth()
            if x > 0 and x + w > largura and linha < max_linhas - 1:
                linha, x = linha + 1, 0
            atribuicao.append(linha)
            x += w + esp
        if atribuicao == estado["atribuicao"]:
            return  # nada mudou — evita re-empacotar a cada <Configure> de altura
        estado["atribuicao"] = atribuicao
        for f in filhos:
            f.pack_forget()
        for frm in linhas:
            frm.pack_forget()
        for i in sorted(set(atribuicao)):
            linhas[i].pack(fill="x", pady=(0 if i == 0 else espaco_linhas, 0))
        for f, i in zip(filhos, atribuicao):
            f.pack(in_=linhas[i], side="left", padx=(0, espaco))

    container.bind("<Configure>", _reorganizar, add="+")
    _reorganizar()
    return _reorganizar


def rodape_fixo(janela):
    """Rodapé que fica SEMPRE visível: é empacotado antes de tudo o resto com
    side="bottom", por isso é o corpo (normalmente scrollável) que encolhe
    quando a janela é baixa — nunca o botão de gravar. Os botões devem ser
    criados dentro do frame devolvido."""
    frm = ctk.CTkFrame(janela, fg_color=SURFACE, corner_radius=0, border_width=1, border_color=BORDER)
    frm.pack(side="bottom", fill="x")
    return frm


def page_header(parent, eyebrow, title, meta=""):
    """Cabeçalho de página compacto: eyebrow + título à esquerda e um espaço
    para ações à direita (`cabecalho.acoes`, onde vão os botões da página).

    Substitui a versão de 92px com grelha decorativa, que num portátil a 125%
    deixava a tabela das Ordens com 3 linhas visíveis."""
    cab = ctk.CTkFrame(parent, fg_color="transparent")
    esq = ctk.CTkFrame(cab, fg_color="transparent")
    esq.pack(side="left", fill="y")
    ctk.CTkLabel(esq, text=eyebrow.upper(), font=font_eyebrow(11), text_color=TEAL, anchor="w").pack(fill="x")
    linha = ctk.CTkFrame(esq, fg_color="transparent")
    linha.pack(fill="x")
    ctk.CTkLabel(linha, text=title, font=font_display(22), text_color=TEXT, anchor="w").pack(side="left")
    if meta:
        ctk.CTkLabel(linha, text=f"  ·  {meta}", font=font_body(12), text_color=TEXT_MUTED, anchor="w").pack(side="left", pady=(4, 0))
    # width/height=1: sem botões, um CTkFrame vazio pedia 200x200 e o cabeçalho
    # ficava com 200px de altura (ex: Manutenção, Configuração).
    cab.acoes = ctk.CTkFrame(cab, fg_color="transparent", width=1, height=1)
    cab.acoes.pack(side="right", anchor="s")
    return cab


# ==========================================================================
# TABELAS
# ==========================================================================
# Texto por variante de estado. "ok" e "neutral" ficam neutros DE PROPÓSITO:
# antes, cada linha Concluída era pintada de verde e a tabela inteira virava
# um bloco verde a 3,5:1 — a cor deixava de assinalar o que importa.
_TAG_TEXTO = {
    "ok": TEXT,
    "neutral": TEXT,
    "muted": TEXT_MUTED,
    "run": TEAL,
    "warn": WARNING,
    "bad": CRITICAL,
}

_FONTE_TABELA = ("Segoe UI", 10)
_FONTE_TABELA_CAB = ("Segoe UI Semibold", 10)


def aplicar_estilo_tabelas():
    """Estilo único "AM.Treeview" para todas as tabelas (antes havia 4 estilos
    com alturas de linha diferentes, e cada tab chamava theme_use("default")).
    A altura de linha deriva da métrica da fonte, que o Tk já escala com o DPI —
    um valor fixo em píxeis ficava apertado a 125%."""
    style = ttk.Style()
    if style.theme_use() != "default":
        style.theme_use("default")
    altura = tkfont.Font(font=_FONTE_TABELA).metrics("linespace") + 14
    style.configure("AM.Treeview", background=SURFACE[0], foreground=TEXT[0], fieldbackground=SURFACE[0],
                    borderwidth=0, rowheight=altura, font=_FONTE_TABELA)
    style.configure("AM.Treeview.Heading", background=SURFACE_ALT[0], foreground=TEXT_MUTED[0],
                    borderwidth=0, relief="flat", font=_FONTE_TABELA_CAB, padding=(6, 6))
    style.map("AM.Treeview", background=[("selected", ACCENT[0])], foreground=[("selected", WHITE)])
    style.map("AM.Treeview.Heading", background=[("active", BORDER[0])])
    return style


def tabela(parent, colunas, altura=None, scroll_horizontal=False):
    """Cria uma tabela no estilo da app dentro de um frame com scrollbar.

    colunas: [(chave, título, largura, âncora[, estica])] — `estica` (por omissão
    True para colunas de texto alinhadas à esquerda) diz se a coluna absorve a
    largura que sobra.
    Devolve (frame, tree): o chamador empacota o frame.
    As linhas recebem a cor pela tag "tag_<variante>" (ver _TAG_TEXTO)."""
    aplicar_estilo_tabelas()
    frm = ctk.CTkFrame(parent, fg_color="transparent")
    chaves = [c[0] for c in colunas]
    opcoes = dict(columns=chaves, show="headings", style="AM.Treeview")
    if altura:
        opcoes["height"] = altura
    tree = ttk.Treeview(frm, **opcoes)
    for col in colunas:
        chave, titulo, largura, ancora = col[:4]
        estica = col[4] if len(col) > 4 else ancora == "w"
        tree.heading(chave, text=titulo, anchor=ancora)
        tree.column(chave, width=largura, minwidth=40, anchor=ancora, stretch=estica)
    for variante, cor in _TAG_TEXTO.items():
        tree.tag_configure(f"tag_{variante}", foreground=cor[0])

    sb = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    if scroll_horizontal:
        sbx = ttk.Scrollbar(frm, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=sbx.set)
        sbx.pack(side="bottom", fill="x")
    sb.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return frm, tree


def ligar_a_selecao(tree, botoes):
    """Ativa os `botoes` só quando há uma linha selecionada. Antes estavam sempre
    ativos e, sem seleção, não faziam nada (nem avisavam). Devolve a função de
    atualização, para chamar depois de repovoar a tabela."""
    def _atualizar(event=None):
        ativo = bool(tree.selection())
        for b in botoes:
            definir_ativo(b, ativo)
    tree.bind("<<TreeviewSelect>>", _atualizar, add="+")
    _atualizar()
    return _atualizar


def definir_ativo(botao, ativo: bool):
    """Ativa/desativa um botão com aspeto coerente. Só mudar o `state` não
    chega: um botão principal (navy/teal) desativado continuava a parecer
    clicável. Desativado = fundo neutro e texto atenuado."""
    if not botao.winfo_exists():
        return
    if not hasattr(botao, "_cor_ativa"):
        botao._cor_ativa = botao.cget("fg_color")
    botao.configure(state="normal" if ativo else "disabled",
                    fg_color=botao._cor_ativa if ativo else SURFACE_ALT, text_color_disabled=TEXT_MUTED)


class TreeviewPillColumn:
    """Sobrepõe pills coloridas (fundo + texto) numa coluna de um ttk.Treeview.

    O Treeview só suporta cor de texto por LINHA inteira (tag_configure), nunca
    por célula isolada — para ter uma pill só na coluna Estado, sobrepomos um
    CTkLabel exatamente por cima da célula, e realinhamos sempre que a tabela
    faz scroll, é redimensionada, ou é repovoada.

    Usar só em tabelas pequenas (ex: agenda de Manutenção): o realinhamento
    percorre todas as linhas. Tabelas grandes usam as tags de `tabela()`.
    """

    def __init__(self, tree, coluna):
        self.tree = tree
        self.coluna = coluna
        self._dados = {}   # item_id -> (texto, variant)
        self._pills = {}   # item_id -> CTkLabel

        tree.bind("<Configure>", self._reposicionar, add="+")
        tree.bind("<<TreeviewSelect>>", lambda e: tree.after(1, self._reposicionar), add="+")
        tree.bind("<Destroy>", self._ao_destruir, add="+")

        anterior = tree.cget("yscrollcommand")

        def _on_scroll(*args):
            if anterior:
                tree.tk.call(anterior, *args)
            self._reposicionar()

        tree.configure(yscrollcommand=_on_scroll)

        self._poll()  # rede de segurança: cobre scroll por roda do rato/teclado e
                       # qualquer reconfiguração futura do yscrollcommand que ignore este wrapper

    def _poll(self):
        if not self.tree.winfo_exists():
            return
        self._reposicionar()
        self.tree.after(250, self._poll)

    def definir_dados(self, dados):
        """dados: {item_id: (texto, variant)}. Chamar sempre que a tabela for repovoada."""
        self._dados = dados
        for item_id in list(self._pills):
            if item_id not in dados:
                self._pills.pop(item_id).destroy()
        self._reposicionar()

    def _reposicionar(self, event=None):
        if not self.tree.winfo_exists():
            return
        visiveis = set(self.tree.get_children())
        base_x, base_y = self.tree.winfo_x(), self.tree.winfo_y()
        # bbox()/winfo_x() estão em píxeis físicos, mas o place()/configure() de um
        # widget CTk multiplicam pela escala — sem dividir, a 125% as pills iam
        # parar fora da tabela (e não se viam).
        try:
            escala = ctk.ScalingTracker.get_widget_scaling(self.tree.master)
        except Exception:
            escala = 1.0
        alt_pill = 20

        for item_id, (texto, variant) in self._dados.items():
            bbox = self.tree.bbox(item_id, self.coluna) if item_id in visiveis else None
            if not bbox:
                pill_widget = self._pills.get(item_id)
                if pill_widget is not None:
                    pill_widget.place_forget()
                continue

            x, y, w, h = bbox
            pill_widget = self._pills.get(item_id)
            if pill_widget is None or not pill_widget.winfo_exists():
                pill_widget = pill(self.tree.master, texto, variant)
                self._pills[item_id] = pill_widget
            else:
                # Atualiza texto e cores caso o estado tenha mudado desde a última renderização
                bg, fg = _PILL_VARIANTS.get(variant, _PILL_VARIANTS["neutral"])
                pill_widget.configure(text=f" {texto} ", fg_color=bg, text_color=fg)
            pill_widget.configure(width=max((w - 8) / escala, 10), height=alt_pill)
            topo = base_y + y + max((h - alt_pill * escala) / 2, 0)
            pill_widget.place(x=(base_x + x + 4) / escala, y=topo / escala)

    def _ao_destruir(self, event=None):
        for pill_widget in self._pills.values():
            if pill_widget.winfo_exists():
                pill_widget.destroy()
        self._pills.clear()


# ==========================================================================
# FEEDBACK
# ==========================================================================
_TOAST_CORES = {"ok": SUCCESS, "info": TEAL, "warn": WARNING, "bad": CRITICAL}


def toast(widget, texto, variante="ok", duracao_ms=3500):
    """Notificação não modal no canto inferior direito da janela principal.
    Substitui os messagebox de "Sucesso" (um clique em OK por cada ação) —
    erros e confirmações continuam em messagebox, porque exigem resposta."""
    try:
        top = widget.winfo_toplevel()
        while getattr(top, "master", None) is not None and isinstance(top, ctk.CTkToplevel):
            # se o diálogo de origem vai fechar, mostra na janela por baixo dele
            top = top.master.winfo_toplevel()
    except Exception:
        return None
    frm = ctk.CTkFrame(top, fg_color=("#15212E", "#E7ECF2"), corner_radius=RADIUS_M)
    barra = ctk.CTkFrame(frm, fg_color=_TOAST_CORES.get(variante, TEAL), width=5, corner_radius=2)
    barra.pack(side="left", fill="y", padx=(8, 0), pady=8)
    ctk.CTkLabel(frm, text=texto, text_color=("#FFFFFF", "#15212E"), font=font_body(13), justify="left",
                 wraplength=380).pack(side="left", padx=(10, 16), pady=10)
    frm.place(relx=1.0, rely=1.0, x=-24, y=-24, anchor="se")
    frm.lift()

    def _fechar():
        if frm.winfo_exists():
            frm.destroy()
    top.after(duracao_ms, _fechar)
    return frm


# ==========================================================================
# DIÁLOGOS
# ==========================================================================
class Dialogo(ctk.CTkToplevel):
    """Janela modal base de toda a app.

    - Título (+ subtítulo) no topo, com `self.cabecalho_acoes` à direita.
    - `self.corpo`: com scroll (por omissão) ou um frame simples.
    - Rodapé FIXO com [Cancelar] [ação principal] à direita, `self.rodape_info`
      à esquerda (texto de contexto) e `self.rodape_esquerda` (ex: eliminar).
    - Enter confirma (exceto dentro de caixas de texto multi-linha), Esc cancela.
    - Tamanho relativo ao ecrã (`dimensionar_janela`), redimensionável na altura.

    Subclasses implementam `confirmar()`. Com `texto_acao=None` o diálogo só tem
    um botão "Fechar" (diálogos informativos)."""

    def __init__(self, parent, titulo, largura=520, altura=460, texto_acao="Guardar",
                 subtitulo="", scroll=True, estilo_acao="primary", mostrar_titulo=True):
        super().__init__(parent)
        self.title(titulo)
        self.configure(fg_color=BG)
        _, alt = dimensionar_janela(self, largura, altura)
        self.minsize(min(largura, 360), min(alt, 260))
        self.resizable(False, True)
        self.transient(parent)
        self.grab_set()

        # Rodapé primeiro (side="bottom"): é o corpo que encolhe, nunca os botões.
        self.rodape = rodape_fixo(self)
        frm_botoes = ctk.CTkFrame(self.rodape, fg_color="transparent")
        frm_botoes.pack(fill="x", padx=20, pady=14)
        # width/height=1: um CTkFrame vazio pede 200x200 por omissão e esticava o rodapé
        self.rodape_esquerda = ctk.CTkFrame(frm_botoes, fg_color="transparent", width=1, height=1)
        self.rodape_esquerda.pack(side="left")
        self.rodape_info = ctk.CTkLabel(frm_botoes, text="", font=font_body(11), text_color=TEXT_MUTED,
                                        anchor="w", justify="left")
        self.rodape_info.pack(side="left", padx=(0, 12))

        if texto_acao:
            fabrica = {"primary": button_primary, "action": button_action, "danger": button_danger}[estilo_acao]
            self.btn_acao = fabrica(frm_botoes, text=texto_acao, height=38, command=self.confirmar)
            self.btn_acao.pack(side="right")
            self.btn_cancelar = button_secondary(frm_botoes, text="Cancelar", height=38, width=100, command=self.cancelar)
            self.btn_cancelar.pack(side="right", padx=(0, 10))
        else:
            self.btn_acao = None
            self.btn_cancelar = button_primary(frm_botoes, text="Fechar", height=38, width=110, command=self.cancelar)
            self.btn_cancelar.pack(side="right")

        self.cabecalho_acoes = None
        if mostrar_titulo:
            cab = ctk.CTkFrame(self, fg_color="transparent")
            cab.pack(side="top", fill="x", padx=20, pady=(16, 6))
            esq = ctk.CTkFrame(cab, fg_color="transparent")
            esq.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(esq, text=titulo, font=font_display(17), text_color=TEXT, anchor="w").pack(fill="x")
            if subtitulo:
                ctk.CTkLabel(esq, text=subtitulo, font=font_body(12), text_color=TEXT_MUTED, anchor="w",
                             justify="left", wraplength=max(largura - 80, 200)).pack(fill="x")
            self.cabecalho_acoes = ctk.CTkFrame(cab, fg_color="transparent", width=1, height=1)
            self.cabecalho_acoes.pack(side="right")

        if scroll:
            self.corpo = ctk.CTkScrollableFrame(self, fg_color="transparent")
            self.corpo.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 8))
        else:
            self.corpo = ctk.CTkFrame(self, fg_color="transparent")
            self.corpo.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 12))

        self.bind("<Escape>", lambda e: self.cancelar())
        self.bind("<Return>", self._ao_enter)

    def _ao_enter(self, event):
        if isinstance(event.widget, tk.Text):
            return  # Enter numa caixa de texto multi-linha é uma nova linha
        if self.btn_acao is not None and str(self.btn_acao.cget("state")) != "disabled":
            self.confirmar()

    def confirmar(self):
        """Ação principal — as subclasses implementam."""
        self.destroy()

    def cancelar(self):
        self.destroy()


def rotulo_campo(parent, texto, obrigatorio=False):
    """Rótulo de campo de formulário (maiúsculas pequenas, com * se obrigatório)."""
    return ctk.CTkLabel(parent, text=texto.upper() + (" *" if obrigatorio else ""), font=font_eyebrow(11),
                        text_color=TEXT_MUTED, anchor="w")
