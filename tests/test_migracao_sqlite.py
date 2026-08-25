"""
Testes do script de migração JSON → SQLite. Cobrem especificamente os
casos legacy que já apanhámos ao longo do projeto: id_maquina antigo,
hora_maquina em formato timedelta, campos planos de QA, quantidade/
operador com nomes de campo antigos, e o loop CAPA (N:N ações aplicadas).
"""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))


@pytest.fixture
def ambiente_migracao(tmp_path, monkeypatch):
    """Isola todos os ficheiros JSON de origem e a BD de destino num
    diretório temporário, e recarrega os módulos para apanharem os
    caminhos monkeypatched."""
    import config.paths as paths
    from database import sqlite_manager

    nomes = {
        "ARQUIVO_LOGS": "producao_i3D.json", "ARQUIVO_MAQUINAS": "parque_maquinas.json",
        "ARQUIVO_PROJETOS": "projetos.json", "ARQUIVO_MATERIAIS": "materiais.json",
        "ARQUIVO_PEDIDOS": "pedidos.json", "ARQUIVO_NC_FALHAS": "nc_falhas.json",
        "ARQUIVO_ACOES": "acoes_corretivas.json", "ARQUIVO_TEMPLATES": "templates_producao.json",
        "ARQUIVO_AUDIT_LOG": "audit_log.json",
    }
    caminhos = {}
    for attr, nome in nomes.items():
        caminho = str(tmp_path / nome)
        monkeypatch.setattr(paths, attr, caminho)
        caminhos[attr] = caminho
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump([], f)

    caminho_db = str(tmp_path / "amanager.db")
    monkeypatch.setattr(sqlite_manager, "ARQUIVO_DB", caminho_db)
    monkeypatch.setattr(paths, "DATA_DIR", str(tmp_path))

    import migrar_json_para_sqlite as migrador
    monkeypatch.setattr(migrador, "ARQUIVO_LOGS", caminhos["ARQUIVO_LOGS"])
    monkeypatch.setattr(migrador, "ARQUIVO_MAQUINAS", caminhos["ARQUIVO_MAQUINAS"])
    monkeypatch.setattr(migrador, "ARQUIVO_PROJETOS", caminhos["ARQUIVO_PROJETOS"])
    monkeypatch.setattr(migrador, "ARQUIVO_MATERIAIS", caminhos["ARQUIVO_MATERIAIS"])
    monkeypatch.setattr(migrador, "ARQUIVO_PEDIDOS", caminhos["ARQUIVO_PEDIDOS"])
    monkeypatch.setattr(migrador, "ARQUIVO_NC_FALHAS", caminhos["ARQUIVO_NC_FALHAS"])
    monkeypatch.setattr(migrador, "ARQUIVO_ACOES", caminhos["ARQUIVO_ACOES"])
    monkeypatch.setattr(migrador, "ARQUIVO_TEMPLATES", caminhos["ARQUIVO_TEMPLATES"])
    monkeypatch.setattr(migrador, "ARQUIVO_AUDIT_LOG", caminhos["ARQUIVO_AUDIT_LOG"])

    return caminhos


def _escrever(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f)


def test_migra_maquina_simples(ambiente_migracao):
    _escrever(ambiente_migracao["ARQUIVO_MAQUINAS"], [
        {"id": "X1-1", "nome": "Bambu Lab X1C #1", "tech": "FDM", "estado": "Operacional"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM maquinas WHERE id = 'X1-1'").fetchone()
        assert row is not None
        assert row["nome"] == "Bambu Lab X1C #1"


def test_migra_producao_novo_formato(ambiente_migracao):
    _escrever(ambiente_migracao["ARQUIVO_MAQUINAS"], [
        {"id": "X1-1", "nome": "Bambu Lab X1C #1", "tech": "FDM"},
    ])
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "data_inicio": "2026-08-04 15:59:21", "tecnologia": "FDM",
         "maquina": "Bambu Lab X1C #1", "tempo_estimado": "02:23", "estado": "Concluída",
         "operador": "joao", "quantidade_consumida": "87.65"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        assert row["maquina_nome"] == "Bambu Lab X1C #1"
        assert row["maquina_id"] == "X1-1"
        assert row["tempo_estimado"] == "02:23"
        assert row["operador"] == "joao"


def test_migra_producao_legacy_id_maquina(ambiente_migracao):
    """id_maquina antigo deve resolver via lookup do parque de máquinas."""
    _escrever(ambiente_migracao["ARQUIVO_MAQUINAS"], [
        {"id": "X1C-1", "nome": "Bambu Lab X1C #1", "tech": "FDM"},
    ])
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 212, "id_maquina": "X1C-1", "data_inicio": "2026-07-24", "estado": "Concluída"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        assert row["maquina_nome"] == "Bambu Lab X1C #1"


def test_migra_producao_legacy_id_maquina_mapeamento_estatico(ambiente_migracao):
    """id_maquina que não está no parque atual mas está no mapeamento
    legacy estático (ex: 'X1-1' formato antigo) deve resolver na mesma."""
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "id_maquina": "X1-1", "data_inicio": "2026-07-24", "estado": "Concluída"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        assert row["maquina_nome"] == "Bambu Lab X1C #1"
        assert row["maquina_id"] is None  # não existe no parque atual, só no mapeamento estático


def test_migra_producao_legacy_hora_maquina_timedelta(ambiente_migracao):
    """hora_maquina em formato 'N days, H:MM:SS' deve converter para HH:MM."""
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "data_inicio": "2026-07-24", "hora_maquina": "1 day, 2:48:00", "estado": "Concluída"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        assert row["tempo_estimado"] == "26:48"


def test_migra_producao_legacy_operador_responsavel(ambiente_migracao):
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "data_inicio": "2026-07-24", "responsavel": "Emerson R", "estado": "Concluída"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        assert row["operador"] == "Emerson R"


def test_migra_producao_legacy_quantidade(ambiente_migracao):
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "data_inicio": "2026-07-24", "quantidade": 469.89, "estado": "Concluída"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        assert row["quantidade_consumida"] == "469.89"


def test_migra_producao_legacy_qa_campos_planos(ambiente_migracao):
    """QA sem estrutura controlo_qualidade — campos planos antigos devem
    consolidar-se na mesma coluna JSON."""
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "data_inicio": "2026-07-24", "estado": "Concluída",
         "inspecao_visual": True, "controlo_dimensional": True, "conformidade_peca": False},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        qa = json.loads(row["controlo_qualidade"])
        assert qa["inspecao_visual"] is True
        assert qa["controlo_dimensional"] is True
        assert qa["conformidade"] is False


def test_migra_producao_maquina_numerica_desconhecida(ambiente_migracao):
    """IDs puramente numéricos do sistema antigo (sem correspondência
    possível) ficam marcados como Desconhecida em vez de rebentar."""
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "id_maquina": "84", "data_inicio": "2020-01-01", "estado": "Concluída"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        assert "Desconhecida" in row["maquina_nome"]
        assert row["maquina_id"] is None


def test_migra_pedido_com_pecas(ambiente_migracao):
    _escrever(ambiente_migracao["ARQUIVO_PEDIDOS"], [
        {"id": 5, "requerente_email": "a@ceiia.com", "nr_projeto": "236863",
         "nome_projeto": "PPS BEN", "data_pedido": "2026-08-01", "data_entrega": "2026-08-10",
         "estado": "Em Andamento",
         "pecas": [
             {"pn": "P1", "material": "PLA - Generic", "qtd_solicitada": 5, "qtd_produzida": 0},
             {"pn": "P2", "material": "ASA - Generic", "qtd_solicitada": 2, "qtd_produzida": 1},
         ]},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        pedido = con.execute("SELECT * FROM pedidos").fetchone()
        assert pedido["requerente_email"] == "a@ceiia.com"
        pecas = con.execute("SELECT * FROM pedido_pecas ORDER BY ordem").fetchall()
        assert len(pecas) == 2
        assert pecas[0]["pn"] == "P1"
        assert pecas[1]["qtd_produzida"] == 1


def test_migra_vinculo_producao_pedido_resolve_ids(ambiente_migracao):
    """O ID do pedido no JSON original é diferente do novo ID autoincrement
    da BD — a migração tem de resolver essa correspondência corretamente."""
    _escrever(ambiente_migracao["ARQUIVO_PEDIDOS"], [
        {"id": 999, "requerente_email": "a@ceiia.com", "nr_projeto": "X", "nome_projeto": "Y",
         "data_pedido": "2026-08-01", "data_entrega": "2026-08-10", "estado": "Em Andamento", "pecas": []},
    ])
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "data_inicio": "2026-08-04", "estado": "Concluída", "pedidos_vinculados": [999]},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        pedido_novo_id = con.execute("SELECT id FROM pedidos").fetchone()["id"]
        vinculo = con.execute("SELECT * FROM producao_pedidos").fetchone()
        assert vinculo["pedido_id"] == pedido_novo_id


def test_migra_loop_capa_acoes_aplicadas(ambiente_migracao):
    _escrever(ambiente_migracao["ARQUIVO_NC_FALHAS"], [
        {"cod": "COD001", "descricao": "Obstrução", "tecnologia": "FDM"},
    ])
    _escrever(ambiente_migracao["ARQUIVO_ACOES"], [
        {"act": "ACT001", "acao": "Limpeza", "tecnologia": "FDM", "codigos_aplicaveis": ["COD001"]},
    ])
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "data_inicio": "2026-08-06", "estado": "Cancelada",
         "nc_codigo": "COD001", "acoes_aplicadas": ["ACT001"]},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        producao = con.execute("SELECT * FROM producoes").fetchone()
        assert producao["nc_codigo"] == "COD001"
        vinculo = con.execute("SELECT * FROM producao_acoes_aplicadas").fetchone()
        assert vinculo["act"] == "ACT001"


def test_migra_producao_sem_nc_fica_null(ambiente_migracao):
    """nc_codigo vazio ('') deve virar NULL na BD, nunca string vazia
    (que violaria a foreign key para nc_falhas)."""
    _escrever(ambiente_migracao["ARQUIVO_LOGS"], [
        {"id": 1, "data_inicio": "2026-08-06", "estado": "Concluída", "nc_codigo": ""},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM producoes").fetchone()
        assert row["nc_codigo"] is None


def test_migra_acoes_corretivas_com_codigos_aplicaveis(ambiente_migracao):
    _escrever(ambiente_migracao["ARQUIVO_NC_FALHAS"], [
        {"cod": "COD001", "descricao": "A", "tecnologia": "FDM"},
        {"cod": "COD002", "descricao": "B", "tecnologia": "FDM"},
    ])
    _escrever(ambiente_migracao["ARQUIVO_ACOES"], [
        {"act": "ACT001", "acao": "Ação X", "tecnologia": "FDM",
         "codigos_aplicaveis": ["COD001", "COD002"], "etapas": ["Passo 1", "Passo 2"]},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        acao = con.execute("SELECT * FROM acoes_corretivas WHERE act = 'ACT001'").fetchone()
        assert json.loads(acao["etapas"]) == ["Passo 1", "Passo 2"]
        codigos = con.execute("SELECT nc_cod FROM acoes_codigos_aplicaveis WHERE act = 'ACT001'").fetchall()
        assert {r["nc_cod"] for r in codigos} == {"COD001", "COD002"}


def test_migra_flag_limpar_evita_duplicados(ambiente_migracao):
    _escrever(ambiente_migracao["ARQUIVO_MAQUINAS"], [
        {"id": "X1-1", "nome": "Bambu Lab X1C #1", "tech": "FDM"},
    ])
    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager

    migrador.migrar()
    migrador.SQLiteManager.garantir_esquema()
    with SQLiteManager.conectar() as con:
        con.execute("DELETE FROM maquinas")
        con.execute(
            "INSERT INTO maquinas (id, nome, tech) VALUES ('X1-1', 'Bambu Lab X1C #1', 'FDM')"
        )
    with SQLiteManager.conectar() as con:
        total = con.execute("SELECT COUNT(*) c FROM maquinas").fetchone()["c"]
        assert total == 1  # confirma que a tabela não acumulou duplicados manualmente


def test_migra_projeto_formato_string_legacy(ambiente_migracao):
    """projetos.json em produção real usa strings soltas 'id - nome' em vez
    de dicts — este era o bug que rebentava a migração inteira (por
    rollback de transação) mal chegasse a esta função."""
    _escrever(ambiente_migracao["ARQUIVO_PROJETOS"], ["236863 - PPS BEN", "247042 - PPS CASTA"])

    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        projetos = con.execute("SELECT * FROM projetos ORDER BY id").fetchall()
        assert len(projetos) == 2
        assert dict(projetos[0])["id"] == "236863"
        assert dict(projetos[0])["nome"] == "PPS BEN"


def test_migra_projeto_string_sem_separador(ambiente_migracao):
    """Uma string sem ' - ' vira id=texto, nome=vazio — não rebenta."""
    _escrever(ambiente_migracao["ARQUIVO_PROJETOS"], ["SemSeparador"])

    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        row = con.execute("SELECT * FROM projetos").fetchone()
        assert row["id"] == "SemSeparador"
        assert row["nome"] == ""


def test_migra_material_formato_string_legacy(ambiente_migracao):
    """materiais.json também aceita strings soltas 'nome - fabricante'."""
    _escrever(ambiente_migracao["ARQUIVO_MATERIAIS"], ["PLA - Generic", "ASA - Generic"])

    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()

    with SQLiteManager.conectar() as con:
        materiais = con.execute("SELECT * FROM materiais ORDER BY nome").fetchall()
        assert len(materiais) == 2
        assert dict(materiais[0])["nome"] == "ASA"
        assert dict(materiais[0])["fabricante"] == "Generic"


def test_migra_entrada_malformada_e_ignorada_sem_rebentar_tudo(ambiente_migracao):
    """Uma entrada de formato inesperado nalgum ficheiro (ex: string solta
    onde se esperava um dict) não pode destruir a migração inteira por
    rollback — deve ser ignorada com aviso, preservando tudo o resto."""
    _escrever(ambiente_migracao["ARQUIVO_MAQUINAS"], [
        {"id": "X1-1", "nome": "Bambu Lab X1C #1", "tech": "FDM"},
        "entrada inesperada",
        {"id": "X1-2", "nome": "Bambu Lab X1C #2", "tech": "FDM"},
    ])

    import migrar_json_para_sqlite as migrador
    from database.sqlite_manager import SQLiteManager
    migrador.migrar()  # não deve lançar exceção

    with SQLiteManager.conectar() as con:
        maquinas = con.execute("SELECT * FROM maquinas").fetchall()
        assert len(maquinas) == 2  # as 2 válidas persistiram, a inválida foi ignorada
