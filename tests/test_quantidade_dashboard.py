"""
Testes da resolução de quantidade mostrada no dashboard.

Regressão: produções SLS ainda em curso apareciam com QNT = 0.0 porque o
dashboard lia apenas os campos em bruto (quantidade_real /
quantidade_consumida), enquanto o CSV de auditoria já usava
ProducaoService.estimar_quantidade() — que para SLS deriva a quantidade a
partir de altura_cuba e percentagem_po_novo. Os dois passaram a usar a
mesma fonte.
"""
from services.producao_service import ProducaoService


def _qtd_dashboard(log):
    """Réplica exata da cadeia usada em historico_tab.py para a coluna QNT."""
    return (
        log.get("quantidade_real") or
        ProducaoService.estimar_quantidade(log) or
        log.get("quantidade") or
        0.0
    )


def test_sls_em_curso_mostra_estimativa_e_nao_zero():
    """O bug original: SLS sem quantidade_real mostrava 0.0 no dashboard."""
    log = {"tecnologia": "SLS", "estado": "Em Andamento",
           "altura_cuba": "465", "percentagem_po_novo": "0.3"}
    resultado = _qtd_dashboard(log)
    assert resultado != 0.0
    assert float(resultado) > 0


def test_sls_fechada_prefere_quantidade_real():
    """Depois de fechada, o valor real tem precedência sobre a estimativa."""
    log = {"tecnologia": "SLS", "estado": "Concluída", "quantidade_real": "8.15",
           "altura_cuba": "465", "percentagem_po_novo": "0.3"}
    assert _qtd_dashboard(log) == "8.15"


def test_dashboard_e_csv_mostram_o_mesmo_valor():
    """Garante que as duas vistas não voltam a divergir."""
    from services.export_service import ExportService
    log = {"tecnologia": "SLS", "estado": "Em Andamento",
           "altura_cuba": "465", "percentagem_po_novo": "0.3"}
    assert str(_qtd_dashboard(log)) == ExportService._obter_quantidade_estimada(log)


def test_fdm_em_curso_usa_quantidade_consumida():
    log = {"tecnologia": "FDM", "estado": "Em Andamento", "quantidade_consumida": "122.92"}
    assert _qtd_dashboard(log) == "122.92"


def test_fdm_fechada_prefere_quantidade_real():
    log = {"tecnologia": "FDM", "estado": "Concluída",
           "quantidade_consumida": "120", "quantidade_real": "118.5"}
    assert _qtd_dashboard(log) == "118.5"


def test_legacy_campo_quantidade_continua_a_funcionar():
    """Produções antigas usavam o campo 'quantidade' (sem sufixo)."""
    log = {"tecnologia": "FDM", "estado": "Concluída", "quantidade": 469.89}
    assert _qtd_dashboard(log) == 469.89


def test_sem_dados_nenhuns_devolve_zero():
    assert _qtd_dashboard({"tecnologia": "FDM", "estado": "Em Andamento"}) == 0.0


def test_sls_com_dados_invalidos_nao_rebenta():
    """Altura não numérica não pode partir o carregamento do dashboard."""
    log = {"tecnologia": "SLS", "altura_cuba": "abc", "percentagem_po_novo": "0.3"}
    assert _qtd_dashboard(log) == 0.0


def test_sls_com_campos_none_nao_rebenta():
    log = {"tecnologia": "SLS", "altura_cuba": None, "percentagem_po_novo": None}
    assert _qtd_dashboard(log) == 0.0


def test_ordenacao_converte_estimativa_para_float():
    """A chave de ordenação da coluna QNT tem de aceitar o mesmo valor que
    é mostrado, incluindo estimativas SLS (string) e vírgula decimal."""
    def _chave(l):
        return float(str(
            l.get("quantidade_real") or ProducaoService.estimar_quantidade(l)
            or l.get("quantidade") or 0
        ).replace(",", "."))

    logs = [
        {"tecnologia": "SLS", "altura_cuba": "465", "percentagem_po_novo": "0.3"},
        {"tecnologia": "FDM", "quantidade_consumida": "122,92"},  # vírgula decimal
        {"tecnologia": "FDM", "quantidade_real": "8.5"},
        {"tecnologia": "FDM"},  # sem dados
    ]
    valores = sorted(_chave(l) for l in logs)
    assert valores[0] == 0.0
    assert valores[-1] == 122.92
