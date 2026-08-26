"""
Testes de deteção de não-conformidade recorrente — alerta quando o mesmo
código de erro se repete numa máquina sem que nenhuma ocorrência tenha
tido ação corretiva confirmada (integra diretamente com o loop CAPA).
"""
from datetime import datetime, timedelta

from services.nc_service import NCService


def _seed_nc(caminho_falhas=None, caminho_acoes=None, db_sqlite=None):
    """NCService migrou para SQLite — semeia o catálogo diretamente na BD.
    Mantém a assinatura antiga (argumentos ignorados) para não ter de
    reescrever as ~10 chamadas existentes neste ficheiro."""
    from database.sqlite_manager import SQLiteManager
    with SQLiteManager.conectar() as con:
        con.execute(
            "INSERT OR IGNORE INTO nc_falhas (cod, descricao, tecnologia) VALUES (?, ?, ?)",
            ("COD002", "Falha de adesão", "FDM"),
        )
        con.execute(
            "INSERT OR IGNORE INTO acoes_corretivas (act, acao, tecnologia) VALUES (?, ?, ?)",
            ("ACT001", "Ação de teste", "FDM"),
        )


def _seed_producoes(caminho_db, logs):
    """ProducaoService agora lê de SQLite — insere as produções de teste
    diretamente nas tabelas relevantes (produção + N:N ações aplicadas),
    já que o `caminho_db` recebido não é mais um caminho JSON."""
    from database.sqlite_manager import SQLiteManager
    with SQLiteManager.conectar() as con:
        for log in logs:
            cur = con.execute(
                "INSERT INTO producoes (data_inicio, tecnologia, maquina_nome, nc_codigo) "
                "VALUES (?, 'FDM', ?, ?)",
                (log["data_inicio"], log["maquina"], log.get("nc_codigo") or None),
            )
            pid = cur.lastrowid
            for act_cod in log.get("acoes_aplicadas", []):
                con.execute(
                    "INSERT OR IGNORE INTO producao_acoes_aplicadas (producao_id, act) VALUES (?, ?)",
                    (pid, act_cod),
                )


def _log(id_, dias_atras, maquina="Bambu Lab X1C #1", nc="COD002", acoes=None):
    data = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y-%m-%d %H:%M:%S")
    return {"id": id_, "maquina": maquina, "data_inicio": data,
            "nc_codigo": nc, "acoes_aplicadas": acoes or []}


def test_detecta_recorrencia_sem_correcao(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes, arquivo_producoes)
    _seed_producoes(arquivo_producoes, [
        _log(1, dias_atras=1), _log(2, dias_atras=3), _log(3, dias_atras=5),
    ])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {"COD002": 3}


def test_ignora_ocorrencia_fora_da_janela(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes, arquivo_producoes)
    _seed_producoes(arquivo_producoes, [
        _log(1, dias_atras=1), _log(2, dias_atras=20),  # a segunda está fora dos 7 dias
    ])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {}, dias=7)
    # Só 1 ocorrência dentro da janela — abaixo do mínimo de 2, não alerta
    assert resultado == {}


def test_ignora_ocorrencias_de_outra_maquina(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes, arquivo_producoes)
    _seed_producoes(arquivo_producoes, [
        _log(1, dias_atras=1, maquina="Bambu Lab X1C #1"),
        _log(2, dias_atras=2, maquina="Bambu Lab X1C #2"),
    ])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {}  # só 1 ocorrência na máquina consultada — abaixo do mínimo


def test_nao_alerta_se_capa_ja_fechado(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes, arquivo_producoes)
    _seed_producoes(arquivo_producoes, [
        _log(1, dias_atras=1, acoes=["ACT001"]),  # esta já foi corrigida
        _log(2, dias_atras=3), _log(3, dias_atras=5),
    ])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {}, "Não deve alertar quando pelo menos uma ocorrência já foi corrigida"


def test_nao_alerta_com_ocorrencia_unica(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes, arquivo_producoes)
    _seed_producoes(arquivo_producoes, [_log(1, dias_atras=1)])
    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {}


def test_respeita_minimo_customizado(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes, arquivo_producoes)
    _seed_producoes(arquivo_producoes, [_log(1, dias_atras=1), _log(2, dias_atras=2)])
    assert NCService.detectar_recorrencia("Bambu Lab X1C #1", {}, minimo=2) == {"COD002": 2}
    assert NCService.detectar_recorrencia("Bambu Lab X1C #1", {}, minimo=3) == {}


def test_nome_maquina_vazio_devolve_vazio(arquivos_nc, arquivo_producoes):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes, arquivo_producoes)
    _seed_producoes(arquivo_producoes, [_log(1, dias_atras=1)])
    assert NCService.detectar_recorrencia("", {}) == {}
    assert NCService.detectar_recorrencia(None, {}) == {}


def test_resolve_id_maquina_legacy_via_lookup():
    """Produções legacy só com id_maquina (sem nome resolvido) já não podem
    existir na BD SQLite em si — a FK obriga a máquina a estar resolvida
    antes de gravar (é isso que o script de migração garante à entrada).
    O que continua válido, e é isto que se testa aqui, é a função pura
    normalizar_maquina() resolver corretamente um dict construído à mão
    (ex: vindo de uma fonte externa) que só tenha id_maquina."""
    from services.producao_service import ProducaoService
    producao_legacy = {"id_maquina": "X1-1"}  # sem "maquina" preenchido
    id_para_nome = {"X1-1": "Bambu Lab X1C #1"}
    assert ProducaoService.normalizar_maquina(producao_legacy, id_para_nome) == "Bambu Lab X1C #1"


def test_deteccao_recorrencia_usa_maquina_ja_resolvida_pela_fk(arquivos_nc, arquivo_producoes):
    """Cenário real na nova arquitetura: a produção é gravada com
    maquina_nome já resolvido (como o script de migração ou criar_producao
    já garantem) — a deteção de recorrência funciona normalmente sobre
    dados que vieram da BD, sem precisar de nenhuma resolução em runtime."""
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc(caminho_falhas, caminho_acoes, arquivo_producoes)

    _seed_producoes(arquivo_producoes, [
        {"id": 1, "maquina": "Bambu Lab X1C #1",
         "data_inicio": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
         "nc_codigo": "COD002", "acoes_aplicadas": []},
        {"id": 2, "maquina": "Bambu Lab X1C #1",
         "data_inicio": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
         "nc_codigo": "COD002", "acoes_aplicadas": []},
    ])

    resultado = NCService.detectar_recorrencia("Bambu Lab X1C #1", {})
    assert resultado == {"COD002": 2}


def test_formatar_alerta_recorrencia_lista_vazia():
    assert NCService.formatar_alerta_recorrencia({}) == ""


def test_formatar_alerta_recorrencia_ordena_por_contagem(arquivos_nc):
    from database.sqlite_manager import SQLiteManager
    with SQLiteManager.conectar() as con:
        con.execute("INSERT OR IGNORE INTO nc_falhas (cod, descricao, tecnologia) "
                    "VALUES ('COD001', 'Obstrução', 'FDM')")
        con.execute("INSERT OR IGNORE INTO nc_falhas (cod, descricao, tecnologia) "
                    "VALUES ('COD002', 'Adesão', 'FDM')")

    msg = NCService.formatar_alerta_recorrencia({"COD001": 2, "COD002": 5})
    linhas = msg.split("\n")
    assert linhas[0].startswith("COD002"), "O código com mais ocorrências deve vir primeiro"
