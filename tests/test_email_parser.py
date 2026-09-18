"""Testes para PedidoService.importar_de_email e helpers de historico_tab."""
import pytest
from services.pedido_service import PedidoService


# ── Fixtures ──────────────────────────────────────────────────────────────────

PROJETOS = ["247042 - PPS CASTA", "236863 - PPS BEN", "257147 - PPS AquaFountain"]
MATERIAIS = ["ASA - Generic", "PLA - Generic", "PETG - Generic", "PA12 - 3DSystems"]

EMAIL_COMPLETO = """\
TAREFA: Fabrico de peças para protótipo
PROJETO: 247042 - PPS CASTA
REQUERENTE: herminio.fernandes@ceiia.com
LINK FICHEIROS: \\\\ceiia.com\\PPS\\CASTA\\ficheiros
PRAZO DE ENTREGA: 20/09/2026
CRITÉRIOS DE ACEITAÇÃO: Tolerância ±0.2mm
OBSERVAÇÕES: Tecnologia: FDM; Material: ASA - Generic; Entregar em saco.
LISTA DE PEÇAS: CAST-001; ASA - Generic; 10 CAST-002; PLA - Generic; 5
"""

EMAIL_SEM_PECAS = """\
TAREFA: Impressão urgente
PROJETO: 236863 - PPS BEN
LINK FICHEIROS: \\\\ceiia.com\\PPS\\BEN\\job01
PRAZO DE ENTREGA: 2026-12-01
OBSERVAÇÕES: Tecnologia: SLS; Material: PA12 - 3DSystems
"""

EMAIL_DATA_FORMATO_ISO = """\
PROJETO: 257147 - PPS AquaFountain
PRAZO DE ENTREGA: 2026-11-15
OBSERVAÇÕES: Tecnologia: SLA
LISTA DE PEÇAS: AQF-001; ASA - Generic; 3
"""


# ── Testes do parser ───────────────────────────────────────────────────────────

def test_email_completo_extrai_projeto():
    r = PedidoService.importar_de_email(EMAIL_COMPLETO, PROJETOS, MATERIAIS)
    assert r["nr_projeto"] == "247042"
    assert r["nome_projeto"] == "PPS CASTA"


def test_email_completo_converte_data_dd_mm_aaaa():
    r = PedidoService.importar_de_email(EMAIL_COMPLETO, PROJETOS, MATERIAIS)
    assert r["data_entrega"] == "2026-09-20"


def test_email_completo_extrai_tecnologia_fdm():
    r = PedidoService.importar_de_email(EMAIL_COMPLETO, PROJETOS, MATERIAIS)
    assert r["tecnologia"] == "FDM"


def test_email_completo_extrai_duas_pecas():
    r = PedidoService.importar_de_email(EMAIL_COMPLETO, PROJETOS, MATERIAIS)
    assert len(r["pecas"]) == 2
    assert r["pecas"][0]["pn"] == "CAST-001"
    assert r["pecas"][0]["qtd"] == "10"
    assert r["pecas"][1]["pn"] == "CAST-002"
    assert r["pecas"][1]["qtd"] == "5"


def test_email_completo_match_material_parcial():
    r = PedidoService.importar_de_email(EMAIL_COMPLETO, PROJETOS, MATERIAIS)
    # "ASA - Generic" deve bater com o material "ASA - Generic" da lista
    assert r["pecas"][0]["material"] == "ASA - Generic"


def test_email_sem_pecas_usa_link_como_pn():
    r = PedidoService.importar_de_email(EMAIL_SEM_PECAS, PROJETOS, MATERIAIS)
    assert len(r["pecas"]) == 1
    assert r["pecas"][0]["pn"] == "job01"


def test_email_tecnologia_sls():
    r = PedidoService.importar_de_email(EMAIL_SEM_PECAS, PROJETOS, MATERIAIS)
    assert r["tecnologia"] == "SLS"


def test_email_data_formato_iso():
    r = PedidoService.importar_de_email(EMAIL_DATA_FORMATO_ISO, PROJETOS, MATERIAIS)
    assert r["data_entrega"] == "2026-11-15"


def test_email_projeto_inferido_por_link():
    email = """\
TAREFA: Teste
LINK FICHEIROS: \\\\ceiia.com\\PPS\\CASTA\\ficheiros
PRAZO DE ENTREGA: 01/01/2027
OBSERVAÇÕES: Tecnologia: FDM
"""
    r = PedidoService.importar_de_email(email, PROJETOS, MATERIAIS)
    assert r["nr_projeto"] == "247042"


def test_email_vazio_devolve_campos_vazios():
    r = PedidoService.importar_de_email("", PROJETOS, MATERIAIS)
    assert r["nr_projeto"] == ""
    assert r["pecas"] == []


def test_email_data_invalida_passa_raw():
    email = "PROJETO: 236863 - PPS BEN\nPRAZO DE ENTREGA: amanha\nOBSERVAÇÕES: Tecnologia: FDM\n"
    r = PedidoService.importar_de_email(email, PROJETOS, MATERIAIS)
    assert r["data_entrega"] == "amanha"   # raw — a UI mostrará erro de formato


def test_email_observacoes_filtra_tecnologia_e_material():
    r = PedidoService.importar_de_email(EMAIL_COMPLETO, PROJETOS, MATERIAIS)
    obs = r["observacoes"]
    assert "Tecnologia:" not in obs
    assert "Material:" not in obs
    assert "Entregar em saco" in obs
