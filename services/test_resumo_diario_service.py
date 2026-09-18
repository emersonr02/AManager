"""
Testes do ResumoDiarioService — agregação de dados partilhada entre a
janela automática do resumo do dia e a exportação em PDF, e o controlo
de "já visto hoje" que evita repetir a janela em cada reinício.
"""
import os
import pytest
from datetime import datetime


@pytest.fixture
def ambiente_resumo(tmp_path, monkeypatch):
    from services import producao_service, maquina_service
    from database.json_manager import JSONManager

    caminho_logs = tmp_path / "producao.json"
    caminho_maq = tmp_path / "maquinas.json"

    monkeypatch.setattr(producao_service, "ARQUIVO_LOGS", str(caminho_logs))
    monkeypatch.setattr(maquina_service, "ARQUIVO_MAQUINAS", str(caminho_maq))

    JSONManager.salvar([], str(caminho_logs))
    JSONManager.salvar([], str(caminho_maq))

    return {"logs": str(caminho_logs), "maquinas": str(caminho_maq)}


@pytest.fixture
def marcador_isolado(tmp_path, monkeypatch):
    """Isola o diretório do marcador 'já visto hoje' num tmp_path, para
    os testes não interferirem com o marcador real da máquina de CI/dev."""
    from services import resumo_diario_service
    caminho = tmp_path / ".amanager_teste"
    monkeypatch.setattr(resumo_diario_service.ResumoDiarioService, "_MARCADOR_DIR", str(caminho))
    return str(caminho)


def _seed_logs(caminho, logs):
    from database.json_manager import JSONManager
    JSONManager.salvar(logs, caminho)


def _seed_maquinas(caminho, maquinas):
    from database.json_manager import JSONManager
    JSONManager.salvar(maquinas, caminho)


# ── Agregação de dados ────────────────────────────────────────────────────────

def test_coletar_agrega_producoes_do_dia(ambiente_resumo):
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_logs(ambiente_resumo["logs"], [
        {"id": 1, "maquina": "X1", "data_inicio": f"{hoje} 08:00:00", "estado": "Concluída", "tempo_real": "02:00"},
        {"id": 2, "maquina": "X2", "data_inicio": f"{hoje} 09:00:00", "estado": "Cancelada"},
        {"id": 3, "maquina": "X3", "data_inicio": f"{hoje} 10:00:00", "estado": "Em Andamento", "tempo_estimado": "01:00"},
    ])
    from services.resumo_diario_service import ResumoDiarioService
    dados = ResumoDiarioService.coletar()

    assert len(dados["concluidas"]) == 1
    assert len(dados["canceladas"]) == 1
    assert len(dados["em_curso_hoje"]) == 1
    assert dados["data_referencia"] == hoje


def test_coletar_ignora_producoes_de_outros_dias_nos_kpis(ambiente_resumo):
    _seed_logs(ambiente_resumo["logs"], [
        {"id": 1, "maquina": "X1", "data_inicio": "2020-01-01 08:00:00", "estado": "Concluída"},
    ])
    from services.resumo_diario_service import ResumoDiarioService
    dados = ResumoDiarioService.coletar()  # hoje, não 2020-01-01
    assert len(dados["concluidas"]) == 0


def test_coletar_em_curso_geral_inclui_producoes_antigas_nao_fechadas(ambiente_resumo):
    """em_curso_geral é diferente de em_curso_hoje — inclui produções
    iniciadas em qualquer dia que ainda não fecharam."""
    _seed_logs(ambiente_resumo["logs"], [
        {"id": 1, "maquina": "X1", "data_inicio": "2020-01-01 08:00:00", "estado": "Em Andamento"},
    ])
    from services.resumo_diario_service import ResumoDiarioService
    dados = ResumoDiarioService.coletar()
    assert len(dados["em_curso_hoje"]) == 0       # não é de hoje
    assert len(dados["em_curso_geral"]) == 1       # mas ainda está em curso


def test_coletar_calcula_total_horas(ambiente_resumo):
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_logs(ambiente_resumo["logs"], [
        {"id": 1, "maquina": "X1", "data_inicio": f"{hoje} 08:00:00", "estado": "Concluída", "tempo_real": "02:00"},
        {"id": 2, "maquina": "X2", "data_inicio": f"{hoje} 09:00:00", "estado": "Concluída", "tempo_real": "01:30"},
    ])
    from services.resumo_diario_service import ResumoDiarioService
    dados = ResumoDiarioService.coletar()
    assert dados["total_horas"] == 3.5


def test_coletar_identifica_maquinas_paradas(ambiente_resumo):
    _seed_maquinas(ambiente_resumo["maquinas"], [
        {"id": "M1", "nome": "Máquina 1", "estado": "Operacional"},
        {"id": "M2", "nome": "Máquina 2", "estado": "Manutenção - Parado"},
    ])
    from services.resumo_diario_service import ResumoDiarioService
    dados = ResumoDiarioService.coletar()
    assert len(dados["maquinas_paradas"]) == 1
    assert dados["maquinas_paradas"][0]["id"] == "M2"


def test_coletar_com_nc_e_estado_capa(ambiente_resumo):
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_logs(ambiente_resumo["logs"], [
        {"id": 1, "maquina": "X1", "data_inicio": f"{hoje} 08:00:00", "estado": "Cancelada",
         "nc_codigo": "COD002", "acoes_aplicadas": ["ACT001"]},
        {"id": 2, "maquina": "X2", "data_inicio": f"{hoje} 09:00:00", "estado": "Cancelada",
         "nc_codigo": "COD003", "acoes_aplicadas": []},
    ])
    from services.resumo_diario_service import ResumoDiarioService
    dados = ResumoDiarioService.coletar()
    assert len(dados["com_nc"]) == 2


def test_coletar_dia_vazio_nao_rebenta(ambiente_resumo):
    from services.resumo_diario_service import ResumoDiarioService
    dados = ResumoDiarioService.coletar(data_referencia="2020-01-01")
    assert dados["concluidas"] == []
    assert dados["total_horas"] == 0


def test_coletar_resolve_maquina_legacy_via_id_maquina(ambiente_resumo):
    hoje = datetime.now().strftime("%Y-%m-%d")
    _seed_logs(ambiente_resumo["logs"], [
        {"id": 1, "id_maquina": "X1-1", "data_inicio": f"{hoje} 08:00:00", "estado": "Em Andamento"},
    ])
    _seed_maquinas(ambiente_resumo["maquinas"], [
        {"id": "X1-1", "nome": "Bambu Lab X1C #1", "estado": "Operacional"},
    ])
    from services.resumo_diario_service import ResumoDiarioService
    dados = ResumoDiarioService.coletar()
    assert dados["id_para_nome"]["X1-1"] == "Bambu Lab X1C #1"


# ── Marcador "já visto hoje" ───────────────────────────────────────────────────

def test_ja_visto_hoje_inicialmente_falso(marcador_isolado):
    from services.resumo_diario_service import ResumoDiarioService
    assert ResumoDiarioService.ja_visto_hoje("2026-08-25") is False


def test_marcar_visto_e_depois_ja_visto_hoje(marcador_isolado):
    from services.resumo_diario_service import ResumoDiarioService
    ResumoDiarioService.marcar_visto("2026-08-25")
    assert ResumoDiarioService.ja_visto_hoje("2026-08-25") is True


def test_marcador_e_especifico_do_dia(marcador_isolado):
    from services.resumo_diario_service import ResumoDiarioService
    ResumoDiarioService.marcar_visto("2026-08-25")
    assert ResumoDiarioService.ja_visto_hoje("2026-08-26") is False


def test_marcar_visto_usa_hoje_por_omissao(marcador_isolado):
    from services.resumo_diario_service import ResumoDiarioService
    hoje = datetime.now().strftime("%Y-%m-%d")
    ResumoDiarioService.marcar_visto()  # sem argumento — usa hoje
    assert ResumoDiarioService.ja_visto_hoje(hoje) is True
