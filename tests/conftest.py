import hashlib
import os

import pytest

from database import json_manager
from services import pedido_service, maquina_service, nc_service, projeto_service, material_service, producao_service, manutencao_service

# customtkinter tenta pintar a titlebar nativa a cada CTk/CTkToplevel criado no
# Windows, através de ctypes + DWM (withdraw -> update -> GetParent -> DwmSetWindowAttribute).
# Criar/destruir muitas janelas rapidamente (como faz a suite de testes) expõe uma
# condição de corrida nessa chamada que já se traduziu num "Windows fatal exception:
# access violation" a abrir o segundo CTkToplevel de um teste. A própria biblioteca
# expõe esta flag para desligar esse hack cosmético — sem efeito nos testes, que
# nunca mostram a janela (withdraw()) e portanto nunca veem a cor da titlebar.
import customtkinter as ctk
ctk.CTk._deactivate_windows_window_header_manipulation = True
ctk.CTkToplevel._deactivate_windows_window_header_manipulation = True


def _hash_pasta_dados():
    """Soma de verificação de todos os ficheiros em data/ — usada para garantir que
    nenhum teste (por falta de isolamento/monkeypatch) escreveu em dados reais."""
    from config.paths import DATA_DIR

    resumo = {}
    if not os.path.isdir(DATA_DIR):
        return resumo
    for nome in sorted(os.listdir(DATA_DIR)):
        caminho = os.path.join(DATA_DIR, nome)
        if os.path.isfile(caminho):
            with open(caminho, "rb") as f:
                resumo[nome] = hashlib.sha256(f.read()).hexdigest()
    return resumo


@pytest.fixture(scope="session", autouse=True)
def _protecao_dados_reais():
    """Tripwire de sessão: falha alto e a apontar o(s) ficheiro(s) exato(s) se algum
    teste escrever em data/*.json reais (em vez de usar os ficheiros isolados em
    tmp_path). Ver memória 'git_history_purge' — já houve um incidente de dados
    de cliente CEiiA a vazar para o histórico do git; nenhum teste deve arriscar
    voltar a tocar nesses ficheiros."""
    antes = _hash_pasta_dados()
    yield
    depois = _hash_pasta_dados()
    if antes != depois:
        alterados = [k for k in (set(antes) | set(depois)) if antes.get(k) != depois.get(k)]
        raise AssertionError(
            "Um ou mais testes escreveram em data/*.json REAIS (não isolados): "
            f"{sorted(alterados)}. Falta aplicar gui_arquivos/arquivo_* nesse teste."
        )


@pytest.fixture(scope="session")
def app_sessao(tmp_path_factory):
    """Uma única instância de AppIndustrialI3D (logo, um único interpretador Tcl/Tk)
    para toda a sessão de testes.

    Criar e destruir janelas Tk repetidamente no mesmo processo é instável neste
    Windows: o segundo `Tk()` do processo falha de forma intermitente com
    "couldn't read file .../auto.tcl" mesmo que o primeiro já tenha sido destruído
    — não é uma questão de esperar mais, é o processo já não conseguir abrir um
    segundo interpretador Tcl de forma fiável. A solução é nunca ter mais do que
    um `Tk()` vivo no processo: construímos a app real uma única vez (com ficheiros
    de dados isolados, só para a construção não tocar em data/*.json a sério) e
    todos os testes de UI penduram os seus widgets de teste nela.
    """
    import pytest as _pytest
    from gui.app import AppIndustrialI3D

    mp = _pytest.MonkeyPatch()
    _aplicar_patches_gui(mp, tmp_path_factory.mktemp("gui_dados_sessao"))

    app = AppIndustrialI3D()
    app.withdraw()
    yield app
    app.destroy()
    mp.undo()


@pytest.fixture
def ctk_root(app_sessao):
    """Frame descartável, filho da app partilhada da sessão, para servir de
    parent_frame a componentes de UI em testes. Destruído no fim de cada teste."""
    import customtkinter as ctk
    frame = ctk.CTkFrame(app_sessao)
    yield frame
    frame.destroy()


@pytest.fixture
def arquivo_pedidos(tmp_path, monkeypatch):
    caminho = tmp_path / "pedidos.json"
    monkeypatch.setattr(pedido_service, "ARQUIVO_PEDIDOS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_projetos(tmp_path, monkeypatch):
    caminho = tmp_path / "projetos.json"
    monkeypatch.setattr(projeto_service, "ARQUIVO_PROJETOS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_materiais(tmp_path, monkeypatch):
    caminho = tmp_path / "materiais.json"
    monkeypatch.setattr(material_service, "ARQUIVO_MATERIAIS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_producoes(tmp_path, monkeypatch):
    caminho = tmp_path / "producao_i3D.json"
    monkeypatch.setattr(producao_service, "ARQUIVO_LOGS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_maquinas(tmp_path, monkeypatch):
    caminho = tmp_path / "parque_maquinas.json"
    monkeypatch.setattr(maquina_service, "ARQUIVO_MAQUINAS", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_manutencoes(tmp_path, monkeypatch):
    caminho = tmp_path / "manutencoes.json"
    monkeypatch.setattr(manutencao_service, "ARQUIVO_MANUTENCOES", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivo_tarefas_manutencao(tmp_path, monkeypatch):
    caminho = tmp_path / "tarefas_manutencao.json"
    monkeypatch.setattr(manutencao_service, "ARQUIVO_TAREFAS_MANUTENCAO", str(caminho))
    return str(caminho)


@pytest.fixture
def arquivos_nc(tmp_path, monkeypatch):
    falhas = tmp_path / "nc_falhas.json"
    acoes = tmp_path / "acoes_corretivas.json"
    monkeypatch.setattr(nc_service, "ARQUIVO_NC_FALHAS", str(falhas))
    monkeypatch.setattr(nc_service, "ARQUIVO_ACOES", str(acoes))
    return str(falhas), str(acoes)


@pytest.fixture
def json_file(tmp_path):
    return str(tmp_path / "dados.json")


def _aplicar_patches_gui(mp, base_dir):
    """Redireciona os ficheiros de dados usados diretamente pelos módulos de gui/
    (que importam as constantes por nome, não pelo módulo config.paths)."""
    from gui import pedidos_tab, historico_tab, producao_tab
    from gui.dialogs import novo_pedido, editar_pedido, fechar_ordem

    caminhos = {
        "pedidos": base_dir / "pedidos.json",
        "producoes": base_dir / "producao_i3D.json",
        "maquinas": base_dir / "parque_maquinas.json",
        "manutencoes": base_dir / "manutencoes.json",
        "tarefas_manutencao": base_dir / "tarefas_manutencao.json",
    }

    mp.setattr(pedido_service, "ARQUIVO_PEDIDOS", str(caminhos["pedidos"]))
    for modulo in (pedidos_tab, historico_tab, novo_pedido, editar_pedido, fechar_ordem):
        mp.setattr(modulo, "ARQUIVO_PEDIDOS", str(caminhos["pedidos"]))

    mp.setattr(producao_service, "ARQUIVO_LOGS", str(caminhos["producoes"]))
    mp.setattr(producao_tab, "ARQUIVO_LOGS", str(caminhos["producoes"]))

    mp.setattr(maquina_service, "ARQUIVO_MAQUINAS", str(caminhos["maquinas"]))
    mp.setattr(producao_tab, "ARQUIVO_MAQUINAS", str(caminhos["maquinas"]))

    # manutencao_tab.py só fala com ManutencaoService (nunca importa estas constantes
    # por nome), por isso basta patchar o service — nenhum módulo de gui/ a mais aqui.
    mp.setattr(manutencao_service, "ARQUIVO_MANUTENCOES", str(caminhos["manutencoes"]))
    mp.setattr(manutencao_service, "ARQUIVO_TAREFAS_MANUTENCAO", str(caminhos["tarefas_manutencao"]))

    return {k: str(v) for k, v in caminhos.items()}


@pytest.fixture
def gui_arquivos(tmp_path, monkeypatch):
    return _aplicar_patches_gui(monkeypatch, tmp_path)
