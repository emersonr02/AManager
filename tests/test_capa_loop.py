"""
Testes do "loop CAPA" — confirmação de quais ações corretivas sugeridas
para um código de não-conformidade foram de facto aplicadas, e como isso
se reflete no CSV de auditoria.
"""
import csv

from services.nc_service import NCService
from services.export_service import ExportService


def _seed_nc_e_acoes(caminho_falhas, caminho_acoes):
    from database.json_manager import JSONManager
    JSONManager.salvar([
        {"cod": "COD001", "descricao": "Obstrução do bico", "tecnologia": "FDM"},
        {"cod": "COD002", "descricao": "Falha de adesão", "tecnologia": "FDM"},
    ], caminho_falhas)
    JSONManager.salvar([
        {"act": "ACT001", "acao": "Limpeza do nozzle", "codigos_aplicaveis": ["COD001"]},
        {"act": "ACT002", "acao": "Verificação do alinhamento", "codigos_aplicaveis": ["COD001", "COD002"]},
        {"act": "ACT004", "acao": "Troca do filamento", "codigos_aplicaveis": ["COD001", "COD002"]},
    ], caminho_acoes)


# ── NCService: resolução de nomes de ação ──────────────────────────────────────

def test_obter_nome_acao_resolve_codigo_existente(arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc_e_acoes(caminho_falhas, caminho_acoes)
    assert NCService.obter_nome_acao("ACT001") == "Limpeza do nozzle"


def test_obter_nome_acao_devolve_codigo_se_nao_encontrado(arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc_e_acoes(caminho_falhas, caminho_acoes)
    # Ação removida do catálogo depois de já ter sido aplicada num registo antigo
    assert NCService.obter_nome_acao("ACT999") == "ACT999"


def test_formatar_acoes_aplicadas_junta_nomes(arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc_e_acoes(caminho_falhas, caminho_acoes)
    resultado = NCService.formatar_acoes_aplicadas(["ACT001", "ACT004"])
    assert resultado == "Limpeza do nozzle; Troca do filamento"


def test_formatar_acoes_aplicadas_lista_vazia_devolve_string_vazia(arquivos_nc):
    assert NCService.formatar_acoes_aplicadas([]) == ""
    assert NCService.formatar_acoes_aplicadas(None) == ""


def test_formatar_acoes_aplicadas_preserva_ordem(arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc_e_acoes(caminho_falhas, caminho_acoes)
    resultado = NCService.formatar_acoes_aplicadas(["ACT004", "ACT001"])
    assert resultado == "Troca do filamento; Limpeza do nozzle"


# ── Export CSV: coluna de ações aplicadas e taxa de fecho ──────────────────────

def _producao_com_nc(id_=1, nc_codigo="COD001", acoes_aplicadas=None, notas=""):
    return dict(
        id=id_, tecnologia="FDM", maquina="X1C-1", operador="joao",
        data_inicio="2026-08-01 10:00:00", pedidos_vinculados=[],
        estado="Cancelada", quantidade_consumida="10", tempo_estimado="01:00",
        tempo_real="01:00", quantidade_real="10", verificado_por="maria",
        data_fecho="2026-08-01 12:00:00", nc_codigo=nc_codigo,
        acoes_aplicadas=acoes_aplicadas or [], notas_acao_corretiva=notas,
    )


def _ler_csv_como_dicts(caminho, chave_procurada="Nº PRODUÇÃO"):
    with open(caminho, newline='', encoding='utf-8-sig') as f:
        linhas = list(csv.reader(f, delimiter=';'))
    idx_cab = next(i for i, row in enumerate(linhas) if row and row[0] == chave_procurada)
    cabecalho = linhas[idx_cab]
    return cabecalho, linhas[idx_cab + 1:]


def test_csv_inclui_coluna_de_acoes_aplicadas(tmp_path, arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc_e_acoes(caminho_falhas, caminho_acoes)

    caminho_csv = tmp_path / "auditoria.csv"
    prod = _producao_com_nc(acoes_aplicadas=["ACT001", "ACT002"], notas="Bico limpo e alinhado")
    ok = ExportService.exportar_historico_csv(str(caminho_csv), [prod], [])
    assert ok is True

    cabecalho, linhas = _ler_csv_como_dicts(str(caminho_csv))
    dados = dict(zip(cabecalho, linhas[0]))

    assert "AÇÕES CORRETIVAS APLICADAS" in cabecalho
    assert dados["AÇÕES CORRETIVAS APLICADAS"] == "Limpeza do nozzle; Verificação do alinhamento"
    assert dados["NOTAS DA CORREÇÃO"] == "Bico limpo e alinhado"


def test_csv_producao_sem_acoes_aplicadas_fica_vazio(tmp_path, arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc_e_acoes(caminho_falhas, caminho_acoes)

    caminho_csv = tmp_path / "auditoria.csv"
    prod = _producao_com_nc(acoes_aplicadas=[])
    ExportService.exportar_historico_csv(str(caminho_csv), [prod], [])

    cabecalho, linhas = _ler_csv_como_dicts(str(caminho_csv))
    dados = dict(zip(cabecalho, linhas[0]))
    assert dados["AÇÕES CORRETIVAS APLICADAS"] == ""


def test_csv_producao_sem_nc_nao_tem_acoes(tmp_path, arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc_e_acoes(caminho_falhas, caminho_acoes)

    caminho_csv = tmp_path / "auditoria.csv"
    prod = _producao_com_nc(nc_codigo="", acoes_aplicadas=["ACT001"])  # dado inconsistente propositado
    ExportService.exportar_historico_csv(str(caminho_csv), [prod], [])

    cabecalho, linhas = _ler_csv_como_dicts(str(caminho_csv))
    dados = dict(zip(cabecalho, linhas[0]))
    # Sem código NC, não faz sentido mostrar ações — mesmo que o campo exista
    assert dados["CÓDIGO NC"] == ""


def test_pareto_calcula_taxa_de_fecho_capa(tmp_path, arquivos_nc):
    caminho_falhas, caminho_acoes = arquivos_nc
    _seed_nc_e_acoes(caminho_falhas, caminho_acoes)

    caminho_csv = tmp_path / "auditoria.csv"
    producoes = [
        _producao_com_nc(id_=1, nc_codigo="COD001", acoes_aplicadas=["ACT001"]),   # fechada
        _producao_com_nc(id_=2, nc_codigo="COD001", acoes_aplicadas=[]),            # NÃO fechada
        _producao_com_nc(id_=3, nc_codigo="COD002", acoes_aplicadas=["ACT004"]),   # fechada
    ]
    ExportService.exportar_historico_csv(str(caminho_csv), producoes, [])

    conteudo = caminho_csv.read_text(encoding="utf-8-sig")
    assert "TAXA DE FECHO (CAPA)" in conteudo
    linhas = conteudo.replace("\r\n", "\n").split("\n")
    linha_cod001 = next(l for l in linhas if l.startswith("COD001"))
    # COD001: 1 de 2 ocorrências com ação aplicada → 50%
    assert "50%" in linha_cod001
    linha_cod002 = next(l for l in linhas if l.startswith("COD002"))
    # COD002: 1 de 1 ocorrência com ação aplicada → 100%
    assert "100%" in linha_cod002
