from datetime import datetime, timedelta

from database.json_manager import JSONManager
from services.maquina_service import MaquinaService
from services.manutencao_service import ManutencaoService
from gui.parque_tab import ParqueTab


def _labels_texto(container):
    textos = []
    for child in container.winfo_children():
        if type(child).__name__ == "CTkLabel":
            textos.append(child.cget("text"))
        textos.extend(_labels_texto(child))
    return textos


def test_grid_vazio_sem_maquinas(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    tab = ParqueTab(ctk_root, None, None)

    assert tab.scroll_container.winfo_children() == []


def test_grid_cria_um_cartao_por_maquina(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer 1", tech="FDM", estado="Operacional", manutencao="OK")
    MaquinaService.salvar_maquina(mid="M2", nome="Printer 2", tech="SLA", estado="Operacional", manutencao="OK")

    tab = ParqueTab(ctk_root, None, None)

    assert len(tab.scroll_container.winfo_children()) == 2


def test_cartao_mostra_id_e_nome_da_maquina(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer Um", tech="FDM", estado="Operacional", manutencao="OK")

    tab = ParqueTab(ctk_root, None, None)

    textos = _labels_texto(tab.scroll_container)
    assert "M1" in textos
    assert "Printer Um" in textos


def test_cartao_mostra_modelo_quando_definido(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer Um", tech="FDM", estado="Operacional", manutencao="OK", modelo="Bambu Lab X1C")

    tab = ParqueTab(ctk_root, None, None)

    textos = _labels_texto(tab.scroll_container)
    assert any("Bambu Lab X1C" in t for t in textos)


def test_cartao_sem_modelo_nao_mostra_linha_de_modelo(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer Um", tech="FDM", estado="Operacional", manutencao="OK")

    tab = ParqueTab(ctk_root, None, None)

    textos = _labels_texto(tab.scroll_container)
    assert not any(t.startswith("Modelo:") for t in textos)


def test_cartao_mostra_notas_de_manutencao_quando_nao_ok(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer Um", tech="FDM", estado="Manutenção", manutencao="Trocar bico")

    tab = ParqueTab(ctk_root, None, None)

    textos = _labels_texto(tab.scroll_container)
    assert any("Trocar bico" in t for t in textos)


def test_cartao_mostra_pill_atrasada_quando_ha_tarefa_vencida(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer Um", tech="FDM", estado="Operacional", manutencao="OK", modelo="Bambu Lab X1C")
    ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)
    JSONManager.salvar([{
        "id": 1, "tarefa_id": 1, "maquina_id": "M1",
        "data_realizacao": (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),
        "operador": "tester", "notas": "",
    }], arquivo_manutencoes)

    tab = ParqueTab(ctk_root, None, None)

    textos = _labels_texto(tab.scroll_container)
    assert any("MANUTENÇÃO ATRASADA" in t for t in textos)


def test_cartao_sem_tarefa_vencida_nao_mostra_pill(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer Um", tech="FDM", estado="Operacional", manutencao="OK", modelo="Bambu Lab X1C")

    tab = ParqueTab(ctk_root, None, None)

    textos = _labels_texto(tab.scroll_container)
    assert not any("MANUTENÇÃO ATRASADA" in t for t in textos)


def test_url_imagem_com_esquema_invalido_nao_rebenta(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer Um", tech="FDM", estado="Operacional",
                                   manutencao="OK", url_img="ficheiro/local/sem-http.png")

    tab = ParqueTab(ctk_root, None, None)

    textos = _labels_texto(tab.scroll_container)
    assert any("URL de imagem inválido" in t for t in textos)


def test_atualizar_grid_substitui_cartoes_antigos(arquivo_maquinas, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    MaquinaService.salvar_maquina(mid="M1", nome="Printer Um", tech="FDM", estado="Operacional", manutencao="OK")
    tab = ParqueTab(ctk_root, None, None)
    assert len(tab.scroll_container.winfo_children()) == 1

    MaquinaService.salvar_maquina(mid="M2", nome="Printer Dois", tech="FDM", estado="Operacional", manutencao="OK")
    tab.atualizar_grid_maquinas()

    assert len(tab.scroll_container.winfo_children()) == 2
