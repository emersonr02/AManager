import pytest
from datetime import datetime, timedelta

from database.json_manager import JSONManager
from services.maquina_service import MaquinaService
from services.manutencao_service import ManutencaoService
from gui.manutencao_tab import ManutencaoTab


@pytest.fixture
def avisos(monkeypatch):
    chamadas = {"warning": [], "error": [], "info": []}
    monkeypatch.setattr("gui.manutencao_tab.messagebox.showwarning", lambda t, m: chamadas["warning"].append(m))
    monkeypatch.setattr("gui.manutencao_tab.messagebox.showerror", lambda t, m: chamadas["error"].append(m))
    monkeypatch.setattr("gui.manutencao_tab.messagebox.showinfo", lambda t, m: chamadas["info"].append(m))
    return chamadas


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _criar_maquina(mid="M1", nome="Printer 1", modelo="Bambu Lab X1C"):
    MaquinaService.salvar_maquina(mid=mid, nome=nome, tech="FDM", estado="Operacional", manutencao="OK", modelo=modelo)


def _linhas(tree):
    return [tree.item(i)["values"] for i in tree.get_children()]


# ---------- Agenda ----------

def test_agenda_vazia_sem_maquinas_ou_tarefas(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    tab = ManutencaoTab(ctk_root, None, None)

    assert _linhas(tab.tree_agenda) == []


def test_agenda_lista_tarefa_atrasada(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    _criar_maquina()
    tarefa = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)
    JSONManager.salvar([{
        "id": 1, "tarefa_id": tarefa["id"], "maquina_id": "M1",
        "data_realizacao": _fmt(datetime.now() - timedelta(days=20)), "operador": "a", "notas": "",
    }], arquivo_manutencoes)

    tab = ManutencaoTab(ctk_root, None, None)

    linhas = _linhas(tab.tree_agenda)
    assert len(linhas) == 1
    assert linhas[0][0] == "Printer 1"
    assert linhas[0][5] == "Atrasada"


def test_marcar_concluida_regista_historico_e_atualiza_agenda(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root, avisos):
    _criar_maquina()
    tarefa = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)
    JSONManager.salvar([{
        "id": 1, "tarefa_id": tarefa["id"], "maquina_id": "M1",
        "data_realizacao": _fmt(datetime.now() - timedelta(days=20)), "operador": "a", "notas": "",
    }], arquivo_manutencoes)
    tab = ManutencaoTab(ctk_root, None, None)
    tab.tree_agenda.selection_set(tab.tree_agenda.get_children()[0])

    tab.marcar_concluida()

    assert len(ManutencaoService.obter_historico()) == 2  # o antigo + o novo registo
    assert avisos["info"]
    linhas = _linhas(tab.tree_agenda)
    assert linhas[0][5] == "OK"  # acabada de concluir, já não está atrasada


def test_marcar_concluida_sem_selecao_nao_rebenta(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root, avisos):
    tab = ManutencaoTab(ctk_root, None, None)

    tab.marcar_concluida()

    assert ManutencaoService.obter_historico() == []


# ---------- Tarefas Periódicas ----------

def test_lista_tarefas_inclui_ativas_e_inativas(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    _criar_maquina()
    ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Ativa", frequencia_dias=10)
    inativa = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Inativa", frequencia_dias=10)
    ManutencaoService.definir_ativa(inativa["id"], False)

    tab = ManutencaoTab(ctk_root, None, None)

    linhas = _linhas(tab.tree_tarefas)
    assert len(linhas) == 2


def test_adicionar_tarefa_sem_modelo_disponivel_bloqueia(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root, avisos):
    tab = ManutencaoTab(ctk_root, None, None)
    tab.ent_tarefa_nome.insert(0, "Limpeza")
    tab.ent_tarefa_freq_dias.insert(0, "30")

    tab.adicionar_tarefa()

    assert avisos["warning"]
    assert ManutencaoService.obter_tarefas() == []


def test_adicionar_tarefa_sem_frequencia_mostra_erro_do_service(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root, avisos):
    _criar_maquina()
    tab = ManutencaoTab(ctk_root, None, None)
    tab.cmb_tarefa_modelo.set("Bambu Lab X1C")
    tab.ent_tarefa_nome.insert(0, "Limpeza")
    # nem dias nem horas preenchidos

    tab.adicionar_tarefa()

    assert avisos["error"]
    assert ManutencaoService.obter_tarefas() == []


def test_adicionar_tarefa_com_frequencia_invalida_bloqueia(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root, avisos):
    _criar_maquina()
    tab = ManutencaoTab(ctk_root, None, None)
    tab.cmb_tarefa_modelo.set("Bambu Lab X1C")
    tab.ent_tarefa_nome.insert(0, "Limpeza")
    tab.ent_tarefa_freq_dias.insert(0, "abc")

    tab.adicionar_tarefa()

    assert avisos["warning"]
    assert ManutencaoService.obter_tarefas() == []


def test_adicionar_tarefa_valida_persiste_e_limpa_formulario(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root, avisos):
    _criar_maquina()
    tab = ManutencaoTab(ctk_root, None, None)
    tab.cmb_tarefa_modelo.set("Bambu Lab X1C")
    tab.ent_tarefa_nome.insert(0, "Limpeza")
    tab.ent_tarefa_freq_dias.insert(0, "30")
    tab.ent_tarefa_freq_horas.insert(0, "200")

    tab.adicionar_tarefa()

    tarefas = ManutencaoService.obter_tarefas()
    assert len(tarefas) == 1
    assert tarefas[0]["frequencia_dias"] == 30
    assert tarefas[0]["frequencia_horas"] == 200.0
    assert tab.ent_tarefa_nome.get() == ""


def test_toggle_ativa_tarefa_desativa_e_reativa(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    _criar_maquina()
    ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)
    tab = ManutencaoTab(ctk_root, None, None)
    tab.tree_tarefas.selection_set(tab.tree_tarefas.get_children()[0])

    tab.toggle_ativa_tarefa()
    assert ManutencaoService.obter_tarefas() == []

    tab.tree_tarefas.selection_set(tab.tree_tarefas.get_children()[0])
    tab.toggle_ativa_tarefa()
    assert len(ManutencaoService.obter_tarefas()) == 1


def _encontrar_widgets(container, classe):
    encontrados = []
    for child in container.winfo_children():
        if type(child).__name__ == classe:
            encontrados.append(child)
        encontrados.extend(_encontrar_widgets(child, classe))
    return encontrados


def test_editar_tarefa_guarda_alteracoes(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root, avisos):
    _criar_maquina()
    ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Nome Antigo", frequencia_dias=10)
    tab = ManutencaoTab(ctk_root, None, None)
    tab.tree_tarefas.selection_set(tab.tree_tarefas.get_children()[0])

    tab.editar_tarefa_selecionada()
    top = ctk_root.winfo_toplevel().winfo_children()[-1]
    entradas = _encontrar_widgets(top, "CTkEntry")
    botao = _encontrar_widgets(top, "CTkButton")[0]
    ent_nome = entradas[0]

    ent_nome.delete(0, "end")
    ent_nome.insert(0, "Nome Novo")
    botao.cget("command")()

    assert ManutencaoService.obter_tarefas()[0]["nome"] == "Nome Novo"
    assert top.winfo_exists() == 0


# ---------- Histórico ----------

def test_historico_mostra_nomes_resolvidos(arquivo_maquinas, arquivo_producoes, arquivo_manutencoes, arquivo_tarefas_manutencao, ctk_root):
    _criar_maquina()
    tarefa = ManutencaoService.criar_tarefa(modelo="Bambu Lab X1C", nome="Limpeza", frequencia_dias=10)
    ManutencaoService.registar_conclusao(tarefa["id"], "M1", operador="jsilva", notas="Tudo ok")

    tab = ManutencaoTab(ctk_root, None, None)

    linhas = _linhas(tab.tree_historico)
    assert len(linhas) == 1
    assert linhas[0][0] == "Printer 1"
    assert linhas[0][1] == "Limpeza"
    assert linhas[0][3] == "jsilva"
    assert linhas[0][4] == "Tudo ok"
