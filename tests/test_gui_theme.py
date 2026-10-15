import customtkinter as ctk
import pytest

from gui import theme


def _texto_do_botao(seg, valor):
    return seg._buttons_dict[valor].cget("text_color")


# ---------- Contraste das opções selecionadas ----------

def test_segmented_selecao_com_texto_branco_e_restantes_escuras(ctk_root):
    seg = theme.segmented(ctk_root, values=["7 dias", "30 dias", "Tudo"])
    seg.set("30 dias")

    assert _texto_do_botao(seg, "30 dias") == theme.WHITE
    assert _texto_do_botao(seg, "7 dias") == theme.TEXT
    assert _texto_do_botao(seg, "Tudo") == theme.TEXT


def test_segmented_recolore_ao_mudar_de_selecao(ctk_root):
    seg = theme.segmented(ctk_root, values=["A", "B"])
    seg.set("A")
    seg.set("B")

    assert _texto_do_botao(seg, "B") == theme.WHITE
    assert _texto_do_botao(seg, "A") == theme.TEXT


def test_tabview_aba_ativa_com_texto_branco(ctk_root):
    tv = theme.tabview(ctk_root)
    tv.add("Agenda")
    tv.add("Histórico")
    tv.set("Histórico")

    seg = tv._segmented_button
    assert _texto_do_botao(seg, "Histórico") == theme.WHITE
    assert _texto_do_botao(seg, "Agenda") == theme.TEXT


# ---------- Dimensionamento relativo ao ecrã ----------

@pytest.fixture
def janela(ctk_root):
    win = ctk.CTkToplevel(ctk_root)
    win.withdraw()
    yield win
    win.destroy()


def _ecra(monkeypatch, janela, largura, altura, escala):
    monkeypatch.setattr(janela, "winfo_screenwidth", lambda: largura)
    monkeypatch.setattr(janela, "winfo_screenheight", lambda: altura)
    monkeypatch.setattr(ctk.ScalingTracker, "get_window_scaling", classmethod(lambda cls, w: escala))


def test_dimensionar_janela_respeita_tamanho_pedido_em_ecra_grande(monkeypatch, janela):
    _ecra(monkeypatch, janela, 1920, 1080, 1.0)

    assert theme.dimensionar_janela(janela, 820, 820) == (820, 820)


def test_dimensionar_janela_desconta_escala_do_windows(monkeypatch, janela):
    # Portátil 1366x768 a 125%: cabem 768*0.85/1.25 = 522 unidades CTk de altura.
    # O cálculo antigo (fechar_ordem) comparava unidades CTk com píxeis físicos
    # e deixava 652, que a 125% ocupam 815px — mais do que o ecrã.
    _ecra(monkeypatch, janela, 1366, 768, 1.25)

    largura, altura = theme.dimensionar_janela(janela, 820, 820)

    assert altura == 522
    assert largura == 820
    assert altura * 1.25 <= 768


def test_kpi_card_nao_impoe_largura_minima_de_200(ctk_root):
    # Com a largura por omissão do CTkFrame (200), 4 cartões no Resumo do Dia
    # (640 de largura útil) deixavam o 4.º cortado.
    frm = ctk.CTkFrame(ctk_root)
    theme.kpi_card(frm, "Concluídas", "1")

    assert frm.winfo_children()[0].cget("width") <= 120
