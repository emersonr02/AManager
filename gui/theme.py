"""Sistema de design central (cor, tipografia, componentes) do AManager.

Cores são definidas como tuplos (claro, escuro) — o CustomTkinter escolhe
automaticamente o valor certo consoante `ctk.set_appearance_mode()`, e
atualiza-os ao vivo quando o modo muda, sem código extra de repintura.
"""

import customtkinter as ctk
import tkinter as tk

# ==========================================================================
# COR
# ==========================================================================
BG = ("#F3F6FA", "#12161C")
SURFACE = ("#FFFFFF", "#1A212A")
SURFACE_ALT = ("#EBF0F6", "#212932")
BORDER = ("#DCE3EB", "#2B3542")

TEXT = ("#15212E", "#E7ECF2")
TEXT_MUTED = ("#5C6B7D", "#93A2B4")

ACCENT = ("#123A5E", "#5C9CD6")           # ação primária / marca
ACCENT_STRONG = ("#0A2740", "#0A2740")    # fundo da sidebar (fixo, não segue o modo)
ACCENT_HOVER = ("#0A2740", "#7FB4E6")

TEAL = ("#0A7E8C", "#3FC1CE")             # ação secundária / "em produção"
TEAL_BG = ("#E3F0F2", "#123339")
TEAL_HOVER = ("#08616C", "#59CDD8")

SUCCESS = ("#1F9D55", "#3BC17E")
SUCCESS_BG = ("#E6F5EC", "#1E3A2C")

WARNING = ("#B4720A", "#E3A23D")
WARNING_BG = ("#FBEFDC", "#3A2E17")

CRITICAL = ("#C43D26", "#F0685A")
CRITICAL_BG = ("#FBE6E1", "#3A1F1B")

WHITE = "#FFFFFF"
SIDEBAR_TEXT = "#EAF1F8"
SIDEBAR_TEXT_MUTED = "#93A6BB"

GRID_LINE = ("#DCE7F2", "#232B35")

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
# TIPOGRAFIA
# ==========================================================================
def font_display(size=22, weight="bold"):
    """Títulos de página — condensada, com peso."""
    return ctk.CTkFont(family="Segoe UI Semibold", size=size, weight=weight)


def font_body(size=13, weight="normal"):
    """Texto corrido, labels, botões."""
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


def font_mono(size=12, weight="normal"):
    """Dados: IDs, códigos, quantidades, datas, tempos — alinhamento tabular."""
    return ctk.CTkFont(family="Cascadia Mono", size=size, weight=weight)


def font_eyebrow(size=10):
    """Rótulo pequeno em maiúsculas acima de um título ou valor."""
    return ctk.CTkFont(family="Cascadia Mono", size=size, weight="bold")


# ==========================================================================
# COMPONENTES
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


def kpi_card(parent, label, value, caption="", value_variant=None):
    """Cartão de indicador (KPI): rótulo pequeno + valor grande em monoespaçada + legenda."""
    value_color = {"warn": WARNING, "bad": CRITICAL}.get(value_variant, TEXT)

    card = ctk.CTkFrame(parent, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=RADIUS_M)
    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=14, pady=12)

    ctk.CTkLabel(inner, text=label.upper(), font=font_eyebrow(10), text_color=TEAL, anchor="w").pack(fill="x")
    ctk.CTkLabel(inner, text=str(value), font=font_mono(26, "bold"), text_color=value_color, anchor="w").pack(fill="x", pady=(4, 0))
    if caption:
        ctk.CTkLabel(inner, text=caption, font=font_body(11), text_color=TEXT_MUTED, anchor="w").pack(fill="x")

    return card


def entry(parent, **kwargs):
    """CTkEntry pré-estilizado consistente com o resto da app."""
    defaults = dict(fg_color=SURFACE_ALT, text_color=TEXT, border_color=BORDER, border_width=1, corner_radius=RADIUS_S)
    defaults.update(kwargs)
    return ctk.CTkEntry(parent, **defaults)


def combobox(parent, **kwargs):
    """CTkComboBox pré-estilizado consistente com o resto da app."""
    defaults = dict(fg_color=SURFACE_ALT, text_color=TEXT, border_color=BORDER, button_color=ACCENT, button_hover_color=ACCENT_HOVER)
    defaults.update(kwargs)
    return ctk.CTkComboBox(parent, **defaults)


def button_primary(parent, **kwargs):
    defaults = dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=WHITE, corner_radius=RADIUS_S, font=font_body(13, "bold"))
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def button_action(parent, **kwargs):
    """Botão de ação secundária (verbo positivo: adicionar, iniciar) — teal."""
    defaults = dict(fg_color=TEAL, hover_color=TEAL_HOVER, text_color=WHITE, corner_radius=RADIUS_S, font=font_body(13, "bold"))
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def button_ghost(parent, **kwargs):
    """Botão de ação secundária discreta (editar, gerir)."""
    defaults = dict(fg_color=TEAL_BG, hover_color=BORDER, text_color=TEAL, corner_radius=RADIUS_S, font=font_body(12, "bold"))
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def button_danger(parent, **kwargs):
    defaults = dict(fg_color=CRITICAL_BG, hover_color=CRITICAL, text_color=CRITICAL, corner_radius=RADIUS_S, font=font_body(12, "bold"))
    defaults.update(kwargs)
    return ctk.CTkButton(parent, **defaults)


def page_header(parent, eyebrow, title, meta=""):
    """Cabeçalho de página: eyebrow + título + meta, sobre um grid subtil (referência
    à mesa de impressão) que se redesenha sozinho quando a janela é redimensionada."""
    altura = 92
    canvas = tk.Canvas(parent, height=altura, bg=resolve(BG), highlightthickness=0)

    def _desenhar(event=None):
        canvas.delete("grid")
        largura = canvas.winfo_width()
        passo = 22
        cor = resolve(GRID_LINE)
        for x in range(0, largura, passo):
            canvas.create_line(x, 0, x, altura, fill=cor, tags="grid")
        for y in range(0, altura, passo):
            canvas.create_line(0, y, largura, y, fill=cor, tags="grid")
        canvas.tag_lower("grid")

    canvas.bind("<Configure>", _desenhar)

    inner = ctk.CTkFrame(canvas, fg_color="transparent")
    ctk.CTkLabel(inner, text=eyebrow.upper(), font=font_eyebrow(10), text_color=TEAL, anchor="w").pack(fill="x")
    ctk.CTkLabel(inner, text=title, font=font_display(24), text_color=TEXT, anchor="w").pack(fill="x", pady=(2, 0))
    if meta:
        ctk.CTkLabel(inner, text=meta, font=font_mono(11), text_color=TEXT_MUTED, anchor="w").pack(fill="x")
    canvas.create_window(2, altura // 2, anchor="w", window=inner)

    return canvas


class TreeviewPillColumn:
    """Sobrepõe pills coloridas (fundo + texto) numa coluna de um ttk.Treeview.

    O Treeview só suporta cor de texto por LINHA inteira (tag_configure), nunca
    por célula isolada — para ter uma pill só na coluna Estado, sobrepomos um
    CTkLabel exatamente por cima da célula, e realinhamos sempre que a tabela
    faz scroll, é redimensionada, ou é repovoada.
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
            pill_widget.configure(width=max(w - 8, 10), height=20)
            pill_widget.place(x=base_x + x + 4, y=base_y + y + max((h - 20) // 2, 0))

    def _ao_destruir(self, event=None):
        for pill_widget in self._pills.values():
            if pill_widget.winfo_exists():
                pill_widget.destroy()
        self._pills.clear()
