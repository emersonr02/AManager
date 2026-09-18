import pytest

from services.maquina_service import MaquinaService
from gui.dialogs.logistica_maquina import JanelaLogisticaMaquina


@pytest.fixture
def avisos(monkeypatch):
    chamadas = {"warning": [], "askyesno": True}
    monkeypatch.setattr("gui.dialogs.logistica_maquina.messagebox.showwarning", lambda t, m: chamadas["warning"].append(m))
    monkeypatch.setattr("gui.dialogs.logistica_maquina.messagebox.askyesno", lambda t, m: chamadas["askyesno"])
    return chamadas


def test_modo_cadastro_campos_vazios_por_omissao(arquivo_maquinas, ctk_root, avisos):
    win = JanelaLogisticaMaquina(ctk_root, None, lambda: None, None, None)

    assert win.ent_id.get() == ""
    assert win.ent_id.cget("state") == "normal"
    assert win.ent_modelo.get() == ""
    assert win.ent_notas.get() == "OK"
    win.destroy()


def test_modo_edicao_preenche_e_bloqueia_id(arquivo_maquinas, ctk_root, avisos):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer 1", tech="SLA", estado="Operacional", manutencao="Trocar resina", url_img="http://x/img.png", modelo="Formlabs Form 3L")
    dados = MaquinaService.obter_todas()[0]

    win = JanelaLogisticaMaquina(ctk_root, dados, lambda: None, None, None)

    assert win.ent_id.get() == "M1"
    assert win.ent_id.cget("state") == "disabled"
    assert win.ent_nome.get() == "Printer 1"
    assert win.ent_modelo.get() == "Formlabs Form 3L"
    assert win.cmb_tech.get() == "SLA"
    assert win.ent_notas.get() == "Trocar resina"
    assert win.ent_url_img.get() == "http://x/img.png"
    win.destroy()


def test_gravar_sem_id_ou_nome_bloqueia(arquivo_maquinas, ctk_root, avisos):
    win = JanelaLogisticaMaquina(ctk_root, None, lambda: None, None, None)
    win.ent_nome.insert(0, "Sem ID")

    win.gravar()

    assert avisos["warning"]
    assert MaquinaService.obter_todas() == []
    win.destroy()


def test_gravar_cadastro_novo_persiste_e_chama_callback(arquivo_maquinas, ctk_root, avisos):
    chamado = []
    win = JanelaLogisticaMaquina(ctk_root, None, lambda: chamado.append(True), None, None)
    win.ent_id.insert(0, "NOVA-1")
    win.ent_nome.insert(0, "Impressora Nova")
    win.cmb_tech.set("FDM")
    win.cmb_est.set("Operacional")

    win.gravar()

    maquinas = MaquinaService.obter_todas()
    assert len(maquinas) == 1
    assert maquinas[0]["id"] == "NOVA-1"
    assert chamado == [True]
    assert win.winfo_exists() == 0


def test_gravar_grava_modelo_informado(arquivo_maquinas, ctk_root, avisos):
    win = JanelaLogisticaMaquina(ctk_root, None, lambda: None, None, None)
    win.ent_id.insert(0, "M1")
    win.ent_nome.insert(0, "Printer")
    win.ent_modelo.insert(0, "Bambu Lab X1C")

    win.gravar()

    assert MaquinaService.obter_todas()[0]["modelo"] == "Bambu Lab X1C"


def test_gravar_notas_vazias_usa_ok_por_omissao(arquivo_maquinas, ctk_root, avisos):
    win = JanelaLogisticaMaquina(ctk_root, None, lambda: None, None, None)
    win.ent_id.insert(0, "M1")
    win.ent_nome.insert(0, "Printer")
    win.ent_notas.delete(0, "end")  # limpa o "OK" pré-preenchido

    win.gravar()

    assert MaquinaService.obter_todas()[0]["manutencao"] == "OK"


def test_gravar_edicao_atualiza_sem_duplicar(arquivo_maquinas, ctk_root, avisos):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer 1", tech="FDM", estado="Operacional", manutencao="OK")
    dados = MaquinaService.obter_todas()[0]

    win = JanelaLogisticaMaquina(ctk_root, dados, lambda: None, None, None)
    win.ent_nome.delete(0, "end")
    win.ent_nome.insert(0, "Printer 1 Renomeada")

    win.gravar()

    maquinas = MaquinaService.obter_todas()
    assert len(maquinas) == 1
    assert maquinas[0]["nome"] == "Printer 1 Renomeada"


def test_remover_com_confirmacao_apaga_ativo(arquivo_maquinas, ctk_root, avisos):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer 1", tech="FDM", estado="Operacional", manutencao="OK")
    dados = MaquinaService.obter_todas()[0]
    chamado = []
    win = JanelaLogisticaMaquina(ctk_root, dados, lambda: chamado.append(True), None, None)

    avisos["askyesno"] = True
    win.remover()

    assert MaquinaService.obter_todas() == []
    assert chamado == [True]
    assert win.winfo_exists() == 0


def test_remover_sem_confirmacao_mantem_ativo(arquivo_maquinas, ctk_root, avisos):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer 1", tech="FDM", estado="Operacional", manutencao="OK")
    dados = MaquinaService.obter_todas()[0]
    win = JanelaLogisticaMaquina(ctk_root, dados, lambda: None, None, None)

    avisos["askyesno"] = False
    win.remover()

    assert len(MaquinaService.obter_todas()) == 1
    assert win.winfo_exists() == 1
    win.destroy()
