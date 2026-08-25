"""
Testes de deteção de não-conformidade recorrente — alerta quando o mesmo
código de erro se repete numa máquina sem que nenhuma ocorrência tenha
tido ação corretiva confirmada (integra diretamente com o loop CAPA).
"""
from datetime import datetime, timedelta

from services.nc_service import NCService


def _seed_nc(caminho_falhas, caminho_acoes):
    from database.json_manager import JSONManager
    JSONManager.salvar([
        {"cod": "COD002", "descricao": "Falha de adesão", "tecnologia": "FDM"},
    ], caminho_falhas)
    JSONManager.salvar([], caminho_acoes)


def _seed_producoes(caminho_logs, logs):
    from database.json_manager import JSONManager
    JSONManager.salvar(logs, caminho_logs)


def _log(id_, dias_atras, maquina="Bambu Lab X1C #1", nc="COD002", acoes=None):
    data = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y-%m-%d %H:%M:%S")
    return {"id": id_, "maquina": maquina, "data_inicio": data,
            "nc_codigo": nc, "acoes_aplicadas": acoes or []}


def test_detecta_recorrencia_sem_correcao(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes)
    _seed_producoes(arquivo_producoes, [
        _log(1, dias_atras=1), _log(2, dias_atras=3), _log(3, dias_atras=5),
    ])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {"COD002": 3}


def test_ignora_ocorrencia_fora_da_janela(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes)
    _seed_producoes(arquivo_producoes, [
        _log(1, dias_atras=1), _log(2, dias_atras=20),  # a segunda está fora dos 7 dias
    ])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {}, dias=7)
    # Só 1 ocorrência dentro da janela — abaixo do mínimo de 2, não alerta
    assert resultado == {}


def test_ignora_ocorrencias_de_outra_maquina(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes)
    _seed_producoes(arquivo_producoes, [
        _log(1, dias_atras=1, maquina="Bambu Lab X1C #1"),
        _log(2, dias_atras=2, maquina="Bambu Lab X1C #2"),
    ])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {}  # só 1 ocorrência na máquina consultada — abaixo do mínimo


def test_nao_alerta_se_capa_ja_fechado(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes)
    _seed_producoes(arquivo_producoes, [
        _log(1, dias_atras=1, acoes=["ACT001"]),  # esta já foi corrigida
        _log(2, dias_atras=3), _log(3, dias_atras=5),
    ])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {}, "Não deve alertar quando pelo menos uma ocorrência já foi corrigida"


def test_nao_alerta_com_ocorrencia_unica(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes)
    _seed_producoes(arquivo_producoes, [_log(1, dias_atras=1)])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {}


def test_respeita_minimo_customizado(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes)
    _seed_producoes(arquivo_producoes, [_log(1, dias_atras=1), _log(2, dias_atras=2)])
    assert NCService.detectar_recorrencia("Bambu Lab X1C #1", {}, minimo=2) == {"COD002": 2}
    assert NCService.detectar_recorrencia("Bambu Lab X1C #1", {}, minimo=3) == {}


def test_nome_maquina_vazio_devolve_vazio(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes)
    _seed_producoes(arquivo_producoes, [_log(1, dias_atras=1)])
    assert NCService.detectar_recorrencia("", {}) == {}
    assert NCService.detectar_recorrencia(None, {}) == {}


def test_resolve_id_maquina_legacy_via_lookup(arquivos_nc, arquivo_producoes):
    """Produções legacy guardam id_maquina em vez de maquina — a deteção
    deve resolver o nome via o lookup do parque de máquinas."""
    from database.json_manager import JSONManager
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes)

    logs_legacy = [
        {"id": 1, "id_maquina": "X1-1",
         "data_inicio": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
         "nc_codigo": "COD002", "acoes_aplicadas": []},
        {"id": 2, "id_maquina": "X1-1",
         "data_inicio": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
         "nc_codigo": "COD002", "acoes_aplicadas": []},
    ]
    JSONManager.salvar(logs_legacy, arquivo_producoes)

    id_para_nome = {"X1-1": "Bambu Lab X1C #1"}
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", id_para_nome)
    assert resultado == {"COD002": 2}


def test_formatar_alerta_recorrencia_lista_vazia():
    assert NCService.formatar_alerta_recorrencia({}) == ""


def test_formatar_alerta_recorrencia_ordena_por_contagem(arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    from database.json_manager import JSONManager
    JSONManager.salvar([
        {"cod": "COD001", "descricao": "Obstrução", "tecnologia": "FDM"},
        {"cod": "COD002", "descricao": "Adesão", "tecnologia": "FDM"},
    ], caminho_falhas)
    JSONManager.salvar([], caminho_acoes)

    msg = NCService.formatar_alerta_recorrencia({"COD001": 2, "COD002": 5})
    linhas = msg.split("\n")
    assert linhas[0].startswith("COD002"), "O código com mais ocorrências deve vir primeiro"
