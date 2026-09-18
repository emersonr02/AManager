"""
Testes do AuditService — trilha de auditoria append-only para edições
feitas depois da criação inicial de um registo.
"""
import pytest

from services.audit_service import AuditService


@pytest.fixture
def arquivo_audit(tmp_path, monkeypatch):
    from services import audit_service
    caminho = tmp_path / "audit_log.json"
    monkeypatch.setattr(audit_service, "ARQUIVO_AUDIT_LOG", str(caminho))
    return str(caminho)


def test_registrar_cria_entrada_com_todos_os_campos(arquivo_audit):
    entrada = AuditService.registrar("producao", 1, "estado", "Em Andamento", "Concluída", "joao")
    assert entrada["entidade"] == "producao"
    assert entrada["id_entidade"] == 1
    assert entrada["campo"] == "estado"
    assert entrada["valor_anterior"] == "Em Andamento"
    assert entrada["valor_novo"] == "Concluída"
    assert entrada["utilizador"] == "joao"
    assert "timestamp" in entrada


def test_registrar_sem_mudanca_nao_grava_nada(arquivo_audit):
    resultado = AuditService.registrar("producao", 1, "estado", "Concluída", "Concluída")
    assert resultado is None
    assert AuditService.obter_historico() == []


def test_registrar_usa_utilizador_de_sessao_se_omitido(arquivo_audit, monkeypatch):
    monkeypatch.setenv("USERNAME", "maria")
    entrada = AuditService.registrar("producao", 1, "estado", "A", "B")
    assert entrada["utilizador"] == "maria"


def test_registrar_diferencas_ignora_campos_iguais(arquivo_audit):
    antigos = {"estado": "Em Andamento", "tempo_real": "02:00", "operador": "joao"}
    novos = {"estado": "Concluída", "tempo_real": "02:00", "operador": "joao"}
    entradas = AuditService.registrar_diferencas(
        "producao", 1, antigos, novos, ["estado", "tempo_real", "operador"]
    )
    # Só "estado" mudou — os outros dois campos são iguais, não geram entrada
    assert len(entradas) == 1
    assert entradas[0]["campo"] == "estado"


def test_registrar_diferencas_ignora_campos_fora_da_lista(arquivo_audit):
    antigos = {"estado": "A", "campo_irrelevante": "X"}
    novos = {"estado": "A", "campo_irrelevante": "Y"}  # mudou mas não está na lista
    entradas = AuditService.registrar_diferencas(
        "producao", 1, antigos, novos, ["estado"]  # não inclui "campo_irrelevante"
    )
    assert entradas == []


def test_obter_historico_filtra_por_entidade(arquivo_audit):
    AuditService.registrar("producao", 1, "estado", "A", "B")
    AuditService.registrar("pedido", 5, "requerente_email", "a@x.com", "b@x.com")

    so_producao = AuditService.obter_historico(entidade="producao")
    assert len(so_producao) == 1
    assert so_producao[0]["entidade"] == "producao"


def test_obter_historico_filtra_por_id(arquivo_audit):
    AuditService.registrar("producao", 1, "estado", "A", "B")
    AuditService.registrar("producao", 2, "estado", "A", "B")

    so_id_1 = AuditService.obter_historico(entidade="producao", id_entidade=1)
    assert len(so_id_1) == 1
    assert so_id_1[0]["id_entidade"] == 1


def test_obter_historico_ordena_do_mais_recente(arquivo_audit):
    from database.json_manager import JSONManager
    # Injeta entradas com timestamps explicitamente distintos — evita
    # depender da resolução de segundos do relógio real em testes rápidos.
    JSONManager.salvar([
        {"timestamp": "2026-08-25 10:00:00", "entidade": "producao", "id_entidade": 1, "campo": "campo1"},
        {"timestamp": "2026-08-25 10:05:00", "entidade": "producao", "id_entidade": 1, "campo": "campo2"},
    ], arquivo_audit)
    historico = AuditService.obter_historico(entidade="producao", id_entidade=1)
    assert historico[0]["campo"] == "campo2"  # timestamp mais recente primeiro
    assert historico[1]["campo"] == "campo1"


def test_obter_historico_sem_filtros_devolve_tudo(arquivo_audit):
    AuditService.registrar("producao", 1, "estado", "A", "B")
    AuditService.registrar("pedido", 5, "estado", "X", "Y")
    assert len(AuditService.obter_historico()) == 2


def test_log_e_append_only_nunca_perde_entradas_antigas(arquivo_audit):
    for i in range(5):
        AuditService.registrar("producao", i, "estado", "A", "B")
    assert len(AuditService.obter_historico()) == 5


def test_formatar_entrada_produz_string_legivel(arquivo_audit):
    entrada = AuditService.registrar("producao", 1, "estado", "Em Andamento", "Concluída", "joao")
    texto = AuditService.formatar_entrada(entrada)
    assert "joao" in texto
    assert "estado" in texto
    assert "Em Andamento" in texto
    assert "Concluída" in texto
