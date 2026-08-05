from services.maquina_service import MaquinaService


def test_salvar_maquina_nova_cria_exatamente_um_registo(arquivo_maquinas):
    MaquinaService.salvar_maquina("M1", "Impressora 1", "FDM", "Operacional", "OK", "http://x/img.png")

    maquinas = MaquinaService.obter_todas()
    assert len(maquinas) == 1
    assert maquinas[0]["url_img"] == "http://x/img.png"


def test_salvar_maquina_existente_atualiza_sem_duplicar(arquivo_maquinas):
    MaquinaService.salvar_maquina("M1", "Impressora 1", "FDM", "Operacional", "OK", "")
    MaquinaService.salvar_maquina("M1", "Impressora 1 Atualizada", "FDM", "Manutenção", "Pendente", "")

    maquinas = MaquinaService.obter_todas()
    assert len(maquinas) == 1
    assert maquinas[0]["nome"] == "Impressora 1 Atualizada"
    assert maquinas[0]["estado"] == "Manutenção"


def test_remover_maquina(arquivo_maquinas):
    MaquinaService.salvar_maquina("M1", "Impressora 1", "FDM", "Operacional", "OK", "")
    MaquinaService.remover_maquina("M1")

    assert MaquinaService.obter_todas() == []


def test_obter_ativas_por_tecnologia_filtra_operacionais(arquivo_maquinas):
    MaquinaService.salvar_maquina("M1", "Impressora 1", "FDM", "Operacional", "OK", "")
    MaquinaService.salvar_maquina("M2", "Impressora 2", "FDM", "Manutenção", "Pendente", "")
    MaquinaService.salvar_maquina("M3", "Impressora 3", "SLA", "Operacional", "OK", "")

    ativas_fdm = MaquinaService.obter_ativas_por_tecnologia("FDM")

    assert ativas_fdm == ["M1"]
